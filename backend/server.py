#!/usr/bin/env python3
"""Single-origin, loopback-only local RGB service and production asset host."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import argparse,json,mimetypes,secrets,threading,os,re,sys
from urllib.parse import urlsplit,unquote
from hardware import Hardware,ROOT,LAYOUTS
from runtime import data_root,VERSION
from firmware import Firmware
MODELS={'black','llama','creator'};EFFECTS={'Static','Spectrum','Breathing','Wave','Reactive','Ripple'}
def valid_scene(s):
    if not isinstance(s,dict) or set(s)!={'model','layout','effect','color','brightness','speed','paints'}:return False
    if s['model'] not in MODELS or s['layout'] not in LAYOUTS or s['effect'] not in EFFECTS or not hex_colour(s['color']):return False
    for key,low,high in [('brightness',0,100),('speed',1,10)]:
        if type(s[key]) not in (int,float) or not low<=s[key]<=high:return False
    allowed={k['id'] for k in LAYOUTS[s['layout']]['keys']}
    return isinstance(s['paints'],dict) and all(k in allowed and hex_colour(v) for k,v in s['paints'].items())
def hex_colour(x):return isinstance(x,str) and bool(re.fullmatch('#[a-fA-F0-9]{6}',x))
def validate_profiles(profiles):
    if not isinstance(profiles,list) or len(profiles)>64:raise ValueError('Save up to 64 profiles.')
    seen=set()
    for p in profiles:
        if not isinstance(p,dict) or set(p)!={'id','name','scene'} or not isinstance(p['id'],str) or not re.fullmatch('[a-zA-Z0-9-]{1,80}',p['id']) or p['id'] in seen or not isinstance(p['name'],str) or not 1<=len(p['name'].strip())<=48 or not valid_scene(p['scene']):raise ValueError('Invalid lighting profile. Check its name, model, layout and colours.')
        seen.add(p['id'])
    return profiles
class Application:
    def __init__(self,data_dir=None,hardware=None,firmware_platform=None):
        self.hardware=hardware or Hardware();self.token=secrets.token_urlsafe(32);self.data=data_dir or data_root();self.profile_lock=threading.Lock();self.firmware=Firmware(self.hardware,self.data/"firmware",platform=firmware_platform)
    def profiles(self):
        try:return validate_profiles(json.loads((self.data/'profiles.json').read_text()))
        except FileNotFoundError:return []
    def save(self,profiles):
        validate_profiles(profiles)
        with self.profile_lock:
            self.data.mkdir(parents=True,exist_ok=True);path=self.data/'profiles.json'
            if path.exists():
                try:validate_profiles(json.loads(path.read_text()))
                except (ValueError,TypeError):path.rename(self.data/('profiles-preserved-'+secrets.token_hex(5)+'.json'))
            tmp=self.data/'profiles.tmp';tmp.write_text(json.dumps(profiles,indent=2)+'\n');os.replace(tmp,path)
    def mutate(self,path,b):
        if not isinstance(b,dict):raise ValueError('Expected a JSON object.')
        if path=='/api/firmware/prepare':return self.firmware.prepare(b)
        if path=='/api/firmware/inspect':return self.firmware.inspect(b)
        if path=='/api/firmware/flash':return self.firmware.flash(b)
        if path=='/api/profiles' and set(b)=={'profiles'}:self.save(b['profiles']);return {'ok':True}
        if b.get('consent') is not True:raise ValueError('Use Apply to keyboard to send a lighting command.')
        if not isinstance(b.get('device_id'),str) or not re.fullmatch('[0-9]{1,24}',b['device_id']):raise ValueError('Refresh the device connection before applying.')
        if path=='/api/release' and set(b)=={'device_id','consent'}:return self.hardware.release(b['device_id'])
        if path=='/api/lighting' and set(b)=={'layout','colours','device_id','consent'}:
            layout=b['layout'];colours=b['colours']
            if layout not in LAYOUTS or not isinstance(colours,dict) or set(colours)!={k['id'] for k in LAYOUTS[layout]['keys']} or not all(hex_colour(v) for v in colours.values()):raise ValueError('Send exactly one complete, valid keyboard frame.')
            return self.hardware.apply(layout,colours,b['device_id'])
        raise ValueError('Unknown lighting operation.')
def handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version='DuckyLighting/1';protocol_version='HTTP/1.1'
        def log_message(self,*args):pass
        def reply(self,status,body,kind='application/json'):
            data=json.dumps(body).encode() if kind=='application/json' else body
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");self.send_header('Connection','close');self.end_headers();self.wfile.write(data);self.close_connection=True
        def guard(self,write=False):
            ports={str(self.server.server_port),'5178'};hosts={'127.0.0.1:'+p for p in ports}
            if self.headers.get('Host') not in hosts:return False
            origin=self.headers.get('Origin')
            if origin and origin not in {'http://'+h for h in hosts}:return False
            if write and (not origin or self.headers.get('X-Ducky-Token')!=app.token or self.headers.get('Content-Type','').split(';')[0]!='application/json'):return False
            return True
        def do_GET(self):
            if not self.guard():return self.reply(403,{'ok':False,'error':'Use the local Ducky Lighting website.'})
            path=urlsplit(self.path).path
            if path=='/api/status':return self.reply(200,{**app.hardware.status(),'token':app.token,'companion_version':VERSION,'can_quit':hasattr(self.server,'ducky_shutdown'),'firmware_busy':app.firmware.busy})
            if path=='/api/firmware':return self.reply(200,app.firmware.policy(app.hardware.status()))
            if path=='/api/capabilities':return self.reply(200,{'ok':True,**app.hardware.status()['capabilities'],'adapter':'custom9002-only','stock_rgb_verified':False,'frame_readback':False,'animation_streaming':False})
            if path=='/api/profiles':
                try:return self.reply(200,{'ok':True,'profiles':app.profiles()})
                except (ValueError,TypeError):return self.reply(500,{'ok':False,'error':'The saved profile file is invalid. It has been preserved; export your browser profiles before saving.'})
            if path.startswith('/api/'):return self.reply(404,{'ok':False,'error':'Unknown endpoint.'})
            root=ROOT/'dist';file=(root/unquote(path).lstrip('/')).resolve()
            if not file.is_relative_to(root.resolve()):return self.reply(403,{'ok':False,'error':'Invalid asset path.'})
            if path=='/':file=root/'index.html'
            if not file.is_file():return self.reply(404,{'ok':False,'error':'Asset not found. Run npm run build first.'})
            return self.reply(200,file.read_bytes(),mimetypes.guess_type(file)[0] or 'application/octet-stream')
        def do_POST(self):
            if not self.guard(True):return self.reply(403,{'ok':False,'error':'Lighting requests require the local website and its session token.'})
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=(4600000 if urlsplit(self.path).path=='/api/firmware/prepare' else 262144):raise ValueError('Choose a smaller JSON profile or complete lighting frame.')
                body=json.loads(self.rfile.read(n))
                if urlsplit(self.path).path=='/api/companion/quit' and body=={'consent':True} and hasattr(self.server,'ducky_shutdown'):

                    if app.firmware.busy:return self.reply(409,{'ok':False,'error':'Firmware programming is still running. Keep the companion open.'})
                    self.reply(200,{'ok':True});self.server.ducky_shutdown();return
                result=app.mutate(urlsplit(self.path).path,body)
                return self.reply(200 if result.get('ok') else 409,result)
            except (ValueError,TypeError,KeyError):return self.reply(400,{'ok':False,'error':'Invalid request. Check the profile, layout and colour values.'})
            except OSError:return self.reply(500,{'ok':False,'error':'Unable to save locally. Check available disk space and export your profile.'})
    return Handler
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8770);args=p.parse_args()
    application=Application();server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(application));print(f'Ducky Lighting: http://127.0.0.1:{args.port}/',flush=True)
    import signal
    def terminate(signum,frame):
        if application.firmware.busy:return
        threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,terminate)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
