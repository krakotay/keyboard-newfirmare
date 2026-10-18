# SPDX-License-Identifier: MIT
"""Offline patch/control-path and standard GET probe checks. Never opens USB."""
import ctypes,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from v108_common import images

class PatchTest(unittest.TestCase):
 def test_v2_exact_patch_and_existing_critical_wrapper(self):
  v=images();a=v['stock']['full'];b=v['candidate-v2']['full']
  self.assertEqual([i for i,(x,y) in enumerate(zip(a,b)) if x!=y],[0x6881,0x6882,0x6883])
  self.assertEqual(a[0x6881:0x6884],bytes.fromhex('12e153'))
  self.assertEqual(b[0x6881:0x6884],bytes.fromhex('02dfba'))
  self.assertEqual(b[0xdfba:0xdfc2],bytes.fromhex('c2af12e117d2af22'))
  self.assertEqual(b[0xe00b],0x11);self.assertEqual(a[61440:],b[61440:])
 def test_tail_jump_returns_to_irq_epilogue_instead_of_stale_dispatch_snapshot(self):
  # A deliberately limited interpreter of the changed path, NOT an MCU/hardware emulator.
  def run(blob):
   pc=0x6881;stack=[0x83b9];pending=False;ea=True;atomic=None;reset=False
   for _ in range(64):
    if pc in (0x6884,0x83b9):return pc,pending,reset,atomic,ea
    if pc==0xd40e:
     # Summarize the unchanged common init. The actual verified bytes clear USBADDR.
     self.assertEqual(blob[0xd429:0xd430],bytes.fromhex('e4f592f593f596'))
     reset=True;atomic=not ea;pc=stack.pop();continue
    op=blob[pc]
    if op in (2,0x12):
     dest=int.from_bytes(blob[pc+1:pc+3],'big')
     if op==0x12:stack.append(pc+3)
     pc=dest
    elif op==0x22:pc=stack.pop()
    elif op==0:pc+=1
    elif op in(0xc2,0xd2):
     bit=blob[pc+1]
     if bit==0x61:pending=op==0xd2
     elif bit==0xaf:ea=op==0xd2
     else:self.fail('Unexpected bit operation')
     pc+=2
    elif op in(0x43,0x53):
     self.assertEqual(blob[pc+1],0x91);pc+=3
    else:self.fail(f'Unsupported path opcode at {pc:04x}')
   self.fail('Path did not return')
  v=images()
  self.assertEqual(run(v['stock']['full']),(0x6884,True,False,None,True))
  self.assertEqual(run(v['candidate-v2']['full']),(0x83b9,False,True,True,True))

class StandardProbeTest(unittest.TestCase):
 def test_probe_only_issues_expected_standard_in_requests(self):
  import usb_control_probe as probe
  requests=[]
  def ioctl(fd,number,pointer):
   cmd=ctypes.cast(pointer,ctypes.POINTER(probe.ControlTransfer)).contents
   requests.append((cmd.request_type,cmd.request,cmd.value,cmd.index,cmd.length,cmd.timeout_ms))
   data=(bytes.fromhex('12011001000000081d390520093001020001') if cmd.request==6 else b'\x01')
   ctypes.memmove(cmd.data,data,len(data));return len(data)
  with patch.object(probe.libc,'ioctl',side_effect=ioctl):
   desc=probe.read_request(123,'device_descriptor');config=probe.read_request(123,'configuration')
  self.assertEqual(requests,[(0x80,6,0x100,0,18,120),(0x80,8,0,0,1,120)])
  self.assertEqual((desc['vid'],desc['pid']),('391d','2005'));self.assertEqual(config['configuration'],1)
  with self.assertRaises(ValueError):probe.read_request(123,'write')

if __name__=='__main__':unittest.main()
