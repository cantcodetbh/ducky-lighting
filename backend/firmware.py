"""Experimental, fixed-image macOS APROM update coordinator. No automatic programming."""
import base64,hashlib,json,secrets,subprocess,sys,threading,time,struct,os
from pathlib import Path
from runtime import ROOT,data_root,VERSION
OFFICIAL_URL='https://cdn.shopify.com/s/files/1/0728/4382/1295/files/Ducky_Mecha_Mini_RGB_V1.10_DKME2061ST.exe?v=1744792813'
UPDATER_SHA='6d5b1a8fb16c53fc2875dad5399cd574b1fc05eef83141dd89fbcee0ede5aab8'
STOCK_SHA='fb29585b17a0ee1883287def35a1b107695a13c4dc85355cb27f54921ea5f514'
RGB_SHA='d85ee17eeaf68e14d8634ab5d0a59f2ae551ea9aa3c6ded9451ba3fed13458fc'
NATIVE=ROOT/'build/ducky-firmware'
RISK='Experimental firmware. Only one DKME2061ST has been physically validated. Interrupted-flash recovery is unproven; a failed update may require hardware repair. Packet acknowledgements are not full flash readback.'

def digest(data):return hashlib.sha256(data).hexdigest()
def construct_images(updater):
    if len(updater)!=3307520 or digest(updater)!=UPDATER_SHA:raise ValueError('Choose the exact official DKME2061ST V1.10 updater. This file hash is not supported; nothing was executed or sent.')
    stock=updater[0x20f0b8:0x21ea20]
    if len(stock)!=63848 or digest(stock)!=STOCK_SHA or struct.unpack_from('<I',updater,0x21ea20)[0]!=63848:raise ValueError('Firmware extraction did not match the pinned image.')
    patch=json.loads((ROOT/'backend/firmware-patch.json').read_text());image=bytearray(stock+b'\xff'*(65000-len(stock)))
    allowed=set()
    for edit in patch['edits']:
        address=int(edit['address'],16);before=bytes.fromhex(edit['before']);after=bytes.fromhex(edit['after'])
        if stock[address:address+len(before)]!=before or len(after)!=len(before):raise ValueError('Patch anchor mismatch.')
        image[address:address+len(after)]=after;allowed.update(range(address,address+len(after)))
    for segment in patch['segments']:
        address=segment['address'];data=bytes.fromhex(segment['hex'])
        if address<len(stock) or address+len(data)>65000:raise ValueError('Patch lies outside its fixed append area.')
        image[address:address+len(data)]=data
    if image[:0xc0]!=stock[:0xc0] or digest(image)!=RGB_SHA or any(a!=b and i not in allowed for i,(a,b) in enumerate(zip(stock,image))):raise ValueError('Resulting firmware hash or vector table mismatch.')
    return {'candidate':bytes(image),'restore':stock}

def request(image,step):
    total=4+(max(0,len(image)-48)+55)//56
    if not 0<=step<total:raise ValueError('Packet index out of range.')
    b=bytearray(64);struct.pack_into('<II',b,0,(0xae,0xb1,0xa2)[step] if step<3 else 0xa0 if step==3 else 0,0x12 if step==0 else 2*step+1)
    if step==3:struct.pack_into('<II',b,8,0,len(image));b[16:16+min(48,len(image))]=image[:48]
    elif step>3:
        chunk=image[48+(step-4)*56:48+(step-3)*56];b[8:8+len(chunk)]=chunk
    return bytes(b)

def audit(events,image,inspect=False):
    expected=3 if inspect else 4+(len(image)-48+55)//56
    tx=[e for e in events if e.get('event')=='submitting'];rx=[e for e in events if e.get('event')=='received']
    sequence=[e['event'] for e in events if e.get('event') in ('submitting','received')]
    if len(tx)!=expected or len(rx)!=expected or sequence!=['submitting','received']*expected:raise ValueError('Incomplete or unordered programming transcript.')
    for i,(sent,reply) in enumerate(zip(tx,rx)):
        b=bytes.fromhex(sent['body_hex']);r=bytes.fromhex(reply['body_hex'])
        if b!=request(image,i) or len(r)!=64 or int.from_bytes(r[:2],'little')!=sum(b)&0xffff or int.from_bytes(r[4:8],'little')!=2*i+2:raise ValueError('Packet, checksum or sequence mismatch.')
        if i==1 and r[8:12]!=bytes.fromhex('102e1301'):raise ValueError('MCU is not the tested M032SE3AE.')
        if i==2 and r[8:24]!=bytes.fromhex('7dfbffffffff0f005affffffffffffff'):raise ValueError('Boot configuration differs from the tested board.')
    result=next((e for e in reversed(events) if e.get('event')=='program_result'),{})
    if result.get('ok') is not True or result.get('submitted')!=expected or result.get('acknowledged')!=expected:raise ValueError('Native programmer did not confirm the whole exchange.')
    return {'reports':expected,'image_sha256':digest(image),'full_flash_readback':False}

