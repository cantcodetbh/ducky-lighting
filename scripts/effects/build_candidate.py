"""Build a reproducible custom9004 trial image offline. Never runs the updater or accesses USB."""
from pathlib import Path
import argparse,hashlib,json,struct,subprocess,sys,zlib
from elftools.elf.elffile import ELFFile
from capstone import Cs,CS_ARCH_ARM,CS_MODE_THUMB,CS_MODE_MCLASS
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/native-effects-candidate'
HOOKS=[(0xdc3a,0xe5be,'ducky_open_hook'),(0xdc86,0x5fd8,'ducky_lighting_hook'),(0xdd36,0x5fd8,'ducky_lighting_hook'),(0xee8c,0xe624,'ducky_setup_hook'),(0xeeb0,0xeca4,'ducky_out_hook'),(0xee26,0xecf8,'ducky_reset_hook')]
def sha(data):return hashlib.sha256(data).hexdigest()
def thumb_bl(pc,target):
    displacement=target-(pc+4)
    assert displacement%2==0 and -(1<<22)<=displacement<(1<<22)
    encoded=displacement&0x1ffffff;s=(encoded>>24)&1;i1=(encoded>>23)&1;i2=(encoded>>22)&1
    return struct.pack('<HH',0xf000|(s<<10)|((encoded>>12)&0x3ff),0xd000|(((~(i1^s))&1)<<13)|(((~(i2^s))&1)<<11)|((encoded>>1)&0x7ff))
def seed(sequence):
    data=bytearray(b'\xff'*512)
    struct.pack_into('<5I',data,0,0x334b5544,0x50524759,1,sequence,0)
    data[20:230]=bytes(210)
    struct.pack_into('<II',data,232,zlib.crc32(data[:232]),0x54494d43)
    return bytes(data)
def build(updater):
    exe=updater.read_bytes();assert len(exe)==3307520 and sha(exe)=='6d5b1a8fb16c53fc2875dad5399cd574b1fc05eef83141dd89fbcee0ede5aab8'
    stock=exe[0x20f0b8:0x21ea20];assert sha(stock)=='fb29585b17a0ee1883287def35a1b107695a13c4dc85355cb27f54921ea5f514' and struct.unpack_from('<I',exe,0x21ea20)[0]==len(stock)
    OUT.mkdir(parents=True,exist_ok=True);source=ROOT/'firmware/effects-rgb';commands=[]
    for name in ('host_rgb','usb_integration','onboard_store','onboard_hw'):
        command=['clang','--target=arm-none-eabi','-mcpu=cortex-m0','-mthumb','-Oz','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Wall','-Wextra','-Werror','-c',str(source/(name+'.c')),'-o',str(OUT/(name+'.o'))]
        subprocess.run(command,check=True);commands.append(command)
    elfpath=OUT/'onboard9004.elf';command=[sys.executable,'-m','ziglang','ld.lld','-T',str(source/'analysis.ld'),*[str(OUT/(name+'.o')) for name in ('host_rgb','usb_integration','onboard_store','onboard_hw')],'-o',str(elfpath)];subprocess.run(command,check=True);commands.append(command)
    with elfpath.open('rb') as file:
        elf=ELFFile(file);table=elf.get_section_by_name('.symtab');symbols={s.name:int(s['st_value']) for s in table.iter_symbols() if s.name}
        assert not [s.name for s in table.iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF']
        segments=[{'address':int(s['p_vaddr']),'hex':s.data().hex()} for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_filesz']]
    image=bytearray(stock+b'\xff'*(0x20000-len(stock)));edits=[];md=Cs(CS_ARCH_ARM,CS_MODE_THUMB|CS_MODE_MCLASS)
    for pc,old,name in HOOKS:
        before=stock[pc:pc+4];insn=list(md.disasm(before,pc));assert len(insn)==1 and insn[0].mnemonic=='bl' and insn[0].op_str==f'#{old:#x}'
        target=symbols[name]&~1;after=thumb_bl(pc,target);decoded=list(md.disasm(after,pc));assert len(decoded)==1 and decoded[0].op_str==f'#{target:#x}'
        image[pc:pc+4]=after;edits.append({'address':hex(pc),'before':before.hex(),'after':after.hex(),'hook':name})
    assert stock[0xf4dc:0xf4e0].hex()=='c01e0000'
    bss=struct.pack('<I',0x3000-0x5b8);image[0xf4dc:0xf4e0]=bss;edits.append({'address':'0xf4dc','before':'c01e0000','after':bss.hex(),'kind':'Reserve context and SRAM driver through0x20003000'})
    for segment in segments:
        address=segment['address'];data=bytes.fromhex(segment['hex']);assert 0xf970<=address and address+len(data)<=0x1fc00;image[address:address+len(data)]=data
    for address,sequence in ((0x1fc00,0),(0x1fe00,1)):image[address:address+512]=seed(sequence)
    assert image[:0xc0]==stock[:0xc0]
    allowed={offset for e in edits for offset in range(int(e['address'],16),int(e['address'],16)+4)}
    assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(stock,image)))
    start,end=symbols['__ramfunc_start'],symbols['__ramfunc_end'];assert end-start<=0x300
    # Verify every direct branch in the copied code remains inside that blob.
    section=next(s for s in segments if s['address']<=start< s['address']+len(bytes.fromhex(s['hex'])))
    blob=bytes.fromhex(section['hex'])[start-section['address']:end-section['address']]
    (OUT/'ram-driver.bin').write_bytes(blob)
    (OUT/'candidate9004.bin').write_bytes(image)
    result={'scope':'Offline trial build only. No device writes. Physical persistence and recovery remain unverified.','firmware':'custom9004','image_length':len(image),'image_sha256':sha(image),'stock_payload_sha256':sha(stock),'vector_table_preserved':True,'edits':edits,'segments':segments,'symbols':symbols,'ram_driver':{'source_start':start,'length':end-start,'target':0x20002d00,'command_offset':(symbols['nv_ram_command']&~1)-start},'journal':{'slot0':0x1fc00,'slot1':0x1fe00,'page_size':512,'record_bytes':240,'initial_records':'two valid clear tombstones','install_erases_saved_profile':True},'source_sha256':{str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(source.iterdir()) if p.is_file()},'toolchain':subprocess.check_output(['clang','--version'],text=True).splitlines()[0]}
    (OUT/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('updater',type=Path);args=parser.parse_args();m=build(args.updater);print(json.dumps({k:m[k] for k in ('firmware','image_length','image_sha256','ram_driver','journal')},indent=2))
