"""Portable, typed custom9002 Feature transport. No Output/loader/firmware API."""
import hashlib,threading,time
DESC=bytes.fromhex('05010906a101050719e029e71500250175019508810295017508810395037501050819012903910295017505910395067508150026a4000507190029a48100c00600ff0901a101150026ff00750895080902b102c0')
VID,PID,REV=0x3233,0x6301,0x9002
class TransportError(Exception):pass
class PortableHID:
    def __init__(self,module=None):self.module=module;self.last=None
    def library(self):
        if self.module is None:
            try:
                from firmware_hid import library
                self.module=library()
            except ImportError:raise TransportError('The HID adapter is not installed. Use the packaged companion.')
        return self.module
    def enumerate(self):
        try:return [d for d in self.library().enumerate(VID,PID) if d.get('vendor_id')==VID and d.get('product_id')==PID]
        except (OSError,TransportError):return []
    @staticmethod
    def identity(d):
        # Do not expose serial/path strings in the local API or diagnostics.
        return str(int.from_bytes(hashlib.sha256(bytes(d['path'])+str(d.get('release_number')).encode()).digest()[:8],'big'))
    @staticmethod
    def candidate(d):return d.get('release_number')==REV and ((d.get('usage_page'),d.get('usage'))==(0xff00,1) or ((d.get('usage_page'),d.get('usage'))==(1,6) and d.get('interface_number') in (0,-1)))
    def selected(self):
        candidates=[d for d in self.enumerate() if self.candidate(d)]
        vendor=[d for d in candidates if d.get('usage_page')==0xff00]
        candidates=vendor or candidates
        return candidates[0] if len(candidates)==1 else None
    def status(self):
        all_devices=self.enumerate();selected=self.selected() if all_devices else None
        return {'ok':True,'connected':bool(all_devices),'rgb_control':selected is not None,'device_id':self.identity(selected) if selected else None,'matching_interfaces':1 if selected else 0}
    @staticmethod
    def operations(action,payload):
        if action=='release':return [bytes([0xd1,3,0,0,0,0,0,0])]
        if action!='pixels' or not isinstance(payload,list) or not 1<=len(payload)<=70:raise TransportError('Invalid typed colour operation.')
        seen=set();ops=[]
        for row,col,rgb in payload:
            if type(row) is not int or type(col) is not int or not 0<=row<5 or not 0<=col<14 or (row,col) in seen or len(rgb)!=3 or any(type(v) is not int or not 0<=v<=255 for v in rgb):raise TransportError('Invalid or duplicate LED colour.')
            seen.add((row,col));ops.append(bytes([0xd1,1,row,col,*rgb,0]))
        return ops
    def command(self,action,payload,device_id):
        submitted=accepted=0;device=None;started=time.monotonic();previous=None
        try:
            ops=self.operations(action,payload);chosen=self.selected()
            if not chosen or self.identity(chosen)!=device_id:raise TransportError('Keyboard disconnected or changed. Refresh the connection.')
            device=self.library().device();device.open_path(chosen['path'])
            if bytes(device.get_report_descriptor())!=DESC:raise TransportError('Report descriptor differs from the tested keyboard. No colour sent.')
            def still_same():
                current=self.selected()
                if not current or current['path']!=chosen['path'] or self.identity(current)!=device_id:raise TransportError('Keyboard changed during the command. No retry sent.')
                if time.monotonic()-started>8:raise TransportError('Command deadline reached. Last colour may have applied; no retry sent.')
            def status():
                for attempt in range(3):
                    still_same();time.sleep(.01)
                    try:
                        report=bytes(device.get_feature_report(0,9))
                        if len(report)==9 and report[0]==0:
                            b=report[1:]
                            if b[:5]==b'DRGB\x01' and all(v in (0,1) for v in b[5:]):return b
                    except OSError:pass
                raise TransportError('No valid custom RGB status. Colour writes were not retried.')
            state=status();previous=bool(state[5])
            if state[7]:raise TransportError('Keyboard is still processing a previous colour.')
            for index,body in enumerate(ops):
                still_same();time.sleep(.01);submitted+=1
                if device.send_feature_report(b'\0'+body)!=9:raise TransportError('Colour transfer failed. No automatic retry.')
                if index:accepted+=1
            for _ in range(3):
                state=status()
                if not state[7]:break
            if state[7] or state[6]!=1 or state[5]!=(action!='release'):raise TransportError('Final command was not acknowledged.')
            accepted=len(ops)
            result={'ok':True,'accepted_count':accepted,'submitted_count':submitted,'previous_rgb_active':previous,'device_id':device_id,'elapsed_ms':round((time.monotonic()-started)*1000,1),'transport':'hidapi','physical_validation':'Windows/Linux physical validation pending'}
        except (OSError,TransportError,ValueError,TypeError) as e:result={'ok':False,'error':str(e),'accepted_count':accepted,'submitted_count':submitted,'previous_rgb_active':previous,'unknown':submitted>accepted}
        finally:
            if device is not None:
                try:device.close()
                except OSError:pass
        self.last=result;return result
