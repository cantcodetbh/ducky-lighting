import sys,json,tempfile,threading,http.client,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from server import Application,handler,ThreadingHTTPServer,LAYOUTS,validate_profiles
from hardware import Hardware
class FakeHardware:
    def __init__(self):self.writes=[];self.mode='demo';self.onboard=False
    def status(self):return {'ok':True,'mode':self.mode,'connected':self.mode!='demo','device_id':'123','detail':'RAM test','capabilities':{'rgb':self.mode=='available','effects':False,'onboard_profiles':self.onboard}}
    def apply(self,*args):
        if self.mode!='available':return {'ok':False,'error':'disconnected'}
        self.writes.append(args);return {'ok':True,'accepted_count':64}
    def save_onboard(self,*args):
        if not self.onboard:return {'ok':False,'error':'onboard firmware required'}
        self.writes.append(('save',args));return {'ok':True,'onboard_saved':True}
    def clear_onboard(self,*args):
        if not self.onboard:return {'ok':False,'error':'onboard firmware required'}
        self.writes.append(('clear',args));return {'ok':True,'onboard_saved':False}
    def effect(self,*args):self.writes.append(('effect',args));return {'ok':True,'accepted_count':1}
    def release(self,*args):self.writes.append(args);return {'ok':True}
class Backend(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.hw=FakeHardware();self.app=Application(Path(self.tmp.name),self.hw);self.server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.app));self.port=self.server.server_port;self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def request(self,path='/api/status',body=None,**headers):
        defaults={'Host':f'127.0.0.1:{self.port}','Origin':f'http://127.0.0.1:{self.port}','X-Ducky-Token':self.app.token,'Content-Type':'application/json'};defaults.update(headers)
        c=http.client.HTTPConnection('127.0.0.1',self.port);c.request('GET' if body is None else 'POST',path,None if body is None else json.dumps(body),defaults);r=c.getresponse();result=r.status,json.loads(r.read());c.close();return result
    def test_enumeration_never_writes_and_three_states(self):
        for mode in ['demo','detected','available']:
            self.hw.mode=mode;code,s=self.request();self.assertEqual(code,200);self.assertEqual(s['mode'],mode)
        self.request('/api/capabilities');self.assertEqual(self.hw.writes,[])
    def test_reject_cross_origin_token_host_and_generic_reports(self):
        for headers in [{'Origin':'https://evil.example'},{'Host':'evil.example'},{'X-Ducky-Token':'bad'}]:self.assertEqual(self.request('/api/release',{'consent':True,'device_id':'123'},**headers)[0],403)
        self.assertEqual(self.request('/api/lighting',{'bytes':'ff','consent':True})[0],400);self.assertEqual(self.hw.writes,[])
    def test_frame_validation_and_disconnect(self):
        body={'layout':'iso','colours':{k['id']:'#123456' for k in LAYOUTS['iso']['keys']},'device_id':'123','consent':True}
        self.assertEqual(self.request('/api/lighting',body)[0],409)
        self.hw.mode='available';self.assertEqual(self.request('/api/lighting',body)[0],200)
        body['colours']['9:9']='#ffffff';self.assertEqual(self.request('/api/lighting',body)[0],400);self.assertEqual(len(self.hw.writes),1)
    def test_onboard_api_separate_explicit_consent_and_no_9002_writes(self):
        body={'layout':'iso','colours':{k['id']:'#123456' for k in LAYOUTS['iso']['keys']},'device_id':'123','consent':True}
        self.assertEqual(self.request('/api/onboard/save',body)[0],409);self.assertEqual(self.hw.writes,[])
        self.hw.onboard=True
        self.assertEqual(self.request('/api/onboard/save',{**body,'consent':False})[0],400)
        self.assertEqual(self.request('/api/onboard/save',body,Origin='https://evil.example')[0],403)
        self.assertEqual(self.request('/api/onboard/save',body)[1]['onboard_saved'],True)
        self.assertEqual(self.request('/api/onboard/clear',{'device_id':'123','consent':True})[1]['onboard_saved'],False)
        hw=Hardware();calls=[];hw.command=lambda args,identity,count:calls.append((args,count)) or {'ok':True}
        hw.save_onboard('iso',body['colours'],'123');self.assertEqual(calls[0][1],71);self.assertEqual(len(calls[0][0][1]),700)
        for c in (3,5,7):self.assertIn(f'04{c:02x}123456',calls[0][0][1])
        hw=Hardware();hw.status=lambda force=False:{'mode':'available','device_id':'123','capabilities':{'onboard_profiles':False}}
        hw.invoke=lambda args:self.fail('9002 must not receive persistence commands');self.assertFalse(hw.clear_onboard('123')['ok'])
    def test_native_effect_api_validation_and_capability_gate(self):
        body={'effect':'Reactive','speed':5,'colour':'#ff0077','device_id':'123','consent':True}
        self.assertEqual(self.request('/api/effect',body)[0],200)
        self.assertEqual(self.hw.writes[-1],('effect',('Reactive',5,[255,0,119],'123')))
        for update in ({'effect':'flash'},{'speed':True},{'speed':11},{'colour':'red'},{'consent':False}):self.assertEqual(self.request('/api/effect',{**body,**update})[0],400)
        self.assertEqual(self.request('/api/effect',body,Origin='https://evil.example')[0],403)
        hw=Hardware();hw.status=lambda force=False:{'mode':'available','device_id':'123','capabilities':{'effects':False}}
        hw.invoke=lambda args:self.fail('9003 must not receive effect commands');self.assertFalse(hw.effect('Reactive',5,[255,0,0],'123')['ok'])
        calls=[];hw.status=lambda force=False:{'mode':'available','device_id':'123','capabilities':{'effects':True}}
        hw.invoke=lambda args:calls.append(args) or {'ok':True,'accepted_count':1}
        self.assertTrue(hw.effect('Ripple',7,[255,1,2],'123')['ok']);self.assertEqual(calls,[['--device','123','--effect','4','7','255','1','2']])
    def test_profile_persistence_and_invalid_file_preserved(self):
        scene={'model':'black','layout':'iso','effect':'Static','color':'#ff0000','brightness':80,'speed':5,'paints':{'4:5':'#123456'}};p={'id':'abc','name':'Evening','scene':scene}
        self.assertEqual(self.request('/api/profiles',{'profiles':[p]})[0],200)
        self.assertEqual(Application(Path(self.tmp.name),self.hw).profiles(),[p]);self.assertEqual(self.request('/api/profiles')[1]['profiles'],[p])
        (Path(self.tmp.name)/'profiles.json').write_text('broken');self.assertEqual(self.request('/api/profiles')[0],500)
        self.assertEqual(self.request('/api/profiles',{'profiles':[p]})[0],200);self.assertEqual(len(list(Path(self.tmp.name).glob('profiles-preserved-*'))),1)
        self.assertEqual(self.request('/api/profiles',{'profiles':[{**p,'name':''}]})[0],400)
    def test_space_fans_out_without_hardware_and_exact_epoch_guard(self):
        hw=Hardware();calls=[]
        hw.command=lambda args,identity,count:calls.append((args,identity,count)) or {'ok':True}
        for layout,total in [('ansi',63),('iso',64)]:
            hw.apply(layout,{k['id']:'#669c35' for k in LAYOUTS[layout]['keys']},'123');packed=calls[-1][0][1]
            self.assertEqual(calls[-1][2],total)
            for col in (3,5,7):self.assertIn(f'04{col:02x}669c35',packed)
        hw=Hardware();hw.status=lambda force=False:{'mode':'available','device_id':'999'};hw.invoke=lambda args:self.fail('Stale device must not receive commands')
        self.assertFalse(hw.command(['--release'],'123',1)['ok'])
if __name__=='__main__':unittest.main()
