# SPDX-License-Identifier: MIT
"""Shared offline checks and USB trace metrics for the V108 utilities (stdlib only)."""
import collections, errno, hashlib, json, os, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
STOCK_SHA = '7b1b64d424aad7fe3f9397c2480e8bd12186bad0899dd4d88ee8e39ff4cd8a84'
CANDIDATE_SHA = '97e1f51c616a61b400b079cb5cf3b6a8a0a63bed485a19fcd838e3fc2bb8f6be'
# sysfs reads can race physical unplug or a kernel USB reset. Permission errors must propagate.
DISCONNECT_ERRNOS = {errno.ENOENT, errno.ENODEV, errno.ENXIO, errno.ESTALE, errno.EIO}
class CheckError(RuntimeError): pass
def require(condition, message):
 if not condition: raise CheckError(message)
def sha(data): return hashlib.sha256(data).hexdigest()
def images():
 stock = (ROOT/'firmware/stock-full-isp.bin').read_bytes()
 candidate = (ROOT/'firmware/patched-v2-full-isp.bin').read_bytes()
 require(len(stock) == len(candidate) == 65536, 'Full images must be exactly 65536 bytes')
 require(sha(stock) == STOCK_SHA and sha(candidate) == CANDIDATE_SHA, 'Full image SHA-256 mismatch')
 require([i for i,(a,b) in enumerate(zip(stock,candidate)) if a != b] == [0x6881,0x6882,0x6883], 'Unexpected patch range')
 require(stock[0x6881:0x6884] == bytes.fromhex('12e153') and candidate[0x6881:0x6884] == bytes.fromhex('02dfba'), 'Unexpected patch bytes')
 require(stock[61440:] == candidate[61440:], 'Bootloader changed')
 return {name:{'full':full, 'payload':full[:61440], 'sha256':sha(full)}
         for name,full in [('stock',stock),('candidate-v2',candidate)]}

def usb_devices():
 rows=[]
 for p in Path('/sys/bus/usb/devices').glob('*'):
  try:
   vid=(p/'idVendor').read_text().strip(); pid=(p/'idProduct').read_text().strip()
   if (vid,pid) not in [('391d','2005'),('0603','1020'),('0603','1021')]: continue
   rows.append({'port':p.name,'vid':vid,'pid':pid,'bus':int((p/'busnum').read_text()),'address':int((p/'devnum').read_text())})
  except ValueError: continue
  except OSError as error:
   if error.errno not in DISCONNECT_ERRNOS: raise
   continue
 return rows

def target(port=None, mode=None):
 rows=usb_devices()
 require(len(rows)==1, 'Expected exactly one V108/ISP device; found: '+str(rows))
 row=rows[0]
 require(port is None or row['port']==port, 'Device is on a different USB port: '+str(row))
 if mode=='normal': require((row['vid'],row['pid'])==('391d','2005'), 'Expected normal V108 mode')
 if mode=='isp': require((row['vid'],row['pid'])==('0603','1020'), 'Expected verified SH68F90 ISP 0603:1020')
 return row

def restore_owner(directory):
 if 'SUDO_UID' not in os.environ: return
 for p in [directory,*directory.rglob('*')]: os.chown(p,int(os.environ['SUDO_UID']),int(os.environ['SUDO_GID']))

def trace_metrics(lines,bus,addresses):
 """Parse headers only; -115:1 is submitted, 0:1 successful, -71:1 EPROTO."""
 addresses=set(addresses); pending={}; counts=collections.Counter(); endpoints={}; events=[]; latencies=[]
 first=None; first_keyboard=None; malformed=0
 for line in lines:
  f=line.split()
  if len(f)<6: continue
  try:
   kind,b,a,ep=f[3].split(':'); b,a,ep=int(b),int(a),int(ep)
   if b != bus or a not in addresses: continue
   stamp=int(f[1]); phase=f[2]
   if phase=='S':
    pending[f[0]]=(stamp,f[3]); first=stamp if first is None else min(first,stamp);continue
   if phase not in ('C','E'): continue
   status=int(f[4].split(':')[0]); length=int(f[5]); counts[str(status)]+=1
   submitted=pending.pop(f[0],None)
   latency=(stamp-submitted[0])/1000 if submitted else None
   if kind=='Ii':
    key=str(ep); endpoints.setdefault(key,{'successful':0,'eproto':0,'other_errors':0})
    if status==0:
     endpoints[key]['successful']+=1
     if ep==1 and length==8 and first_keyboard is None: first_keyboard=stamp
    elif status==-71: endpoints[key]['eproto']+=1
    elif status not in (-2,-19,-104,-108): endpoints[key]['other_errors']+=1
   if status and status not in (-2,-19,-104,-108):
    events.append({'time_us':stamp,'transfer':f[3],'status':status,'latency_ms':latency})
   if kind in ('Ci','Co') and latency is not None: latencies.append(latency)
  except (ValueError,IndexError): malformed+=1
 return {'bus':bus,'addresses':sorted(addresses),'completion_status_counts':dict(counts),'interrupt_endpoints':endpoints,
  'eproto_completions':sum(v['eproto'] for v in endpoints.values()),'error_events':events,
  'maximum_control_latency_ms':max(latencies,default=None),
  'first_submission_to_first_8byte_keyboard_report_ms':(first_keyboard-first)/1000 if first_keyboard is not None and first is not None else None,
  'malformed_rows':malformed}

def reset_lines(journal,port):
 return [line for line in journal.splitlines() if re.search(r'\busb '+re.escape(port)+r':',line) and re.search(r'\breset (?:low|full|high|super)',line,re.I)]

def write_json(path,value): path.write_text(json.dumps(value,indent=2,ensure_ascii=True)+'\n')
