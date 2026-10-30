"""Explicit NoUSB fixture for testing the packaged helper. Cannot load a real HID library."""
from firmware_hid import DESCRIPTOR,LoaderSession,identity
class VirtualHID:
    def __init__(self):
        self.entries=[{'vendor_id':0x0416,'product_id':0x3f00,'usage_page':0xff00,'usage':1,'path':b'RAM-ONLY-NO-USB','bus_type':1}]
        self.opens=0;self.writes=[];self.replies=[];self.flash=bytearray();self.offset=0;self.step=0;self.error=None;self.descriptor=DESCRIPTOR;self.closed=False;self.generation=0;self.opened_generation=0
    def enumerate(self,*args):return self.entries
    def device(self):return self
    def open_path(self,path):self.opens+=1;self.opened_generation=self.generation
    def get_report_descriptor(self):return self.descriptor
    def close(self):self.closed=True
    def read(self,length,timeout):
        assert length==65
        if self.error=='disconnect' and self.step>=4 and timeout:raise OSError('Simulated removal')
        return self.replies.pop(0) if self.replies else []
    def write(self,packet):
        if self.closed or self.opened_generation!=self.generation:raise OSError('Original device handle was removed')
        assert len(packet)==65 and packet[0]==0
        body=bytes(packet[1:]);self.writes.append(bytes(packet));command=int.from_bytes(body[:4],'little');sequence=int.from_bytes(body[4:8],'little')
        if command==0xae:self.step=0
        expected=(0xae,0xb1,0xa2,0xa0)[self.step] if self.step<4 else 0
        assert command==expected
        if self.step==3:
            assert int.from_bytes(body[8:12],'little')==0
            self.flash=bytearray(int.from_bytes(body[12:16],'little'));self.offset=0
        if self.step>=3:
            chunk=body[16:] if self.step==3 else body[8:];count=min(len(chunk),len(self.flash)-self.offset);self.flash[self.offset:self.offset+count]=chunk[:count];self.offset+=count
        reply=bytearray(64);reply[:2]=(sum(body)&65535).to_bytes(2,'little');reply[4:8]=(2 if self.step==0 else sequence+1).to_bytes(4,'little')
        if self.step==1:reply[8:12]=bytes.fromhex('102e1301') if self.error!='mcu' else bytes(4)
        if self.step==2:reply[8:24]=bytes.fromhex('7dfbffffffff0f005affffffffffffff') if self.error!='config' else bytes(16)
        if self.error=='checksum' and self.step==5:reply[0]^=1
        if self.error=='sequence' and self.step==5:reply[4]^=1
        if self.error=='short' and self.step==5:reply=reply[:-1]
        if self.error=='numbered' and self.step==5:reply=b'\0'+reply
        self.replies.append(reply)
        if self.error=='duplicate' and self.step==5:self.replies.append(reply)
        self.step+=1
        return 64 if self.error=='partial_write' and self.step==6 else 65

def verify():
    from firmware import audit
    results=[]
    for name,length in [('candidate',131072),('restore',63848)]:
        module=VirtualHID();events=[];image=bytes(i%251 for i in range(length));session=LoaderSession(identity(module.entries[0]),module,events.append)
        session.execute(image,True);assert len(module.writes)==3 and not module.flash
        events.clear();session.execute(image);report=audit(events,image);assert bytes(module.flash)==image;assert module.opens==1
        session.close();results.append({'image':name,'reports':report['reports'],'same_open_handle':True})
    negative=[]
    for fault in ('mcu','config','checksum','sequence','short','numbered','duplicate','partial_write','disconnect'):
        module=VirtualHID();module.error=fault;session=LoaderSession(identity(module.entries[0]),module)
        try:session.execute(bytes(131072))
        except (ValueError,OSError):pass
        else:raise AssertionError('Virtual failure accepted: '+fault)
        count=len(module.writes)
        try:session.execute(bytes(131072))
        except ValueError:pass
        else:raise AssertionError('Failed session reused')
        assert len(module.writes)==count
        if fault in ('mcu','config'):assert not module.flash
        session.close();negative.append(fault)
    return {'ok':True,'scope':'Packaged portable firmware transport with injected RAM-only HID fixture. No real device APIs.','virtual_images':results,'failure_cases':negative,'actual_USB_calls':0}
