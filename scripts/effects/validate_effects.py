"""Compiled custom9004 control hook + original native renderers. Offline only."""
from pathlib import Path
import json,struct
p=Path(__file__).with_name('validate_arm.py');scope={'__file__':str(p)}
exec(compile(p.read_text().split('\nm=Machine().boot();')[0],str(p),'exec'),scope)
Machine=scope['Machine'];OUT=scope['OUT'];manifest=scope['manifest'];put=scope['put']
results=[]
for mode,name,speed_address in [(1,'Wave',0x20002153),(4,'Ripple',0x20002156),(6,'Reactive',0x2000214f),(8,'Breathing',0x2000214e)]:
 m=Machine().boot()
 for a in (0xe000,0x915c):m.call(a)
 from unicorn import UC_HOOK_CODE
 def no_storage(u,address,size,user):
  assert address not in (0x79a0,0x7ae0,0x86d6), 'Effect reached original settings/SPI storage path'
 m.u.hook_add(UC_HOOK_CODE,no_storage)
 m.u.mem_write(0x20001fcc,b'\1'*70)
 m.command(bytes([0xd1,6,mode,10,255,0,0,0]));assert m.status()==b'DRGB\x02\x01\x01\x00'
 assert m.u.mem_read(0x2000211d,1)==bytes([mode]) and m.u.mem_read(speed_address,1)==b'\x09'
 def tick():
  m.u.mem_write(0x20000db8,b'\x01');m.call(0xdd36,stop=0xdd3a)
  return bytes(m.u.mem_read(0x20001600,420))
 quiet=[tick() for _ in range(70)]
 if mode in (4,6):
  assert not any(quiet[-1]),'Unpressed matrix should be dark'
  m.u.mem_write(0x20001fcc+15,b'\0') # actual matrix-state convention: pressed=0; Q row1 col1
  pressed=[tick() for _ in range(70)];assert any(pressed[-1]) or any(any(f) for f in pressed)
  if mode==6:
   frame=next(f for f in pressed if any(f));assert any(frame[15*6:16*6]);assert not any(frame[:15*6]+frame[16*6:]),'Reactive should initially light only Q'
  m.u.mem_write(0x20001fcc+15,b'\1');released=[tick() for _ in range(70)]
  assert len(set(pressed+released))>1
 else:assert len(set(quiet))>1,'Native ticks must change output without host frame packets'
 assert not m.commands,'Native effect invoked FMC'
 # Invalid effects/speed/reserved byte leave parameter state unchanged and cannot reach storage.
 before=bytes(m.u.mem_read(0x2000211c,64))
 for packet in [bytes([0xd1,6,2,5,1,2,3,0]),bytes([0xd1,6,6,0,1,2,3,0]),bytes([0xd1,6,6,11,1,2,3,0]),bytes([0xd1,6,6,5,1,2,3,1])]:
  m.command(packet);assert m.status()[6]==0;assert bytes(m.u.mem_read(0x2000211c,64))==before
 # Raw Save while a native effect owns output must fail, rather than save stale frame RAM.
 m.command(bytes.fromhex('d104000000000000'));assert m.status()[6]==0 and not m.commands
 # A normal static command cleanly takes ownership back.
 m.command(bytes.fromhex('d102000010203000'));assert m.status()[6]==1
 assert m.u.mem_read(0x20001600,420)==struct.pack('<210H',*([0x1010,0x2020,0x3030]*70))
 results.append({'mode':mode,'effect':name,'native_ticks':70,'speed_parameter':hex(speed_address),'synthetic_matrix_response':mode in (4,6),'host_frame_packets_during_animation':0,'flash_commands':0,'settings_dirty_or_SPI_queue_calls':0,'invalid_parameters_refused':True,'static_takeover':True,'minimum_stack_store':hex(m.minimum_sp)})
result={'image_sha256':manifest['image_sha256'],'scope':'Compiled custom9004 USB hooks and original V1.10 native renderers with synthetic matrix-state bytes and modeled peripheral memory. Not physical keypress or timing validation.','cases':results,'physical_validation':False}
(OUT/'effects-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
