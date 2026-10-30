"""Fixed Nuvoton ISP HID transport for Windows/Linux; no arbitrary packet interface.
HIDAPI write: zero report-ID + 64 bytes. Read: exactly 64 unnumbered bytes.
https://libusb.info/hidapi/group__API.html
"""
import hashlib,importlib,json,secrets,time,sys
from pathlib import Path
VID,PID=0x0416,0x3f00
DESCRIPTOR=bytes.fromhex('0600ff0901a10119012940150026ff00750895408100190129409100c0')
class LoaderError(ValueError):pass

def identity(info):return str(int.from_bytes(hashlib.sha256(bytes(info['path'])).digest()[:8],'big'))
def library():return importlib.import_module('hidraw' if sys.platform.startswith('linux') else 'hid')
def selected(module):
    all_devices=module.enumerate(VID,PID)
    if len(all_devices)!=1:return None
    d=all_devices[0]
    if (d.get('vendor_id'),d.get('product_id'),d.get('usage_page'),d.get('usage'))!=(VID,PID,0xff00,1) or d.get('bus_type',1) not in (0,1):return None
    return d

def _vendor_reports(raw,expected):
    # Windows reconstructs descriptors. Permit equivalent encodings, not arbitrary HID layouts.
    if not raw or len(raw)>4096:return False
    g={};local={};depth=0;counts={kind:0 for kind in expected};i=0;opened=False;closed=False
    try:
        while i<len(raw):
            prefix=raw[i];i+=1
            if prefix==0xfe:return False
            size=(0,1,2,4)[prefix&3];kind=(prefix>>2)&3;tag=prefix>>4
            if i+size>len(raw):return False
            value=int.from_bytes(raw[i:i+size],'little');i+=size
            if kind==1:
                if tag in (0,1,2,7,9):g[tag]=value
                elif tag in (3,4,5,6) and value==0:pass
                else:return False  # no report IDs, stacks or unsupported globals
            elif kind==2:
                if tag not in (0,1,2):return False
                page=value>>16 if size==4 else g.get(0)
                if page!=0xff00:return False
                usage=value&0xffff
                if not 1<=usage<=64:return False
                local[tag]=usage
            elif kind==0:
                if tag==10:
                    if opened or closed or depth or value!=1 or g.get(0)!=0xff00 or local.get(0)!=1:return False
                    depth=1;opened=True
                elif tag==12:
                    if depth!=1 or size:return False
                    depth=0;closed=True
                elif tag in counts:
                    if depth!=1 or g.get(0)!=0xff00 or g.get(1)!=0 or g.get(2)!=255 or g.get(7)!=8 or g.get(9)!=expected[tag] or value not in (0,2):return False
                    counts[tag]+=1
                else:return False  # no Feature, padding or extra report families
                local={}
            else:return False
        return opened and closed and depth==0 and counts=={kind:1 for kind in expected}
    except (ValueError,TypeError):return False

def descriptor_valid(raw):
    return raw==DESCRIPTOR or _vendor_reports(raw,{8:64,9:64})

def feature_descriptor_valid(raw):
    # Windows exposes the vendor top-level collection separately from the keyboard collection.
    return _vendor_reports(raw,{11:8})

class Discovery:
    def __init__(self,blocked=(),module=None):self.module=module;self.blocked=set(blocked);self.path=None;self.epoch=None
    def status(self):
        module=self.module or library();entries=module.enumerate(VID,PID)
        if not entries:
            self.path=None;self.epoch=None;self.blocked.clear();return None
        d=selected(module)
        if not d:return None
        stable=identity(d)
        if self.path!=stable:self.path=stable;self.epoch=secrets.token_hex(16)
        token=str(int.from_bytes(hashlib.sha256((stable+self.epoch).encode()).digest()[:8],'big'))
        return {'device_id':token,'location':0,'transport_id':stable,'requires_reconnect':stable in self.blocked}

class LoaderSession:
    """One open handle survives check → confirmation → programming. Never reopens on error."""
    def __init__(self,device_id,module=None,emit=None):
        self.module=module or library();self.emit=emit or (lambda event:None);self.device=None;self.failed=False;self.aprom_attempted=False
        self.chosen=selected(self.module)
        if not self.chosen or identity(self.chosen)!=device_id:raise LoaderError('The selected bootloader disappeared or is ambiguous. Nothing sent.')
        try:
            self.device=self.module.device();self.device.open_path(self.chosen['path'])
            if not descriptor_valid(bytes(self.device.get_report_descriptor())):raise LoaderError('Bootloader descriptor differs from the supported 64-byte vendor interface. Nothing sent.')
        except Exception:
            self.close();raise
    def close(self):
        if self.device is not None:
            try:self.device.close()
            except OSError:pass
            self.device=None
    def same(self):
        current=selected(self.module)
        if self.device is None or not current or current['path']!=self.chosen['path']:raise LoaderError('Bootloader disconnected or changed. No reopen or retry sent.')
    def execute(self,image,inspect=False):
        from firmware import request,digest
        if self.failed:raise LoaderError('This session failed. A fresh connection is required.')
        submitted=acknowledged=written=0;total=3 if inspect else 4+(len(image)-48+55)//56
        try:
            for step in range(total):
                self.same()
                if self.device.read(65,0):raise LoaderError('Unexpected or duplicate bootloader input. No next packet sent.')
                body=request(image,step)
                self.emit({'event':'submitting','body_hex':body.hex()});submitted+=1
                if step==3:self.aprom_attempted=True
                # hid_write uses interrupt OUT when available, SET_REPORT otherwise.
                if self.device.write(b'\0'+body)!=65:raise LoaderError('Bootloader output transfer was incomplete. No retry sent.')
                reply=bytes(self.device.read(65,30000 if step>=3 else 3000))
                self.emit({'event':'received','body_hex':reply.hex()})
                if len(reply)!=64 or int.from_bytes(reply[:2],'little')!=sum(body)&65535 or int.from_bytes(reply[4:8],'little')!=step*2+2:raise LoaderError('Bootloader reply length, checksum or sequence mismatch. No retry sent.')
                acknowledged+=1
                if step==1 and reply[8:12]!=bytes.fromhex('102e1301'):raise LoaderError('MCU differs from M032SE3AE. No erase sent.')
                if step==2 and reply[8:24]!=bytes.fromhex('7dfbffffffff0f005affffffffffffff'):raise LoaderError('Boot configuration differs from the tested board. No erase sent.')
                if step>=3:written+=len(image[:48]) if step==3 else len(image[48+(step-4)*56:48+(step-3)*56])
            self.same()
            if self.device.read(65,0):raise LoaderError('Unexpected trailing bootloader input. Result is uncertain.')
            result={'event':'program_result','ok':True,'submitted':submitted,'acknowledged':acknowledged,'bytes_acknowledged':written,'aprom_attempted':self.aprom_attempted,'image_sha256':digest(image)}
            self.emit(result);return result
        except Exception:
            self.failed=True;raise

def pinned_image(path,name):
    from firmware import RGB_SHA,STOCK_SHA,digest
    if name not in ('candidate','restore'):raise LoaderError('Unsupported image choice.')
    limit=131072 if name=='candidate' else 63848
    with Path(path).open('rb') as file:data=file.read(limit+1)
    if len(data)!=limit or digest(data)!=(RGB_SHA if name=='candidate' else STOCK_SHA):raise LoaderError('Firmware image hash or size mismatch. No programming sent.')
    return data
