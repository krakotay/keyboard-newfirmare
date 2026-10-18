#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Capture a physical V108 reconnect, or analyze an existing header-only usbmon trace. Reports are in English."""
import argparse, datetime, os, select, subprocess, sys, time
from pathlib import Path
from v108_common import ROOT, DISCONNECT_ERRNOS, CheckError, require, restore_owner, target, trace_metrics, reset_lines, write_json

def arguments():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--label',default='manual',help='Image/experiment label, e.g. candidate-v2 or stock')
 p.add_argument('--seconds',type=int,default=30,help='Capture window (15..600 seconds; default: 30)')
 p.add_argument('--port',help='Expected physical USB path, e.g. 3-1')
 p.add_argument('--trace',type=Path,help='Offline mode: analyze an existing usbmon file, no device access')
 p.add_argument('--journal',type=Path,help='Optional saved kernel log for offline mode')
 p.add_argument('--bus',type=int,default=3,help='USB bus for offline analysis')
 p.add_argument('--address',type=int,action='append',help='Target address for offline analysis; repeat if needed')
 p.add_argument('--control-probe',action='store_true',help='Also poll standard GET_DESCRIPTOR/GET_CONFIGURATION to distinguish EP0 failure from IN-only failure; changes traffic')
 p.add_argument('--compare',type=Path,help='Previous report.json to compare')
 p.add_argument('--output',type=Path,help='New output directory (must not exist)')
 return p.parse_args()

def port_address(port):
 """Ignore address 0 (a temporary kernel reset state), never attribute default-address traffic."""
 q=Path('/sys/bus/usb/devices')/port
 try:
  if (q/'idVendor').read_text().strip()!='391d' or (q/'idProduct').read_text().strip()!='2005': return None
  address=int((q/'devnum').read_text())
  return address if 1<=address<=127 else None
 except ValueError: return None
 except OSError as error:
  if error.errno not in DISCONNECT_ERRNOS: raise
  return None

def collect_headers(fd,port,initial,seconds):
 rows=[];buffer=b'';addresses={initial};events=[];present=True
 start=time.monotonic();next_progress=start+5;stop_reason='timer_expired'
 try:
  while time.monotonic()-start<seconds:
   address=port_address(port)
   if address is not None and not 1<=address<=127:address=None
   if address is not None:
    if address not in addresses:
     events.append({'event':'new_usb_address','address':address,'elapsed_s':round(time.monotonic()-start,3)})
     print('Re-enumerated at address '+str(address),flush=True)
    addresses.add(address)
   if address is None and present:
    events.append({'event':'device_unavailable_or_resetting','elapsed_s':round(time.monotonic()-start,3)})
   present=address is not None
   if select.select([fd],[],[],.05)[0]:
    try:buffer+=os.read(fd,65536)
    except BlockingIOError:continue
    while b'\n' in buffer:
     raw,buffer=buffer.split(b'\n',1);line=raw.decode(errors='replace');f=line.split()
     if len(f)>3 and f[3].split(':')[0] in ('Ci','Co','Ii','Io'):
      rows.append(line.split(' = ')[0])
   now=time.monotonic()
   if now>=next_progress:
    print(f'Capturing: {max(0,int(seconds-(now-start)))} seconds remaining. Ctrl+C saves collected data.',flush=True)
    next_progress=now+5
 except KeyboardInterrupt:
  stop_reason='user_interrupt'
  print('Capture stopped by Ctrl+C. Saving collected data and English reports...',flush=True)
 return rows,addresses,events,{'duration_s':round(time.monotonic()-start,3),'requested_duration_s':seconds,
  'stop_reason':stop_reason,'partial_capture':stop_reason=='user_interrupt'}

def capture(args,out):
 require(os.geteuid()==0,'Live capture requires sudo; offline analysis does not')
 require(15<=args.seconds<=600,'--seconds must be between 15 and 600')
 row=target(args.port,'normal');port=row['port'];bus=row['bus'];initial=row['address']
 mon=Path('/sys/kernel/debug/usb/usbmon')/f'{bus}u'
 if not mon.exists():subprocess.run(['modprobe','usbmon'],check=True)
 require(mon.exists(),'usbmon is unavailable; mount debugfs before retrying')
 fd=os.open(mon,os.O_RDONLY|os.O_NONBLOCK)
 since=datetime.datetime.now(datetime.timezone.utc).isoformat()
 print(f'CAPTURE READY: {port}, bus {bus}. Window: {args.seconds} seconds.',flush=True)
 print('Unplug/switch off the keyboard, wait at least 3 seconds, reconnect to the SAME port.',flush=True)
 print('When ready, press and release one harmless key once. No key payload is stored.',flush=True)
 print('Wait for the report path; Ctrl+C also saves a partial report.',flush=True)
 probe=None;probe_summary={'enabled':False}
 if getattr(args,'control_probe',False):
  from usb_control_probe import StandardControlProbe
  probe=StandardControlProbe(port);probe.start()
  print('Standard IN-only control probe enabled (GET_DESCRIPTOR/GET_CONFIGURATION).',flush=True)
 try:rows,addresses,events,timing=collect_headers(fd,port,initial,args.seconds)
 finally:
  os.close(fd)
  if probe is not None:probe_summary=probe.stop(out)
 filtered=[]
 for line in rows:
  try:
   _,b,a,_=line.split()[3].split(':')
   if int(b)==bus and int(a) in addresses:filtered.append(line)
  except (ValueError,IndexError):pass
 (out/'usbmon-headers.txt').write_text('\n'.join(filtered)+'\n')
 journal_result=subprocess.run(['journalctl','-k','--since',since,'--no-pager','-o','short-monotonic'],capture_output=True,text=True)
 journal='\n'.join(line for line in journal_result.stdout.splitlines() if f'usb {port}:' in line)+'\n'
 (out/'kernel-usb.log').write_text(journal);write_json(out/'connection-events.json',events)
 new_addresses=addresses-{initial}
 return filtered,journal,bus,sorted(new_addresses or addresses),{'mode':'live','port':port,'initial_address':initial,
  'physical_reconnect_observed':bool(new_addresses),'connection_events':events,'control_probe':probe_summary,**timing,
  'journal_available':journal_result.returncode==0,'journal_error':journal_result.stderr.strip() if journal_result.returncode else None}

