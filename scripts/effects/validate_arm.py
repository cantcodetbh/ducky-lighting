"""Execute compiled custom9004 hooks and SRAM flash driver in Unicorn. No USB/MMIO hardware."""
from pathlib import Path
import hashlib,json,struct,sys
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_PRIMASK
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'build/native-effects-candidate'
manifest=json.loads((OUT/'manifest.json').read_text());IMAGE=(OUT/'candidate9004.bin').read_bytes();assert hashlib.sha256(IMAGE).hexdigest()==manifest['image_sha256']
SYMS=manifest['symbols'];CTX=0x20002500

def u32(u,address):return struct.unpack('<I',u.mem_read(address,4))[0]
def put(u,address,value):u.mem_write(address,struct.pack('<I',value&0xffffffff))
def init_ram(image):
    record=0xf4ec;value=lambda offset:struct.unpack_from('<I',image,offset)[0]
    pos=record+value(record);end=pos+(value(record+4)>>1);out=bytearray()
    while pos<end:
        token=image[pos];pos+=1;n=token&3
        if not n:n=image[pos]+3;pos+=1
        match=token>>4
        if match==15:match=image[pos]+15;pos+=1
        out.extend(image[pos:pos+n-1]);pos+=n-1
        if match:
            low=image[pos];pos+=1;high=(token>>2)&3
            if high==3:high=image[pos];pos+=1
            distance=low+(high<<8);assert 0<distance<=len(out)
            for _ in range(match+2):out.append(out[-distance])
    assert pos==end and len(out)==948
    return out

