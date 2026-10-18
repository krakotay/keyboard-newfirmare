# SPDX-License-Identifier: MIT
"""Offline tests only. Never opens USB or executes the flash CLI."""
import sys, unittest, tempfile
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from v108_common import images, trace_metrics, reset_lines
class ToolsTest(unittest.TestCase):
 def test_real_image_integrity_and_protected_bootloader(self):
  v=images();self.assertEqual(len(v['stock']['full']),65536)
  self.assertEqual(v['stock']['full'][61440:],v['candidate-v2']['full'][61440:])
  for value in v.values():self.assertEqual(value['payload'],value['full'][:61440])
 def test_usbmon_status_interval_suffix_and_payload_ignored(self):
  rows=['a 1000 S Ii:3:020:1 -115:1 8 <',
        'a 3000 C Ii:3:020:1 -71:1 0',
        'a 4000 S Ii:3:020:1 -115:1 8 <',
        'a 5000 C Ii:3:020:1 0:1 8 = deadbeef',
        'b 1000 S Ci:3:020:0 s 80 06 0100 0000 0012 18 <',
        'b 1500 C Ci:3:020:0 -32 0',
        'c 6000 C Ii:3:020:1 -19 0',
        'd 9000 C Ii:3:021:1 -71:1 0',
        'e 9000 C Ii:2:020:1 -71:1 0']
  m=trace_metrics(rows,3,[20]);self.assertEqual(m['eproto_completions'],1)
  self.assertEqual(m['interrupt_endpoints']['1'],{'successful':1,'eproto':1,'other_errors':0})
  self.assertEqual(m['error_events'][0]['latency_ms'],2)
  self.assertEqual(m['maximum_control_latency_ms'],.5)
  self.assertEqual(m['first_submission_to_first_8byte_keyboard_report_ms'],4)
  self.assertNotIn('deadbeef',str(m))
 def test_reset_filter_exact_port(self):
  lines='usb 3-1: reset full-speed USB device\nusb 3-12: reset full-speed USB device\nusb 3-1: new full-speed USB device\n'
  self.assertEqual(len(reset_lines(lines,'3-1')),1)
 def test_no_events_are_not_successful_reports(self):
  m=trace_metrics([],3,[20]);self.assertIsNone(m['first_submission_to_first_8byte_keyboard_report_ms'])
  self.assertEqual(m['completion_status_counts'],{})
class CaptureInterruptionTest(unittest.TestCase):
 def simulate_interrupted_capture(self):
  import check_startup, itertools
  rows=b'a 1000 S Ii:3:022:1 -115:1 8 <\na 3000 C Ii:3:022:1 -71:1 0\nb 4000 C Ii:3:022:1 0:1 8 = private-key-data\n'
  with patch.object(check_startup,'port_address',side_effect=[22,0,22]), \
       patch.object(check_startup.select,'select',side_effect=[([9],[],[]),([],[],[]),KeyboardInterrupt()]), \
       patch.object(check_startup.os,'read',return_value=rows), \
       patch.object(check_startup.time,'monotonic',side_effect=itertools.count()):
   lines,addresses,events,timing=check_startup.collect_headers(9,'3-2',20,30)
  # collect_headers normally receives validated port_address values. Guard zero here too.
  self.assertNotIn('private-key-data','\n'.join(lines))
  self.assertNotIn(0,addresses);self.assertEqual(addresses,{20,22})
  self.assertEqual(len([e for e in events if e['event']=='new_usb_address']),1)
  self.assertEqual(timing['stop_reason'],'user_interrupt');self.assertTrue(timing['partial_capture'])
  return lines,addresses,events,timing
 def test_interrupt_preserves_headers_and_filters_transient_zero(self):
  self.simulate_interrupted_capture()
 def test_partial_capture_still_emits_english_reports_and_comparison(self):
  import check_startup,json
  lines,addresses,events,timing=self.simulate_interrupted_capture()
  meta={'mode':'live','port':'3-2','physical_reconnect_observed':True,'journal_available':True,**timing}
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'capture'
   argv=['check_startup.py','--label','stock','--output',str(out),'--compare',str(Path(__file__).resolve().parents[1]/'reports/stock/report.json')]
   with patch.object(sys,'argv',argv),patch.object(check_startup,'capture',return_value=(lines,'',3,[22],meta)):
    check_startup.main()
   report=json.loads((out/'report.json').read_text());text=(out/'report.md').read_text()
   self.assertTrue(report['partial_capture']);self.assertEqual(report['metrics']['eproto_completions'],1)
   self.assertEqual(report['comparison']['eproto_before'],26)
   self.assertIn('user_interrupt',text);self.assertIn('Partial capture: True',text)
 def test_sysfs_address_zero_is_unavailable(self):
  import check_startup
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);q=root/'3-2';q.mkdir()
   (q/'idVendor').write_text('391d');(q/'idProduct').write_text('2005');(q/'devnum').write_text('0')
   with patch.object(check_startup,'Path',return_value=root):
    self.assertIsNone(check_startup.port_address('3-2'))
    (q/'devnum').write_text('22');self.assertEqual(check_startup.port_address('3-2'),22)

 def test_sysfs_unplug_errno_is_treated_as_temporarily_absent(self):
  import check_startup, errno
  for code in (errno.ENOENT,errno.ENODEV,errno.ENXIO,errno.ESTALE,errno.EIO):
   with self.subTest(errno=code),patch.object(Path,'read_text',side_effect=OSError(code,'Device disconnected')):
    self.assertIsNone(check_startup.port_address('3-2'))
 def test_sysfs_permission_failure_is_not_hidden(self):
  import check_startup, errno
  with patch.object(Path,'read_text',side_effect=PermissionError(errno.EACCES,'Permission denied')):
   with self.assertRaises(PermissionError):check_startup.port_address('3-2')

