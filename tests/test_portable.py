import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from hid_transport import PortableHID,DESC
class FakeHID:
    def __init__(self):
        self.entries=[{'vendor_id':0x3233,'product_id':0x6301,'release_number':0x9002,'usage_page':0xff00,'usage':1,'interface_number':0,'path':b'only-test-path'}]
        self.opens=0;self.writes=[];self.gets=0;self.descriptor=DESC;self.active=0;self.result=0;self.fail_set=0;self.bad_status=False
    def enumerate(self,*_):return self.entries
    def device(self):return self
    def open_path(self,path):self.opens+=1
    def close(self):pass
    def get_report_descriptor(self):return self.descriptor
    def get_feature_report(self,number,length):
        assert(number,length)==(0,9);self.gets+=1
        return b'bad' if self.bad_status else b'\0DRGB\x01'+bytes([self.active,self.result,0])
    def send_feature_report(self,b):
        self.writes.append(bytes(b));self.active=b[2]!=3;self.result=1
        return -1 if len(self.writes)==self.fail_set else len(b)
class Portable(unittest.TestCase):
    def setUp(self):self.lib=FakeHID();self.transport=PortableHID(self.lib);self.identity=self.transport.identity(self.lib.entries[0])
    def test_enumerate_status_no_device_open_or_reports(self):
        self.assertTrue(self.transport.status()['rgb_control']);self.assertEqual((self.lib.opens,self.lib.gets,self.lib.writes),(0,0,[]))
    def test_exact_typed_9byte_feature_framing(self):
        result=self.transport.command('pixels',[(4,5,[102,156,53]),(4,3,[102,156,53])],self.identity)
        self.assertTrue(result['ok']);self.assertEqual(result['accepted_count'],2)
        self.assertEqual(self.lib.writes,[bytes.fromhex('00d1010405669c3500'),bytes.fromhex('00d1010403669c3500')])
    def test_stock_and_wrong_descriptor_and_bad_handshake_write_nothing(self):
        self.lib.entries[0]['release_number']=0;self.assertFalse(self.transport.command('release',None,self.identity)['ok']);self.assertEqual(self.lib.opens,0)
        self.lib.entries[0]['release_number']=0x9002;self.lib.descriptor=b'wrong';self.assertFalse(self.transport.command('release',None,self.identity)['ok']);self.assertEqual(self.lib.gets,0)
        self.lib.descriptor=DESC;self.lib.bad_status=True;self.assertFalse(self.transport.command('release',None,self.identity)['ok']);self.assertEqual(self.lib.gets,3);self.assertEqual(self.lib.writes,[])
    def test_bounds_duplicates_ambiguity_and_generic_command_rejected(self):
        for action,payload in [('flash',None),('pixels',[(5,0,[1,2,3])]),('pixels',[(0,0,[256,2,3])]),('pixels',[(0,0,[1,2,3])]*2)]:
            self.assertFalse(self.transport.command(action,payload,self.identity)['ok'])
        self.assertEqual(self.lib.opens,0);self.lib.entries.append({**self.lib.entries[0],'path':b'second'})
        self.assertFalse(self.transport.command('release',None,self.identity)['ok']);self.assertEqual(self.lib.opens,0)
    def test_partial_failure_no_write_retry(self):
        self.lib.fail_set=2;r=self.transport.command('pixels',[(0,i,[1,2,3]) for i in range(4)],self.identity)
        self.assertFalse(r['ok']);self.assertTrue(r['unknown']);self.assertEqual(len(self.lib.writes),2)
if __name__=='__main__':unittest.main()
