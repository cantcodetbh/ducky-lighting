import sys,unittest,tempfile,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from firmware_hid import LoaderSession,Discovery,descriptor_valid,DESCRIPTOR,identity,pinned_image
from firmware_virtual import VirtualHID,verify
from firmware_ipc import SessionProcess
from firmware import Firmware,audit
import threading
class HIDFirmware(unittest.TestCase):
    def test_framing_full_images_and_failure_stop(self):
        r=verify();self.assertTrue(r['ok']);self.assertEqual(r['actual_USB_calls'],0);self.assertEqual(len(r['failure_cases']),9)
    def test_descriptor_semantics_and_unsafe_reports(self):
        self.assertTrue(descriptor_valid(DESCRIPTOR))
        self.assertTrue(descriptor_valid(DESCRIPTOR.replace(b'\x95\x40',b'\x96\x40\x00')))
        self.assertTrue(descriptor_valid(DESCRIPTOR.replace(b'\x81\x00',b'\x81\x02')))
        for descriptor in (b'',DESCRIPTOR[:-1],DESCRIPTOR+b'\x81\x00',DESCRIPTOR.replace(b'\x75\x08',b'\x75\x10'),DESCRIPTOR.replace(b'\x81\x00',b'\xb1\x00'),DESCRIPTOR[:6]+b'\x85\x01'+DESCRIPTOR[6:],DESCRIPTOR.replace(b'\x95\x40',b'\x95\x3f'),DESCRIPTOR.replace(b'\x06\x00\xff',b'\x06\x01\x00')):
            self.assertFalse(descriptor_valid(descriptor),descriptor.hex())
    def test_enumeration_read_only_and_reconnect_epoch(self):
        module=VirtualHID();stable=identity(module.entries[0]);d=Discovery([stable],module);first=d.status();self.assertTrue(first['requires_reconnect']);self.assertEqual(module.opens,0);self.assertEqual(module.writes,[])
        entry=module.entries[0];module.entries=[];self.assertIsNone(d.status());module.entries=[entry];second=d.status();self.assertFalse(second['requires_reconnect']);self.assertNotEqual(first['device_id'],second['device_id'])
    def test_ambiguity_wrong_identity_and_descriptor_send_nothing(self):
        for fault in ('ambiguous','identity','descriptor'):
            m=VirtualHID();device_id=identity(m.entries[0])
            if fault=='ambiguous':m.entries*=2
            if fault=='identity':device_id='wrong'
            if fault=='descriptor':m.descriptor=b'bad'
            with self.assertRaises(ValueError):LoaderSession(device_id,m)
            self.assertEqual(m.writes,[])
    def test_same_path_replug_cannot_redirect_checked_handle(self):
        module=VirtualHID();session=LoaderSession(identity(module.entries[0]),module);session.execute(bytes(131072),True);module.generation+=1
        with self.assertRaises(OSError):session.execute(bytes(131072))
        self.assertEqual(module.opens,1);self.assertFalse(module.flash);session.close()
    def test_arbitrary_image_file_is_rejected(self):
        with tempfile.NamedTemporaryFile() as file:
            file.write(b'not firmware');file.flush()
            with self.assertRaises(ValueError):pinned_image(file.name,'candidate')
            with self.assertRaises(ValueError):pinned_image(file.name,'arbitrary')
    def test_real_subprocess_held_session_and_parent_transcript_audit(self):
        command=[sys.executable,str(ROOT/'tests/fw_worker_fixture.py')]
        for name,length in [('candidate',131072),('restore',63848)]:
            with patch('firmware_ipc.worker_command',return_value=command):
                process=SessionProcess(identity(VirtualHID().entries[0]))
                try:
                    audit(process.inspect(),bytes(131072),True)
                    events=list(process.program(name,'ignored-test-path'));audit(events,bytes(i%251 for i in range(length)))
                finally:process.close()
    def test_windows_linux_coordinator_uses_held_worker_and_persisted_guards(self):
        for platform in ('win32','linux'):
            with tempfile.TemporaryDirectory() as folder,patch('firmware_ipc.worker_command',return_value=[sys.executable,str(ROOT/'tests/fw_worker_fixture.py')]):
                hardware=type('Hardware',(),{'lock':threading.Lock()})();fw=Firmware(hardware,folder,platform=platform);fw.available=lambda:True
                module=VirtualHID();fw.discovery=Discovery(module=module);fw.images=lambda:{name:bytes(i%251 for i in range(n)) for name,n in [('candidate',131072),('restore',63848)]}
                loader=fw.loader();plan=fw.inspect({'device_id':loader['device_id'],'model':'DKME2061ST','consent':True})
                fw.flash({'device_id':loader['device_id'],'plan_nonce':plan['plan_nonce'],'model':'DKME2061ST','consent':True,'accept_risk':True,'confirmation':'FLASH DKME2061ST','image':'candidate'})
                for _ in range(200):
                    if not fw.busy:break
                    time.sleep(.01)
                self.assertFalse(fw.busy);self.assertEqual(fw.job['state'],'acknowledged');self.assertFalse(hardware.lock.locked())
                self.assertTrue(fw.loader()['requires_reconnect'])
                restarted=Firmware(hardware,folder,platform=platform);self.assertIn(identity(module.entries[0]),restarted.discovery.blocked)
if __name__=='__main__':unittest.main()
