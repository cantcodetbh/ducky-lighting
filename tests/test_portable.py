import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from hid_transport import PortableHID,DESC,TransportError
class FakeHID:
    def __init__(self):
        self.entries=[{'vendor_id':0x3233,'product_id':0x6301,'release_number':0x9002,'usage_page':0xff00,'usage':1,'interface_number':0,'path':b'only-test-path'}]
        self.opens=0;self.writes=[];self.gets=0;self.descriptor=DESC;self.active=0;self.result=0;self.fail_set=0;self.bad_status=False;self.wire=1;self.saved=0
    def enumerate(self,*_):return self.entries
    def device(self):return self
    def open_path(self,path):self.opens+=1
    def close(self):pass
    def get_report_descriptor(self):return self.descriptor
    def get_feature_report(self,number,length):
        assert(number,length)==(0,9);self.gets+=1
        return b'bad' if self.bad_status else b'\0DRGB'+bytes([self.wire,self.active,self.result,self.saved<<1])
    def send_feature_report(self,b):
        self.writes.append(bytes(b));self.active=b[2] not in (3,5);
        if b[2]==4:self.saved=1
        if b[2]==5:self.saved=0
        self.result=1
        return -1 if len(self.writes)==self.fail_set else len(b)
class Portable(unittest.TestCase):
    def setUp(self):self.lib=FakeHID();self.transport=PortableHID(self.lib);self.identity=self.transport.identity(self.lib.entries[0])
    def test_enumerate_status_no_device_open_or_reports(self):
        self.assertTrue(self.transport.status()['rgb_control']);self.assertEqual((self.lib.opens,self.lib.gets,self.lib.writes),(0,0,[]))
    def test_exact_typed_9byte_feature_framing(self):
        result=self.transport.command('pixels',[(4,5,[102,156,53]),(4,3,[102,156,53])],self.identity)
        self.assertTrue(result['ok']);self.assertEqual(result['accepted_count'],2)
        self.assertEqual(self.lib.writes,[bytes.fromhex('00d1010405669c3500'),bytes.fromhex('00d1010403669c3500')])
    def test_windows_vendor_collection_descriptor_and_wrong_feature_size(self):
        self.lib.descriptor=DESC[64:];self.assertTrue(self.transport.command('release',None,self.identity)['ok'])
        self.lib.writes.clear();self.lib.descriptor=DESC[64:].replace(b'\x95\x08',b'\x95\x09')
        self.assertFalse(self.transport.command('release',None,self.identity)['ok']);self.assertEqual(self.lib.writes,[])
        self.lib.descriptor=DESC[64:];self.lib.entries[0]['usage_page']=1;self.lib.entries[0]['usage']=6
        self.assertFalse(self.transport.command('release',None,self.identity)['ok']);self.assertEqual(self.lib.writes,[])
    def test_onboard_save_gates_and_acknowledgement(self):
        payload=[(r,c,[12,34,56]) for r in range(5) for c in range(14)]
        r=self.transport.command('save',payload,self.identity);self.assertFalse(r['ok']);self.assertEqual(self.lib.opens,0);self.assertEqual(self.lib.writes,[])
        self.lib.entries[0]['release_number']=0x9003;self.identity=self.transport.identity(self.lib.entries[0])
        r=self.transport.command('save',payload,self.identity);self.assertFalse(r['ok']);self.assertEqual(self.lib.writes,[])
        self.lib.wire=2;r=self.transport.command('save',payload,self.identity);self.assertTrue(r['ok']);self.assertTrue(r['onboard_saved']);self.assertEqual(r['accepted_count'],71);self.assertEqual(self.lib.writes[-1],bytes.fromhex('00d104000000000000'))
        r=self.transport.command('clear-onboard',None,self.identity);self.assertTrue(r['ok']);self.assertFalse(r['onboard_saved'])
        with self.assertRaises(TransportError):self.transport.operations('save',payload[:-1])
    def test_stock_and_wrong_descriptor_and_bad_handshake_write_nothing(self):
        self.lib.entries[0]['release_number']=0;self.assertFalse(self.transport.command('release',None,self.identity)['ok']);self.assertEqual(self.lib.opens,0)
        self.lib.entries[0]['release_number']=0x9002;self.lib.descriptor=b'wrong';self.assertFalse(self.transport.command('release',None,self.identity)['ok']);self.assertEqual(self.lib.gets,0)
        self.lib.descriptor=DESC;self.lib.bad_status=True;self.assertFalse(self.transport.command('release',None,self.identity)['ok']);self.assertEqual(self.lib.gets,3);self.assertEqual(self.lib.writes,[])
    def test_bounds_duplicates_ambiguity_and_generic_command_rejected(self):
        for action,payload in [('flash',None),('pixels',[(5,0,[1,2,3])]),('pixels',[(0,0,[256,2,3])]),('pixels',[(0,0,[1,2,3])]*2)]:
            self.assertFalse(self.transport.command(action,payload,self.identity)['ok'])
        self.assertEqual(self.lib.opens,0);self.lib.entries.append({**self.lib.entries[0],'path':b'second'})
        self.assertFalse(self.transport.command('release',None,self.identity)['ok']);self.assertEqual(self.lib.opens,0)
    def test_native_effect_revision_handshake_and_bounds(self):
        for revision in (0x9002,0x9003):
            self.lib.entries[0]['release_number']=revision;identity=self.transport.identity(self.lib.entries[0])
            self.assertFalse(self.transport.command('effect',[6,5,255,0,0],identity)['ok']);self.assertEqual(self.lib.opens,0)
        self.lib.entries[0]['release_number']=0x9004;identity=self.transport.identity(self.lib.entries[0])
        self.assertFalse(self.transport.command('effect',[6,5,255,0,0],identity)['ok']);self.assertEqual(self.lib.writes,[])
        self.lib.wire=2;self.assertTrue(self.transport.command('effect',[6,5,255,0,0],identity)['ok'])
        self.assertEqual(self.lib.writes,[bytes.fromhex('00d1060605ff000000')]);self.assertTrue(self.transport.status()['effects'])
        for payload in ([2,5,1,2,3],[6,0,1,2,3],[6,11,1,2,3],[6,5,256,2,3]):
            with self.assertRaises(TransportError):self.transport.operations('effect',payload)
    def test_partial_failure_no_write_retry(self):
        self.lib.fail_set=2;r=self.transport.command('pixels',[(0,i,[1,2,3]) for i in range(4)],self.identity)
        self.assertFalse(r['ok']);self.assertTrue(r['unknown']);self.assertEqual(len(self.lib.writes),2)
if __name__=='__main__':unittest.main()