class FlashTransactionTest(unittest.TestCase):
 def simulate(self, *, corrupt=False, unknown=False, image="candidate-v2", before="stock"):
  import flash_v108
  verified=images();events=[]
  class FakeTransaction:
   def __init__(self,out,port):self.out=out;self.port=port
   def enter(self,name):events.append(name)
   def cli(self,name,action,path,reboot=False,section='full'):
    events.append(name)
    if action=='write':
     # Check the actual locally generated 60KiB payload handed to the CLI.
     expected=verified[before if name.startswith('91') else image]['payload']
     self_test.assertEqual(path.read_bytes(),expected)
     self_test.assertEqual(path.stat().st_size,61440)
    if action=='read':
     data=verified[before]['full'] if name.startswith(('02','92')) else verified[image]['full']
     if unknown and name.startswith('02'):
      data=bytearray(data);data[100]^=1;data=bytes(data)
     if corrupt and name.startswith('04'):
      data=bytearray(data);data[100]^=1;data=bytes(data)
     path.write_bytes(data)
   def reboot(self,name):events.append(name)
   def wait_normal(self):pass
  self_test=self
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'bin').mkdir();(root/'bin/sinowealth-kb-tool').touch();out=root/'audit'
   argv=['flash_v108.py','--image',image,'--execute','--output',str(out)]
   with patch.object(flash_v108,'ROOT',root), patch.object(flash_v108,'images',return_value=verified), \
        patch.object(flash_v108,'Transaction',FakeTransaction), patch.object(flash_v108.os,'geteuid',return_value=0), \
        patch.object(flash_v108,'target',return_value={'port':'3-1','vid':'391d','pid':'2005'}),patch.object(sys,'argv',argv):
    if corrupt or unknown:
     from v108_common import CheckError
     with self.assertRaises(CheckError):flash_v108.main()
    else:flash_v108.main()
   import json
   return events,json.loads((out/'report.json').read_text())
 def test_simulated_success_independent_readback(self):
  events,result=self.simulate();self.assertEqual(result['status'],'written_and_verified')
  self.assertLess(events.index('04-independent-readback'),events.index('05-reboot'))
 def test_simulated_readback_failure_rolls_back_and_verifies(self):
  events,result=self.simulate(corrupt=True)
  self.assertEqual(result['status'],'failed_but_rollback_verified')
  self.assertIn('91-rollback-stock',events);self.assertIn('92-rollback-verify',events)
 def test_simulated_stock_restore_from_v2(self):
  events,result=self.simulate(image='stock',before='candidate-v2')
  self.assertEqual(result['status'],'written_and_verified');self.assertIn('03-write-stock',events)
 def test_simulated_failed_stock_restore_rolls_back_to_v2(self):
  events,result=self.simulate(image='stock',before='candidate-v2',corrupt=True)
  self.assertEqual(result['status'],'failed_but_rollback_verified');self.assertEqual(result['restored_image'],'candidate-v2')
  self.assertIn('91-rollback-candidate-v2',events)
 def test_simulated_unknown_firmware_never_writes(self):
  events,result=self.simulate(unknown=True)
  self.assertFalse(any('write' in name or 'rollback' in name for name in events))
  self.assertIn('90-abort-reboot',events);self.assertEqual(result['status'],'failed')

if __name__=='__main__':unittest.main()