class Firmware:
    def __init__(self,hardware,directory=None,runner=None,platform=None):
        self.hardware=hardware;self.directory=Path(directory) if directory else data_root()/'firmware';self.runner=runner;self.platform=platform or sys.platform
        self.lock=threading.RLock();self.plan=None;self.spent=set();self.job=None;self.busy=False
        # An interrupted companion must not offer a replay on the same loader connection.
        for path in sorted(self.directory.glob('attempt-*.json'))[-64:]:
            try:
                old=json.loads(path.read_text())['job'];self.spent.add(old['loader_device_id'])
                if old['state']=='programming':self.job={**old,'state':'failed','message':'A previous companion session ended while programming. The result is unknown. Reconnect into the loader for a fresh check; do not resume the old attempt.'}
            except (OSError,ValueError,KeyError,TypeError):pass
    def available(self):return self.platform=='darwin' and (self.runner is not None or NATIVE.is_file())
    def invoke(self,args):
        if self.runner:return self.runner(args)
        p=subprocess.run([str(NATIVE),*args],capture_output=True,text=True,timeout=15)
        events=[json.loads(line) for line in p.stdout.splitlines() if line.startswith('{')]
        if p.returncode:raise ValueError('Bootloader check failed. No erase was requested. Reconnect normally and review compatibility.')
        return events
    def loader(self):
        if not self.available():return None
        try:return self.invoke(['--devices'])[0].get('loader')
        except (OSError,ValueError,subprocess.SubprocessError,IndexError):return None
    def images(self):
        try:
            images={name:(self.directory/(name+'.bin')).read_bytes() for name in ('candidate','restore')}
            if digest(images['candidate'])!=RGB_SHA or digest(images['restore'])!=STOCK_SHA:return None
            return images
        except OSError:return None
    def policy(self,device):
        with self.lock:
            supported=bool(device.get('capabilities',{}).get('rgb'));available=self.available()
            return {'ok':True,'version':VERSION,'flashing_enabled':available,'writer_present':available,'images_bundled':False,'images_ready':self.images() is not None,
              'state':'already_supported' if supported else 'experimental' if available else 'platform_unavailable','supported_research_model':'DKME2061ST',
              'device':{'connected':device.get('connected',False),'firmware':device.get('firmware'),'mode':device.get('mode','demo')},'loader':None if self.busy else self.loader(),
              'job':dict(self.job) if self.job else None,'recovery_guaranteed':False,'platform':self.platform,'message':RISK,
              'platform_detail':'Firmware installation is available only through the macOS companion. Windows/Linux RGB transports are experimental; firmware programming is not enabled on those operating systems.'}
    def prepare(self,body):
        if body=={'download_official':True}:
            import urllib.request,ssl
            # Frozen Python must not depend on a developer's Homebrew certificate path.
            ca='/etc/ssl/cert.pem' if self.platform=='darwin' and Path('/etc/ssl/cert.pem').is_file() else None
            context=ssl.create_default_context(cafile=ca)
            try:
                with urllib.request.urlopen(OFFICIAL_URL,timeout=20,context=context) as response:updater=response.read(3307521)
            except OSError:raise ValueError('The official download could not be reached. Choose your local V1.10 updater instead.')
        elif set(body)=={'updater_base64'} and isinstance(body['updater_base64'],str) and len(body['updater_base64'])<=4500000:
            updater=base64.b64decode(body['updater_base64'],validate=True)
        else:raise ValueError('Choose the official updater file or the fixed official download.')
        images=construct_images(updater)
        with self.lock:
            if self.busy:raise ValueError('A firmware operation is already running.')
            self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
            for name,data in images.items():
                path=self.directory/(name+'.bin');tmp=path.with_suffix('.tmp');tmp.write_bytes(data);tmp.chmod(0o600);os.replace(tmp,path)
            self.plan=None
        return {'ok':True,'images_ready':True,'candidate_sha256':RGB_SHA,'restore_sha256':STOCK_SHA,'message':'Both exact images prepared locally. No device command was sent.'}
    def inspect(self,body):
        if set(body)!={'device_id','model','consent'} or body['model']!='DKME2061ST' or body['consent'] is not True:raise ValueError('Confirm the underside model is DKME2061ST before checking the bootloader.')
        with self.lock:
            if not self.available() or self.busy:raise ValueError('Firmware installation is unavailable or busy.')
            self.plan=None
            images=self.images();loader=self.loader()
            if not images or not loader or loader['device_id']!=body['device_id'] or loader['device_id'] in self.spent:raise ValueError('Prepare the updater and reconnect in D-on-connect mode. A fresh bootloader connection is required.')
            if not self.hardware.lock.acquire(False):raise ValueError('A keyboard command is already running.')
            try:
                events=self.invoke(['--inspect',loader['device_id'],str(loader['location'])]);audit(events,images['candidate'],True)
            finally:self.hardware.lock.release()
            self.plan={'nonce':secrets.token_urlsafe(24),'loader':loader,'expires':time.monotonic()+120}
            return {'ok':True,'plan_nonce':self.plan['nonce'],'device_id':loader['device_id'],'mcu':'M032SE3AE','configuration_verified':True,'expires_in':120,'message':'Chip and configuration match. No erase or programming command was sent.'}
    def flash(self,body):
        required={'plan_nonce','device_id','image','model','confirmation','accept_risk','consent'}
        if set(body)!=required or body['model']!='DKME2061ST' or body['confirmation']!='FLASH DKME2061ST' or body['accept_risk'] is not True or body['consent'] is not True or body['image'] not in ('candidate','restore'):raise ValueError('Confirm the exact model, image choice and firmware risk before flashing.')
        with self.lock:
            plan=self.plan;images=self.images();loader=self.loader()
            if not self.available() or self.busy or not plan or not images or plan['expires']<time.monotonic() or not secrets.compare_digest(str(body['plan_nonce']),plan['nonce']) or loader!=plan['loader'] or body['device_id']!=loader['device_id'] or loader['device_id'] in self.spent:raise ValueError('The firmware check expired or the connection changed. Run the bootloader check again.')
            if not self.hardware.lock.acquire(False):raise ValueError('A keyboard command is already running.')
            self.spent.add(loader['device_id']);self.plan=None;self.busy=True
            self.job={'id':secrets.token_hex(8),'state':'programming','image':body['image'],'loader_device_id':loader['device_id'],'submitted':0,'total_reports':1164 if body['image']=='candidate' else 1144,'message':'Keep the cable connected. Closing this tab does not stop the companion.'}

            try:
                self.directory.mkdir(parents=True,exist_ok=True)
                with (self.directory/('attempt-'+self.job['id']+'.json')).open('x') as log:json.dump({'job':self.job,'events':[]},log)
            except OSError:
                self.busy=False;self.spent.discard(loader['device_id']);self.job.update(state='failed',message='Cannot save the firmware attempt log. No programming command was sent.');self.hardware.lock.release();raise ValueError(self.job['message'])
            thread=threading.Thread(target=self._program,args=(dict(self.job),loader,images[body['image']]),daemon=False);thread.start()
            return {'ok':True,'job':dict(self.job)}
    def _program(self,job,loader,image):
        events=[];process=None
        try:
            args=['--program-'+job['image'],loader['device_id'],str(loader['location']),str(self.directory/(job['image']+'.bin'))]
            # Runner is injected only by tests. Production always uses the native executable.
            if self.runner:events=self.runner(args);code=0
            else:
                process=subprocess.Popen([str(NATIVE),*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                for line in process.stdout:
                    event=json.loads(line);events.append(event)
                    if event.get('event')=='submitting':
                        with self.lock:self.job['submitted']+=1
                process.wait(timeout=35);code=process.returncode
            if code:raise ValueError('The programming exchange stopped. The application may be incomplete; no retry was sent.')
            verified=audit(events,image)
            with self.lock:self.job.update(state='acknowledged',submitted=verified['reports'],message='All packets acknowledged. This is not full flash readback. Unplug, release D and reconnect normally. Then check typing and lighting.')
        except Exception as error:
            with self.lock:self.job.update(state='failed',message=str(error)+' Recovery is not guaranteed. Do not retry automatically. If D-on-connect still works, a fresh check can prepare manufacturer V1.10 restoration; otherwise hardware repair may be needed.')
        finally:
            if process is not None and process.poll() is None:process.terminate();process.wait(timeout=5)
            try:
                self.directory.mkdir(parents=True,exist_ok=True);(self.directory/('attempt-'+job['id']+'.json')).write_text(json.dumps({'job':self.job,'events':events},indent=2)+'\n')
            except OSError:pass
            with self.lock:self.busy=False
            self.hardware.lock.release()

# Retained for static policy tests and callers; never creates a writer or touches USB.
def policy(device):
    return {'ok':True,'version':VERSION,'flashing_enabled':False,'writer_present':False,'images_bundled':False,'state':'hosted','device':{'connected':False},'message':RISK,'recovery_guaranteed':False}
