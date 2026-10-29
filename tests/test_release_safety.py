import sys,unittest,json,base64,tempfile,threading,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'backend'),str(ROOT)]
from firmware import Firmware,construct_images,request,audit,NATIVE
from companion import handoff
class Hardware:
    def __init__(self):self.lock=threading.Lock()
class VirtualLoader:
    def __init__(self):self.calls=[];self.device={'device_id':'123','location':1048576};self.fail=None;self.images={'candidate':bytes((i*131+17)%256 for i in range(65000)),'restore':bytes((i*137+23)%256 for i in range(63848))}
    def __call__(self,args):
        self.calls.append(args)
        if args[0]=='--devices':return [{'loader':self.device}]
        inspect=args[0]=='--inspect';image=self.images['restore' if 'restore' in args[0] else 'candidate'];events=[];total=3 if inspect else 4+(len(image)-48+55)//56
        for i in range(total):
            b=request(image,i);r=bytearray(64);r[:2]=(sum(b)&65535).to_bytes(2,'little');r[4:8]=(2*i+2).to_bytes(4,'little')
            if i==1:r[8:12]=bytes.fromhex('102e1301')
            if i==2:r[8:24]=bytes.fromhex('7dfbffffffff0f005affffffffffffff')
            if self.fail==i:r[0]^=1
            events.extend([{'event':'submitting','body_hex':b.hex()},{'event':'received','body_hex':r.hex()}])
        events.append({'event':'program_result','ok':True,'submitted':total,'acknowledged':total,'bytes_acknowledged':0 if inspect else len(image)})
        return events
class Safety(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.runner=VirtualLoader();self.hw=Hardware();self.fw=Firmware(self.hw,self.tmp.name,self.runner,'darwin');self.fw.images=lambda:self.runner.images
    def tearDown(self):self.tmp.cleanup()
    def check(self):return self.fw.inspect({'device_id':'123','model':'DKME2061ST','consent':True})
    def body(self,plan):return {'plan_nonce':plan['plan_nonce'],'device_id':'123','image':'candidate','model':'DKME2061ST','confirmation':'FLASH DKME2061ST','accept_risk':True,'consent':True}
    def wait(self):
        for _ in range(100):
            if not self.fw.busy:return
            time.sleep(.01)
        self.fail('Virtual programmer failed to finish')
    def test_policy_only_enumerates_and_unsupported_platform_cannot_flash(self):
        p=self.fw.policy({'capabilities':{}});self.assertTrue(p['flashing_enabled']);self.assertEqual(self.runner.calls,[['--devices']])
        self.fw.platform='win32';self.assertFalse(self.fw.policy({})['flashing_enabled'])
        with self.assertRaises(ValueError):self.check()
    def test_exact_image_extraction_and_no_arbitrary_file(self):
        for data in (b'MZ',bytes(3307520)):
            with self.assertRaises(ValueError):construct_images(data)
        with self.assertRaises(ValueError):self.fw.prepare({'updater_base64':'invalid!'})
        self.assertEqual(self.runner.calls,[])
    def test_check_only_queries_and_negative_reply_never_arms_flash(self):
        plan=self.check();self.assertTrue(plan['configuration_verified']);self.assertFalse(any(a[0].startswith('--program') for a in self.runner.calls))
        self.runner.fail=1
        with self.assertRaises(ValueError):self.check()
        # A failed fresh check must invalidate a previous authorization.
        self.assertIsNone(self.fw.plan)
    def test_expired_plan_changed_device_and_confirmations_fail_closed(self):
        plan=self.check();body=self.body(plan)
        for key,value in [('confirmation','yes'),('accept_risk',False),('model','DKON2061ST'),('plan_nonce','bad'),('image','arbitrary')]:
            b={**body,key:value}
            with self.assertRaises(ValueError):self.fw.flash(b)
        self.fw.plan['expires']=0
        with self.assertRaises(ValueError):self.fw.flash(body)
        plan=self.check();self.runner.device={'device_id':'456','location':1048576}
        with self.assertRaises(ValueError):self.fw.flash(self.body(plan))
        self.assertFalse(any(a[0].startswith('--program') for a in self.runner.calls))
    def test_virtual_programming_acknowledged_not_claimed_readback_and_no_replay(self):
        result=self.fw.flash(self.body(self.check()));self.assertTrue(result['ok']);self.wait();self.assertEqual(self.fw.job['state'],'acknowledged');self.assertIn('not full flash readback',self.fw.job['message'])
        self.assertFalse(self.hw.lock.locked());self.assertEqual(sum(a[0].startswith('--program') for a in self.runner.calls),1)
        with self.assertRaises(ValueError):self.check()
    def test_partial_failure_stops_and_fresh_connection_required(self):
        plan=self.check();self.runner.fail=30;self.fw.flash(self.body(plan));self.wait();self.assertEqual(self.fw.job['state'],'failed')
        with self.assertRaises(ValueError):self.check()
        self.assertEqual(sum(a[0].startswith('--program') for a in self.runner.calls),1)
    def test_restart_retains_connection_replay_guard_and_marks_interruption_unknown(self):
        self.fw.flash(self.body(self.check()));self.wait()
        restarted=Firmware(self.hw,self.tmp.name,self.runner,'darwin');self.assertIn('123',restarted.spent)
        path=next(Path(self.tmp.name).glob('attempt-*.json'));data=json.loads(path.read_text());data['job']['state']='programming';path.write_text(json.dumps(data))
        interrupted=Firmware(self.hw,self.tmp.name,self.runner,'darwin');self.assertEqual(interrupted.job['state'],'failed');self.assertIn('unknown',interrupted.job['message'])
    def test_official_download_uses_only_pinned_https_url_and_rejects_untrusted_bytes(self):
        from unittest.mock import patch
        import io
        with patch('urllib.request.urlopen',return_value=io.BytesIO(b'not firmware')) as network:
            with self.assertRaises(ValueError):self.fw.prepare({'download_official':True})
            self.assertIn('cdn.shopify.com',network.call_args.args[0]);self.assertIn('context',network.call_args.kwargs)
        with self.assertRaises(ValueError):self.fw.prepare({'download_official':True,'url':'https://evil.invalid'})
        self.assertEqual(self.runner.calls,[])
    def test_no_generic_commands_via_native_cli(self):
        if not NATIVE.exists():self.skipTest('Native macOS helper is not built')
        for args in (['--command','0xa3'],['--program-candidate','123','1048576',str(ROOT/'package.json')],['--inspect','-1','1048576']):
            self.assertEqual(subprocess.run([str(NATIVE),*args],capture_output=True).returncode,2)
    def test_handoff_only_carries_preview(self):
        scene={'model':'black','layout':'iso','effect':'Static','color':'#ff0000','brightness':80,'speed':5,'paints':{}}
        encoded=base64.urlsafe_b64encode(json.dumps(scene).encode()).decode().rstrip('=');self.assertTrue(handoff('ducky-lighting://open?scene='+encoded).startswith('#scene='))
        for url in ['ducky-lighting://flash?image=123','ducky-lighting://open?command=flash']:
            with self.assertRaises(ValueError):handoff(url)
if __name__=='__main__':unittest.main()