class Machine:
    def __init__(self,image=IMAGE):
        self.u=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS);u=self.u
        u.mem_map(0,0x20000);u.mem_write(0,image);u.mem_map(0x20000000,0x4000);u.mem_write(0x20000000,bytes(init_ram(image)))
        u.mem_map(0x40000000,0x100000);u.mem_map(0xe000e000,0x2000)
        put(u,0x40000000,0x01132e10);self.ctl=2;self.unlocked=0;self.key=0;self.pending=None;self.commands=[];self.busy_fetches=0;self.minimum_sp=0x200005b0;self.cache=0;self.config=0xfffffb7d;self.fail_operation=0;self.interrupt_at=0;self.operations=0;self.fault_stop=False;self.stuck=False;self.accelerate=False;self.ram_halt=False
        u.hook_add(UC_HOOK_MEM_WRITE,self.write);u.hook_add(UC_HOOK_MEM_READ,self.read);u.hook_add(UC_HOOK_CODE,self.code)
    def write(self,u,access,address,size,value,user):
        if 0x200003b4<=address<0x200005b8:self.minimum_sp=min(self.minimum_sp,address)
        if address==0x40000100:
            if value==0:self.unlocked=0;self.key=0
            elif value==(0x59,0x16,0x88)[self.key]:
                self.key+=1
                if self.key==3:self.unlocked=1;self.key=0
            else:self.key=0
        elif address==0x4000c000:
            assert self.unlocked,'FMC protected register changed while locked'
            self.ctl=value&~64
        elif address==0x4000c010 and value&1:
            assert self.unlocked and self.ctl&1 and not self.pending
            command=u32(u,0x4000c00c);target=u32(u,0x4000c004);data=u32(u,0x4000c008)
            assert not self.ctl&(4|16|32),'SPROM/config/LDROM write gates enabled'
            if command==0:assert target==0x300000
            elif command==0x22:assert target in (0x1fc00,0x1fe00) and self.ctl&8
            elif command==0x21:assert 0x1fc00<=target<0x20000 and not target&3 and self.ctl&8
            else:raise AssertionError(f'Forbidden FMC command {command:x}')
            self.pending={'command':command,'address':target,'data':data,'reads':2};self.commands.append(dict(self.pending));put(u,0x4000c040,1)
        elif address==0x4000c018:raise AssertionError("FTCTL/cache operation unsupported on M032SE3AE")
    def read(self,u,access,address,size,value,user):
        if address==0x40000100:put(u,address,self.unlocked)
        elif address==0x4000c000:put(u,address,self.ctl)
        elif address in (0x4000c010,0x4000c040) and self.pending:
            if self.stuck:put(u,address,1);return
            self.pending['reads']-=1
            if self.pending['reads']<=0:self.complete()
            else:put(u,address,1)
        elif address==0x4000c040:put(u,address,self.ctl&64)
        elif address==0x4000c018 and self.cache:
            self.cache=0;put(u,address,u32(u,address)&~0x200)
    def complete(self):
        p=self.pending;self.pending=None;u=self.u;command=p['command'];address=p['address']
        if command==0:put(u,0x4000c008,self.config)
        else:
            self.operations+=1
            if self.interrupt_at==self.operations:
                if command==0x22:u.mem_write(address,b'\xff'*256)
                else:put(u,address,u32(u,address)&(p['data']|0xaaaaaaaa))
                self.fault_stop=True;u.emu_stop();return
            if self.fail_operation==self.operations:self.ctl|=64
            elif command==0x22:u.mem_write(address,b'\xff'*512)
            else:
                old=u32(u,address);assert old&p['data']==p['data'];put(u,address,p['data'])
            u.ctl_remove_cache(0x1fc00,0x20000)
        put(u,0x4000c010,0);put(u,0x4000c040,self.ctl&64)
    def code(self,u,address,size,user):
        if self.accelerate:
            from unicorn.arm_const import UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7
            for reg in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7):
                if u.reg_read(reg)==5000000:u.reg_write(reg,1)
                elif u.reg_read(reg)==(0x100000000-5000000):u.reg_write(reg,0xffffffff)
        halt=0x20002d00+(SYMS['nv_ram_fault']&~1)-manifest['ram_driver']['source_start']
        if self.stuck and address==halt:self.fault_stop=True;self.ram_halt=True;u.emu_stop()
        if self.pending:
            start=0x20002d00;end=start+manifest['ram_driver']['length']
            assert start<=address<end,f'Flash instruction fetch while FMC busy: {address:x}'
            self.busy_fetches+=1
            assert u.reg_read(UC_ARM_REG_PRIMASK)==1,'Flash operation with interrupts enabled'
        if 0x20000000<=address<0x20004000:
            assert 0x20002d00<=address<0x20002d00+manifest['ram_driver']['length'],'Execution left reserved SRAM driver'
    def call(self,address,args=(),stop=0x18000,count=3000000):
        u=self.u;u.reg_write(UC_ARM_REG_SP,0x200005b0);u.reg_write(UC_ARM_REG_LR,stop|1)
        for register,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2),args):u.reg_write(register,value)
        u.emu_start(address|1,stop,count=count)
        assert self.fault_stop or u.reg_read(UC_ARM_REG_PC)==stop,f'Execution stopped at {u.reg_read(UC_ARM_REG_PC):x}'
    def boot(self):
        u=self.u;u.mem_write(0x200005b8,b'\xa5'*(0x3000-0x5b8));u.mem_write(0x20003000,b'\xcc'*8)
        self.call(0xf4b0);assert bytes(u.mem_read(0x200005b8,0x3000-0x5b8))==bytes(0x3000-0x5b8);assert u.mem_read(0x20003000,8)==b'\xcc'*8
        self.call(0xdc35,stop=0xdc42)
        assert u32(u,0x20002400)==SYMS['ducky_class_hook'];self.call(0xc0)
        source=manifest['ram_driver']['source_start'];length=manifest['ram_driver']['length'];assert u.mem_read(0x20002d00,length)==u.mem_read(source,length)
        self.layout=struct.unpack('<9I',u.mem_read(SYMS['ducky_context_layout'],36));assert self.layout[0]<=0x800
        self.offsets=dict(zip(('size','rx','status','mode','pending','last','active','saved','scratch'),self.layout))
        return self
    def irq(self,bits):put(self.u,0x400c0004,bits);self.call(0xedc2)
    def setup(self,bm=0x21,request=9,value=0x0300,length=8):
        for reg in (0x400c050c,0x400c051c):put(self.u,reg,u32(self.u,reg)&~3)
        self.u.mem_write(0x400c0100,struct.pack('<BBHHH',bm,request,value,0,length));self.irq(0x80000002)
    def command(self,packet):
        self.setup();assert self.u.mem_read(CTX+self.offsets['mode'],1)==b'\x01'
        self.u.mem_write(0x400c0108,packet);put(self.u,0x400c0514,len(packet));self.irq(0x20002)
        assert self.u.mem_read(CTX+self.offsets['pending'],1)==b'\x01'
        self.call(0xdd36,stop=0xdd3a)
    def status(self):
        self.setup(0xa1,1);return bytes(self.u.mem_read(0x400c0108,8))
    def flash(self):return bytes(self.u.mem_read(0,0x20000))

m=Machine().boot();assert m.status()==b'DRGB\x02\x00\x00\x00';assert not m.commands
# Real USB IRQ, compiled hooks, bounded parser, original lighting bank.
frame=bytearray()
for row in range(5):
    for col in range(14):
        rgb=bytes(((row*53+col*17)&255,(row*29+col*31)&255,(row*71+col*13)&255));frame.extend(rgb);m.command(bytes([0xd1,1,row,col,*rgb,0]))
