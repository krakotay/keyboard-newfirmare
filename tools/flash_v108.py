#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Flash the verified V108 candidate or stock image; defaults to an offline dry run. English audit reports."""
import argparse, datetime, json, os, subprocess, sys, time
from pathlib import Path
from v108_common import ROOT, CheckError, images, require, restore_owner, sha, target, write_json

def arguments():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--image',choices=['candidate-v2','stock'],required=True)
 p.add_argument('--execute',action='store_true',help='Actually enter ISP, read, erase/write if needed, verify and reboot')
 p.add_argument('--port',help='Require this physical USB port (e.g. 3-1); otherwise discover exactly one target')
 p.add_argument('--recover',action='store_true',help='Stock only: allow an already-ISP device and unknown main firmware, with a verified original bootloader')
 p.add_argument('--output',type=Path,help='New audit directory (must not exist)')
 return p.parse_args()

class Transaction:
 def __init__(self,out,port): self.out=out;self.port=port
 def run(self,name,cmd):
  print(name,flush=True)
  with (self.out/(name+'.log')).open('w') as f:
   r=subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,timeout=120)
  print((self.out/(name+'.log')).read_text(),flush=True)
  require(r.returncode==0,name+' failed (exit '+str(r.returncode)+'); see log')
 def cli(self,name,action,path,reboot=False,section='full'):
  # DeviceSelector searches global ISP IDs: enforce exactly one matching target on the same port first.
  target(self.port,'isp')
  cmd=[str(ROOT/'bin/sinowealth-kb-tool'),action,'--platform','sh68f90','--vendor_id','0x391d','--product_id','0x2005',
       '--isp_iface_num','1','--isp_report_id','5','--retry','1','--reboot',str(reboot).lower()]
  if action=='read':cmd+=['--section',section]
  self.run(name,cmd+[str(path)])
 def enter(self,name):
  target(self.port,'normal')
  self.run(name,['python3',str(ROOT/'tools/isp_control.py'),'enter','--label',self.out.name+'-'+name])
  target(self.port,'isp')
 def reboot(self,name):
  self.cli(name,'read',self.out/(name+'-bootloader.bin'),True,'bootloader')
 def wait_normal(self):
  end=time.monotonic()+12
  while time.monotonic()<end:
   try: return target(self.port,'normal')
   except CheckError: time.sleep(.2)
  raise CheckError('V108 did not return to normal USB mode within 12 seconds')

