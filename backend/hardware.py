"""Typed custom9002/9003 RGB adapter. Enumeration is read-only; never flashes firmware."""
from pathlib import Path
import json,plistlib,subprocess,sys,time,threading
from runtime import ROOT
from hid_transport import PortableHID
BINARY=ROOT/'build/ducky-rgb'
LAYOUTS=json.loads((ROOT/'src/data/layouts.json').read_text())
class Hardware:
    def __init__(self):self.lock=threading.Lock();self.cached=None;self.checked=0;self.last=None;self.portable=PortableHID()
    def invoke(self,args):
        try:
            p=subprocess.run([str(BINARY),*args],capture_output=True,text=True,timeout=10)
            result=json.loads(p.stdout)
            if p.returncode:result['ok']=False
            return result
        except subprocess.TimeoutExpired:return {'ok':False,'error':'USB command timed out. The last colour may have applied; reconnect and check before applying again.','unknown':True}
        except (OSError,ValueError):return {'ok':False,'error':'The native RGB helper is unavailable. Rebuild with ./launch.sh.'}
    def usb_devices(self):
        if sys.platform!='darwin':return [{'name':d.get('product_string','Ducky Mecha Mini'),'firmware':str(d.get('release_number','unknown'))} for d in self.portable.enumerate()]
        try:
            raw=subprocess.run(['/usr/sbin/ioreg','-a','-r','-c','IOUSBHostDevice'],capture_output=True,check=True,timeout=4).stdout
            found=[]
            def walk(nodes):
                for n in nodes:
                    if n.get('idVendor')==0x3233 and n.get('idProduct')==0x6301:found.append({'name':n.get('USB Product Name','Ducky One2 Mini RGB'),'firmware':str(n.get('bcdDevice','unknown'))})
                    walk(n.get('IORegistryEntryChildren',[]))
            walk(plistlib.loads(raw));return found
        except (OSError,ValueError,subprocess.SubprocessError):return []
    def status(self,force=False):
        if not force and self.cached is not None and time.monotonic()-self.checked<1:return dict(self.cached)
        native=self.invoke(['--status']) if sys.platform=='darwin' and BINARY.exists() else self.portable.status()
        devices=self.usb_devices() if not native.get('connected') else []
        available=native.get('ok') and native.get('connected') and native.get('rgb_control')
        detected=bool(available or devices)
        result={'ok':True,'mode':'available' if available else 'detected' if detected else 'demo','connected':detected,
          'name':'Ducky Mecha Mini','vid':'0x3233','pid':'0x6301','device_id':native.get('device_id') if available else None,
          'firmware':('custom9004' if native.get('effects') else 'custom9003' if native.get('onboard_profiles') else 'custom9002') if available else devices[0]['firmware'] if devices else None,
          'detail':('Native effects and onboard static colours supported.' if native.get('effects') else 'Custom9003 connected; onboard colours supported.' if native.get('onboard_profiles') else 'Verified macOS custom9002 adapter connected.' if sys.platform=='darwin' else 'Custom9002 detected. This platform transport still needs physical validation; every command checks its exact descriptor.') if available else '3233:6301 detected. RGB protocol is not verified for this firmware.' if detected else 'No Mecha Mini attached. The editor and profiles work locally.',
          'capabilities':{'rgb':bool(available),'effects':bool(available and native.get('effects')),'onboard_profiles':bool(available and native.get('onboard_profiles'))},'last_command':self.last}
        self.cached=result;self.checked=time.monotonic();return dict(result)
    def apply(self,layout,colours,device_id):
        pixels={}
        for key in LAYOUTS[layout]['keys']:
            rgb=colours[key['id']]
            for row,col in key.get('leds',[[key['row'],key['column']]]):pixels[row,col]=rgb
        packed=''.join(f'{r:02x}{c:02x}'+v[1:] for (r,c),v in pixels.items())
        return self.command(['--batch',packed],device_id,len(pixels))
    def save_onboard(self,layout,colours,device_id):
        pixels={(row,col):'#000000' for row in range(5) for col in range(14)}
        for key in LAYOUTS[layout]['keys']:
            for row,col in key.get('leds',[[key['row'],key['column']]]):pixels[row,col]=colours[key['id']]
        packed=''.join(f'{row:02x}{col:02x}'+rgb[1:] for (row,col),rgb in pixels.items())
        return self.command(['--save-batch',packed],device_id,71)
    def clear_onboard(self,device_id):return self.command(['--clear-onboard'],device_id,1)
    def effect(self,name,speed,rgb,device_id):
        mode={'Wave':1,'Ripple':4,'Reactive':6,'Breathing':8}[name]
        return self.command(['--effect',str(mode),str(speed),*[str(v) for v in rgb]],device_id,1)
    def release(self,device_id):return self.command(['--release'],device_id,1)
    def command(self,args,device_id,count):
        if not self.lock.acquire(False):return {'ok':False,'error':'Another keyboard command is finishing. Try again shortly.'}
        try:
            status=self.status(force=True)
            if status['mode']!='available' or status['device_id']!=device_id:return {'ok':False,'error':'The verified keyboard is disconnected or has changed. Refresh the connection first.'}
            if args[0]=='--effect' and not status.get('capabilities',{}).get('effects'):return {'ok':False,'error':'Native animations require custom9004 firmware. No command sent.'}
            if args[0] in ('--save-batch','--clear-onboard') and not status.get('capabilities',{}).get('onboard_profiles'):return {'ok':False,'error':'Onboard saving requires custom9003 firmware. No command sent.'}
            if sys.platform=='darwin' and BINARY.exists():result=self.invoke(['--device',device_id,*args])
            else:
                if args[0]=='--effect':result=self.portable_command('effect',[int(v) for v in args[1:]],device_id)
                elif args[0]=='--clear-onboard':result=self.portable_command('clear-onboard',None,device_id)
                elif args[0]=='--release':result=self.portable_command('release',None,device_id)
                else:
                    packed=args[1];pixels=[(int(packed[i:i+2],16),int(packed[i+2:i+4],16),[int(packed[j:j+2],16) for j in (i+4,i+6,i+8)]) for i in range(0,len(packed),10)]
                    result=self.portable_command('save' if args[0]=='--save-batch' else 'pixels',pixels,device_id)
            if args[0] in ('--save-batch','--clear-onboard') and not result.get('ok'):
                result['error']='The onboard operation was not confirmed. The previous or new saved colours may remain. No automatic retry was sent.'
            self.last=result
            if result.get('ok') and result.get('accepted_count')!=count:result={'ok':False,'error':'The keyboard did not acknowledge the complete frame. No automatic retry was sent.','transport':result}
            return result
        finally:self.lock.release()
    def portable_command(self,action,payload,device_id):
        from runtime import FROZEN
        from firmware_ipc import worker_command
        command=[*worker_command(),'--rgb'] if FROZEN else [sys.executable,str(ROOT/'backend/portable_worker.py')]
        try:
            p=subprocess.run(command,input=json.dumps({'action':action,'payload':payload,'device_id':device_id}),capture_output=True,text=True,timeout=10)
            result=json.loads(p.stdout)
            if type(result.get('ok')) is not bool:raise ValueError()
            return result
        except subprocess.TimeoutExpired:return {'ok':False,'unknown':True,'error':'The device stopped responding. A last colour may have applied. No automatic retry was sent.'}
        except (OSError,ValueError):return {'ok':False,'unknown':True,'error':'The USB helper returned no valid result. No automatic retry was sent.'}