expected=struct.pack('<210H',*[v*257 for v in frame]);assert m.u.mem_read(0x20001600,420)==expected
assert not m.commands,'Changing colours wrote nonvolatile storage'
m.command(bytes.fromhex('d104000000000000'));assert m.status()==b'DRGB\x02\x01\x01\x02';assert m.operations==61
saved=m.flash();assert m.busy_fetches>0 and m.ctl==2 and m.unlocked==0
assert saved[:0x1fc00]==IMAGE[:0x1fc00],'Application code changed during save'
# New CPU and empty RAM, no host colour packets: cold startup restores all channels.
cold=Machine(saved).boot();assert cold.status()==b'DRGB\x02\x01\x00\x02';cold.call(0xdd36,stop=0xdd3a);assert cold.u.mem_read(0x20001600,420)==expected;assert not cold.commands
# Unsaved edits are discarded on USB reset; committed colours return.
cold.command(bytes.fromhex('d1020000ff000000'));cold.call(SYMS['ducky_reset_hook']);cold.call(0xdd36,stop=0xdd3a);assert cold.u.mem_read(0x20001600,420)==expected
cold.command(bytes.fromhex('d104000000000000'));assert not cold.commands,'Identical save caused flash wear'
# Clear is a committed tombstone, survives another cold boot.
cold.command(bytes.fromhex('d105000000000000'));assert cold.status()==b'DRGB\x02\x00\x01\x00'
cleared=Machine(cold.flash()).boot();assert cleared.status()==b'DRGB\x02\x00\x00\x00'
# Invalid packets and no-active-frame save never reach FMC.
invalid=Machine().boot()
for packet in (bytes.fromhex('d104000000000000'),bytes.fromhex('d104010000000000'),bytes.fromhex('d105000001000000'),bytes.fromhex('d106000000000000')):invalid.command(packet)
assert not invalid.commands
# Failed configuration/identity stop before any erase/program command.
for what in ('config','chip'):
    fail=Machine(saved).boot();fail.command(bytes.fromhex('d102000001020300'))
    if what=='config':fail.config=0xfffffffc
    else:put(fail.u,0x40000000,0x01132e00)
    fail.command(bytes.fromhex('d104000000000000'))
    assert not any(c['command'] in (0x21,0x22) for c in fail.commands)
    assert fail.flash()==saved
# Power cuts at erase, header, payload, CRC and commit: cold boot yields old or new frame only.
cut_cases=[];new=bytes([9,8,7])*70;new_expected=struct.pack('<210H',*[v*257 for v in new])
for position in (1,2,3,20,59,60,61):
    cut=Machine(saved).boot();cut.command(bytes.fromhex('d102000009080700'));cut.interrupt_at=position;cut.command(bytes.fromhex('d104000000000000'));assert cut.fault_stop
    reboot=Machine(cut.flash()).boot();reboot.call(0xdd36,stop=0xdd3a);actual=bytes(reboot.u.mem_read(0x20001600,420));assert actual in (expected,new_expected)
    cut_cases.append(position)
# FMC-reported failures retain the previous valid record and restore protected state.
for position in (1,20,61):
    error=Machine(saved).boot();error.command(bytes.fromhex('d102000009080700'));error.fail_operation=position;error.command(bytes.fromhex('d104000000000000'))
    assert error.ctl==2 and error.unlocked==0
    reboot=Machine(error.flash()).boot();reboot.call(0xdd36,stop=0xdd3a);assert reboot.u.mem_read(0x20001600,420)==expected
# A stuck FMC must never return to flash code. Accelerate only the timeout counter.
hung=Machine(saved).boot();hung.command(bytes.fromhex('d102000009080700'));hung.stuck=True;hung.accelerate=True;hung.command(bytes.fromhex('d104000000000000'));assert hung.ram_halt and hung.flash()==saved
result={'scope':'Actual compiled Thumb9004 code, original USB IRQ/lighting code and modeled FMC/NOR registers in Unicorn. No hardware access; not a full timing/electrical model.','image_sha256':manifest['image_sha256'],'cold_boot_restored_without_host_commands':True,'usb_reset_restored_last_saved_frame':True,'clear_survives_cold_boot':True,'exact_channels':210,'save_flash_operations':m.operations,'allowed_pages':['0x1fc00','0x1fe00'],'application_region_unchanged':True,'ldrom_config_sprom_writes':0,'busy_instruction_fetches_in_SRAM_only':True,'interrupts_masked_for_all_flash_operations':True,'FMC_and_SYS_lock_state_restored':True,'invalid_commands_write_nothing':True,'wrong_chip_config_write_nothing':True,'sampled_powercut_positions':cut_cases,'minimum_stack_store':hex(min(m.minimum_sp,cold.minimum_sp,invalid.minimum_sp)),'FMC_failure_preserves_old_profile':True,'stuck_FMC_halts_in_SRAM_without_flash_fetch':True,'timeout_test_counter_accelerated':True,'physical_validation':False}
assert int(result['minimum_stack_store'],16)>=0x200003b4
(OUT/'arm-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
