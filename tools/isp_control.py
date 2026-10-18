# SPDX-License-Identifier: MIT
"""Sinowealth ISP entry/reboot and device snapshots; no flash write/erase commands."""
import argparse,fcntl,json,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VIDPID='0003:0000391D:00002005'
BOOTIDS=('0003:00000603:00001020','0003:00000603:00001021')
def devices():
 rows=[]
 for p in sorted(Path('/sys/class/hidraw').glob('hidraw*')):
  event=(p/'device/uevent').read_text()
  fields=dict(line.split('=',1) for line in event.splitlines() if '=' in line)
  if fields.get('HID_ID')==VIDPID or fields.get('HID_ID') in BOOTIDS:
   rows.append((p,fields))
 return rows
def snapshot(label):
 out=ROOT/'dumps'/label
 out.mkdir(parents=True,exist_ok=False)
 rows=[]
 for p,fields in devices():
  data=(p/'device/report_descriptor').read_bytes()
  (out/(p.name+'-report-descriptor.bin')).write_bytes(data)
  rows.append(dict(node='/dev/'+p.name,descriptor_length=len(data),**fields))
 (out/'hid-devices.json').write_text(json.dumps(rows,indent=2)+'\n')
 for cmd,name in [(['lsusb'],'lsusb.txt'),(['lsusb','-t'],'lsusb-tree.txt')]:
  r=subprocess.run(cmd,capture_output=True,text=True)
  (out/name).write_text(r.stdout+r.stderr)
 print(json.dumps(rows,indent=2),flush=True)
 return rows
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('action',choices=['snapshot','enter','reboot'])
parser.add_argument('--label',required=True)
args=parser.parse_args()
if args.action=='snapshot':snapshot(args.label)
else:
 choices=[(p,f) for p,f in devices() if (f['HID_ID']==VIDPID and f.get('HID_PHYS','').endswith('/input1'))] if args.action=='enter' else [(p,f) for p,f in devices() if f['HID_ID'] in BOOTIDS]
 if len(choices)!=1:raise RuntimeError('Expected exactly one matching interface; got '+str(choices))
 p,f=choices[0]; command=bytes([5,0x75 if args.action=='enter' else 0x5a,0,0,0,0])
 print('Target',p.name,f,'command',command.hex(' '),flush=True)
 fd=os.open('/dev/'+p.name,os.O_RDWR|os.O_NONBLOCK)
 try:
  fcntl.ioctl(fd,(3<<30)|(len(command)<<16)|(ord('H')<<8)|6,command)
 except OSError as e:
  print('Command completion:',repr(e),'(device may have re-enumerated)',flush=True)
 finally:os.close(fd)
 time.sleep(3)
 snapshot(args.label)