def main():
 args=arguments();stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
 out=(args.output or ROOT/'reports'/('startup-'+stamp)).resolve()
 out.mkdir(parents=True,exist_ok=False)
 try:
  if args.trace:
   require(args.address,'Offline analysis requires --address')
   lines=args.trace.read_text().splitlines();journal=args.journal.read_text() if args.journal else ''
   bus=args.bus;addresses=args.address;meta={'mode':'offline','source_trace':str(args.trace.resolve()),'port':args.port,
    'physical_reconnect_observed':None,'journal_available':bool(args.journal)}
  else: lines,journal,bus,addresses,meta=capture(args,out)
  metrics=trace_metrics(lines,bus,addresses)
  resets=reset_lines(journal,meta['port']) if meta.get('port') and meta['journal_available'] else None
  verdict='Transport errors observed' if metrics['eproto_completions'] or any(v['other_errors'] for v in metrics['interrupt_endpoints'].values()) else 'No interrupt transfer errors observed in this capture'
  if resets and verdict.startswith('No interrupt'): verdict='Kernel USB recovery resets observed'
  if verdict.startswith('No interrupt') and not metrics['interrupt_endpoints'].get('1',{}).get('successful',0):
   verdict='Inconclusive: no successful keyboard interrupt report captured'
  if not metrics['completion_status_counts']: verdict='Inconclusive: no target USB completions captured'
  elif meta['mode']=='live' and not meta['physical_reconnect_observed']: verdict='Inconclusive: no new USB address observed; repeat a physical reconnect'
  result={'report_version':1,'created_utc':stamp,'label':args.label,'verdict':verdict,**meta,'metrics':metrics,
   'kernel_reset_count':len(resets) if resets is not None else None,'kernel_reset_lines':resets,
   'limitations':['USB address change confirms re-enumeration, not a measured power-off interval.',
    'The first successful keyboard report depends on a key press and is not an exact readiness time.',
    'Time before USB enumeration and BIOS behavior are not measured.',
    'No keystroke payload is retained. The image label is user-supplied; firmware is not read or written.']}
  if args.compare:
   import json
   old=json.loads(args.compare.read_text());require('metrics' in old,'Comparison file is not a startup report')
   result['comparison']={'baseline':str(args.compare.resolve()),'baseline_label':old.get('label'),
    'eproto_before':old['metrics']['eproto_completions'],'eproto_now':metrics['eproto_completions'],
    'kernel_resets_before':old.get('kernel_reset_count'),'kernel_resets_now':result['kernel_reset_count']}
  write_json(out/'report.json',result)
  m=metrics
  text=['# VGN V108 USB startup report','',f'- UTC: {stamp}',f'- Label (user supplied): {args.label}',f'- Verdict: **{verdict}**',
   f'- Capture stop reason: {meta.get("stop_reason","offline analysis")}',f'- Partial capture: {meta.get("partial_capture",False)}',
   f'- Physical reconnect observed: {meta["physical_reconnect_observed"]}',f'- USB bus / addresses: {bus} / {addresses}',
   f'- Interrupt EPROTO (-71) completions: {m["eproto_completions"]}',f'- Kernel recovery resets: {result["kernel_reset_count"]}',
   f'- Maximum control transfer latency: {m["maximum_control_latency_ms"]} ms',
   f'- First USB submission to first 8-byte keyboard report: {m["first_submission_to_first_8byte_keyboard_report_ms"]} ms','',
   f'- Standard control probe: {meta.get("control_probe",{"enabled":False})}',
   '## Interrupt endpoints','', '| Endpoint | Successful | EPROTO | Other errors |','|---|---:|---:|---:|']
  for ep,v in m['interrupt_endpoints'].items():text.append(f'| {ep} | {v["successful"]} | {v["eproto"]} | {v["other_errors"]} |')
  if 'comparison' in result:
   c=result['comparison'];text+=['','## Comparison','',f'Baseline: {c["baseline_label"]}',f'EPROTO: {c["eproto_before"]} -> {c["eproto_now"]}',f'Kernel resets: {c["kernel_resets_before"]} -> {c["kernel_resets_now"]}']
  text+=['','## Limits','']+['- '+s for s in result['limitations']]
  (out/'report.md').write_text('\n'.join(text)+'\n')
  print(verdict);print('English reports: '+str(out/'report.md')+' and report.json')
 except (Exception, KeyboardInterrupt) as error:
  message=str(error) or type(error).__name__
  write_json(out/'report.json',{'report_version':1,'label':args.label,'status':'capture_failed','error':message})
  (out/'report.md').write_text('# VGN V108 USB startup report\n\nCapture failed: '+message+'\n')
  raise
 finally: restore_owner(out)

if __name__=='__main__':
 try: main()
 except KeyboardInterrupt:
  print('Cancelled outside the capture window.',file=sys.stderr);sys.exit(130)
 except (CheckError,OSError,ValueError,subprocess.SubprocessError) as e:
  print('ERROR: '+str(e),file=sys.stderr);sys.exit(1)
