# SPDX-License-Identifier: MIT
"""Optional standard USB IN-only control probe; no vendor commands, writes or driver detach."""
import collections,ctypes,errno,json,os,threading,time
from pathlib import Path
from v108_common import CheckError,target,write_json
class ControlTransfer(ctypes.Structure):
 _fields_=[('request_type',ctypes.c_uint8),('request',ctypes.c_uint8),('value',ctypes.c_uint16),
  ('index',ctypes.c_uint16),('length',ctypes.c_uint16),('timeout_ms',ctypes.c_uint32),('data',ctypes.c_void_p)]
USBDEVFS_CONTROL=(3<<30)|(ctypes.sizeof(ControlTransfer)<<16)|(ord('U')<<8)
libc=ctypes.CDLL(None,use_errno=True)
libc.ioctl.argtypes=[ctypes.c_int,ctypes.c_ulong,ctypes.c_void_p];libc.ioctl.restype=ctypes.c_int

def read_request(fd,name):
 # Deliberately restricted to these two standard device-to-host GET operations.
 if name=='device_descriptor':request,value,length=6,0x0100,18
 elif name=='configuration':request,value,length=8,0,1
 else:raise ValueError('Only standard GET_DESCRIPTOR and GET_CONFIGURATION are permitted')
 buffer=ctypes.create_string_buffer(length)
 command=ControlTransfer(0x80,request,value,0,length,120,ctypes.cast(buffer,ctypes.c_void_p))
 start=time.monotonic();ctypes.set_errno(0)
 result=libc.ioctl(fd,USBDEVFS_CONTROL,ctypes.byref(command));elapsed=(time.monotonic()-start)*1000
 row={'request':name,'latency_ms':round(elapsed,3),'length':max(result,0),'errno':ctypes.get_errno() if result<0 else 0}
 if result>=0:
  data=buffer.raw[:result]
  if name=='configuration' and len(data)==1:row['configuration']=data[0]
  if name=='device_descriptor' and len(data)==18:
   row.update(vid=f'{int.from_bytes(data[8:10],"little"):04x}',pid=f'{int.from_bytes(data[10:12],"little"):04x}')
 return row

class StandardControlProbe:
 def __init__(self,port):
  self.port=port;self.rows=[];self.stop_event=threading.Event();self.thread=threading.Thread(target=self.run,daemon=True)
  self.started=time.monotonic();self.error=None
 def start(self):self.thread.start()
 def run(self):
  fd=None;current=None
  try:
   while not self.stop_event.is_set():
    try:
     device=target(self.port,'normal');identity=(device['bus'],device['address'])
     if identity!=current:
      if fd is not None:os.close(fd);fd=None
      fd=os.open(f'/dev/bus/usb/{identity[0]:03d}/{identity[1]:03d}',os.O_RDWR|os.O_CLOEXEC);current=identity
     for name in ('device_descriptor','configuration'):
      if self.stop_event.is_set():break
      row=read_request(fd,name);row.update(bus=identity[0],address=identity[1],elapsed_s=round(time.monotonic()-self.started,6));self.rows.append(row)
    except (CheckError,OSError):
     if fd is not None:os.close(fd);fd=None
     current=None
    self.stop_event.wait(.1)
  except Exception as error:self.error=repr(error)
  finally:
   if fd is not None:os.close(fd)
 def stop(self,out):
  self.stop_event.set();self.thread.join(timeout=2)
  write_json(out/'control-probe.json',{'port':self.port,'error':self.error,'rows':self.rows})
  counts=collections.Counter(str(r['errno']) for r in self.rows)
  return {'enabled':True,'requests':len(self.rows),'errno_counts':dict(counts),'error':self.error,
   'configuration_values':sorted({r['configuration'] for r in self.rows if 'configuration' in r}),
   'maximum_latency_ms':max((r['latency_ms'] for r in self.rows),default=None),
   'limitation':'Periodic standard IN requests perturb USB traffic; use to localize the fault, not to benchmark unchanged startup latency.'}