def main():
 args=arguments();require(not args.recover or args.image=='stock','--recover is restricted to the original stock image')
 verified=images();image=verified[args.image]
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
 out=(args.output or ROOT/'dumps'/('flash-'+args.image+'-'+stamp)).resolve();out.mkdir(parents=True,exist_ok=False)
 result={'report_version':1,'created_utc':stamp,'requested_image':args.image,'execute':args.execute,'recover':args.recover,
  'expected_full_sha256':image['sha256'],'payload_sha256':sha(image['payload']),'status':'preflight_passed',
  'write_scope':'Main firmware only, 61440 bytes. Original 4096-byte bootloader excluded from write payload.'}
 def save():
  write_json(out/'report.json',result)
  text=['# VGN V108 firmware operation','']+[f'- {k}: {v}' for k,v in result.items()]
  text+=['','A verified readback proves image identity, not startup latency or BIOS compatibility.',
   'Software recovery requires working USB ISP access; hardware recovery is not verified.']
  (out/'report.md').write_text('\n'.join(text)+'\n')
 tx=None;entered=False;writing=False;previous=None
 try:
  save()
  print('Images verified. Target:',args.image,'full SHA-256:',image['sha256'],flush=True)
  if not args.execute:
   result['status']='dry_run_passed_no_device_commands';save()
   print('DRY RUN: no USB commands, erase, or write performed. Add --execute to flash.')
   return
  require(os.geteuid()==0,'Actual flashing requires sudo')
  require((ROOT/'bin/sinowealth-kb-tool').is_file(),'Missing binary: run bash tools/build.sh')
  # Only two full images are distributed. ISP write payloads are derived locally,
  # outside the tracked publication, and never include the 4096-byte bootloader.
  payloads={}
  for name,value in verified.items():
   payloads[name]=out/(name+'-main-isp.bin')
   payloads[name].write_bytes(value['payload'])
  device=target(args.port,None if args.recover else 'normal');result['device']=device
  tx=Transaction(out,device['port'])
  if device['vid']=='391d':tx.enter('01-enter-isp')
  else:target(device['port'],'isp')
  entered=True
  tx.cli('02-preflash-read','read',out/'before-full.bin')
  before=(out/'before-full.bin').read_bytes();result['before_full_sha256']=sha(before)
  require(len(before)==65536 and before[61440:]==verified['stock']['full'][61440:],'Unexpected bootloader/geometry: no write permitted')
  previous=next((name for name,v in verified.items() if before==v['full']),None)
  result['previous_image']=previous or 'unknown'
  require(previous is not None or args.recover,'Current firmware is unknown: refusing write (stock recovery requires --recover)')
  # Revalidate payload on disk immediately before the destructive command.
  require(sha(payloads[args.image].read_bytes())==result['payload_sha256'],'Payload changed during preflight')
  if before==image['full']:
   result['status']='already_installed_no_erase_or_write'
  else:
   writing=True;result['status']='writing';save()
   tx.cli('03-write-'+args.image,'write',payloads[args.image])
   tx.cli('04-independent-readback','read',out/'after-full.bin')
   actual=(out/'after-full.bin').read_bytes();result['readback_full_sha256']=sha(actual)
   require(actual==image['full'],'Independent full readback mismatch')
   result['status']='written_and_verified';result['bootloader_unchanged']=True
  tx.reboot('05-reboot');tx.wait_normal();result['normal_usb_restored']=True;save()
  print('CURRENT VERIFIED IMAGE: '+args.image+(' (original firmware; experimental patch is absent)' if args.image=='stock' else ' (experimental USB reset patch: '+args.image+')'),flush=True)
 except (Exception, KeyboardInterrupt) as error:
  result['error']=str(error);result['status']='failed';save()
  if tx and writing:
   # Restore a known pre-write image, or stock in explicit recovery mode.
   recovery=previous or 'stock'
   try:
    now=target(tx.port)
    if now['vid']=='391d':tx.enter('90-reenter-for-rollback')
    require(sha(payloads[recovery].read_bytes())==sha(verified[recovery]['payload']),'Rollback payload changed')
    tx.cli('91-rollback-'+recovery,'write',payloads[recovery])
    tx.cli('92-rollback-verify','read',out/'rollback-full.bin')
    require((out/'rollback-full.bin').read_bytes()==verified[recovery]['full'],'Rollback readback mismatch')
    tx.reboot('93-rollback-reboot');tx.wait_normal()
    result.update(status='failed_but_rollback_verified',restored_image=recovery,normal_usb_restored=True)
   except Exception as rollback_error:result.update(status='recovery_required',rollback_error=str(rollback_error))
  elif tx and entered and (previous is not None or not args.recover):
   try:tx.reboot('90-abort-reboot');tx.wait_normal();result['normal_usb_restored']=True
   except Exception as reboot_error:result['reboot_error']=str(reboot_error)
  save();raise
 finally:
  save();restore_owner(out)
  # isp_control snapshots are also part of this audit and should remain user-owned.
  for snap in (ROOT/'dumps').glob(out.name+'-*'):
   if snap.is_dir():restore_owner(snap)
  print('English audit report: '+str(out/'report.md'),flush=True)

if __name__=='__main__':
 try:main()
 except (CheckError,OSError,ValueError,subprocess.SubprocessError) as e:
  print('ERROR: '+str(e),file=sys.stderr);sys.exit(1)
