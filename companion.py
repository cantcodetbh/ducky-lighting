"""Self-contained desktop companion: starts loopback editor; explicit fixed-image firmware setup."""
from pathlib import Path
import argparse,base64,json,logging,os,socket,sys,threading,urllib.request,urllib.parse,webbrowser
sys.path.insert(0,str(Path(__file__).resolve().parent/'backend'))
from runtime import ROOT,data_root,VERSION
from server import Application,handler,ThreadingHTTPServer,valid_scene

def handoff(value):
    if not value:return ''
    if len(value)>20000:raise ValueError('Lighting handoff is too large.')
    parsed=urllib.parse.urlsplit(value)
    if parsed.scheme!='ducky-lighting' or parsed.netloc!='open' or parsed.path not in ('','/'):raise ValueError('Unrecognized Ducky Lighting link.')
    query=urllib.parse.parse_qs(parsed.query,strict_parsing=True)
    if not query:return ''
    if set(query)!={'scene'} or len(query['scene'])!=1:raise ValueError('Invalid lighting handoff.')
    encoded=query['scene'][0]
    if len(encoded)>16000:raise ValueError('Lighting scene is too large.')
    scene=json.loads(base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4)))
    if not valid_scene(scene):raise ValueError('Invalid lighting scene. No device action was taken.')
    # Fragment stays in the browser. It imports a preview, never executes RGB.
    return '#scene='+urllib.parse.quote(encoded,safe='')

def open_editor(url):
    import subprocess
    if sys.platform=='darwin':subprocess.Popen(['/usr/bin/open',url])
    elif sys.platform.startswith('linux'):
        env=os.environ.copy()
        if 'LD_LIBRARY_PATH_ORIG' in env:env['LD_LIBRARY_PATH']=env['LD_LIBRARY_PATH_ORIG']
        else:env.pop('LD_LIBRARY_PATH',None)
        subprocess.Popen(['xdg-open',url],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    else:webbrowser.open(url)

def main():
    if '--hid-worker' in sys.argv:
        from portable_worker import main as worker
        return worker()
    parser=argparse.ArgumentParser();parser.add_argument('link',nargs='?');parser.add_argument('--self-test',action='store_true');parser.add_argument('--no-open',action='store_true');parser.add_argument('--port',type=int,default=8770);args=parser.parse_args()
    fragment=handoff(args.link)
    if args.self_test:
        class NoUSB:
            def status(self):return {'ok':True,'mode':'demo','connected':False,'capabilities':{'rgb':False,'effects':False}}
        app=Application(hardware=NoUSB(),firmware_platform="test");server=ThreadingHTTPServer(('127.0.0.1',0),handler(app));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_port}'
        try:
            status=json.load(urllib.request.urlopen(base+'/api/status'));policy=json.load(urllib.request.urlopen(base+'/api/firmware'));page=urllib.request.urlopen(base).read()
            assert status['mode']=='demo' and policy['flashing_enabled'] is False and policy['writer_present'] is False and b'Ducky Lighting' in page
            print(json.dumps({'ok':True,'version':VERSION,'frozen':bool(getattr(sys,'frozen',False)),'static_assets':True,'firmware_writer_present':(ROOT/'build/ducky-firmware').is_file(),'USB_calls':0}))
        finally:server.shutdown();server.server_close();thread.join()
        return 0
    state=data_root();state.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=state/'companion.log',level=logging.INFO,format='%(asctime)s %(message)s')
    try:
        application=Application();server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(application));server.ducky_firmware=application.firmware
    except OSError:
        # Only reuse a service that identifies the expected companion protocol.
        try:
            status=json.load(urllib.request.urlopen(f'http://127.0.0.1:{args.port}/api/status',timeout=2))
            if status.get('companion_version')!=VERSION:raise RuntimeError('Port is used by another or older service. Close it before opening Ducky Lighting.')
        except Exception:raise RuntimeError('Unable to start the local companion. Port 8770 is occupied.')
        if not args.no_open:open_editor(f'http://127.0.0.1:{args.port}/'+fragment)
        return 0
    # Only the process that owns this server can expose a shutdown action.
    server.ducky_shutdown=lambda:threading.Thread(target=server.shutdown,daemon=True).start()
    if not args.no_open:threading.Timer(.25,lambda:open_editor(f'http://127.0.0.1:{server.server_port}/'+fragment)).start()
    logging.info('Companion started; firmware requires explicit browser confirmation.')
    import signal
    def terminate(signum,frame):
        if server.RequestHandlerClass and getattr(server,'ducky_firmware',None) and server.ducky_firmware.busy:
            logging.warning('Quit deferred while firmware is running.');return
        threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,terminate)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        if sys.platform=='win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,str(error),'Ducky Lighting could not start',0x10)
        elif sys.platform=='darwin' and getattr(sys,'frozen',False):
            import subprocess
            # Use argv, not interpolated AppleScript; no user data enters code.
            subprocess.run(['/usr/bin/osascript','-e','on run argv\ndisplay alert "Ducky Lighting could not start" message (item 1 of argv)\nend run',str(error)])
        else:print(str(error),file=sys.stderr)
        raise SystemExit(1)
