"""Run production packet core against actual Nuvoton parser with RAM-only flash stubs. Never USB."""
from pathlib import Path
import json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from firmware import audit
compiler=shutil.which('clang') or shutil.which('cc')
if not compiler:raise SystemExit('A C compiler is required for the RAM-only bootloader tests.')
out=ROOT/'build/firmware-fixture';out.mkdir(parents=True,exist_ok=True)
flags=[compiler,'-std=c11','-I'+str(ROOT/'backend/native/firmware'),'-I'+str(ROOT/'tests/firmware-fixture')]
if sys.platform!='win32':flags+=['-fsanitize=address,undefined','-fno-omit-frame-pointer']
binary=out/('bootloader-test.exe' if sys.platform=='win32' else 'bootloader-test')
subprocess.run([*flags,str(ROOT/'tests/firmware-fixture/offline_test.c'),str(ROOT/'tests/firmware-fixture/reference_parser.c'),'-o',str(binary)],check=True)
result=subprocess.check_output([str(binary)],text=True)
audits={}
for name,length,factor,offset in [('candidate',131072,131,17),('restore',63848,137,23)]:
    events=[json.loads(line) for line in subprocess.check_output([str(binary),'--transcript-'+name],text=True).splitlines()]
    image=bytes((i*factor+offset)%256 for i in range(length));audits[name]=audit(events,image)
    events[3]['body_hex']='00'*64
    try:audit(events,image)
    except ValueError:pass
    else:raise AssertionError('Corrupt reply passed independent audit.')
if sys.platform=='darwin':
    native=out/'callback-test'
    subprocess.run([compiler,'-std=c11','-Wall','-Wextra','-Werror','-Wno-deprecated-declarations','-fsanitize=address,undefined',str(ROOT/'backend/native/firmware/callback_test.c'),'-framework','IOKit','-framework','CoreFoundation','-o',str(native)],check=True)
    callback=subprocess.check_output([str(native)],text=True).splitlines()[-1]
else:callback='Native IOKit callbacks apply to macOS only.'
record={'platform':sys.platform,'scope':'RAM-only bootloader protocol simulation, not USB transport or physical flash validation. No device APIs invoked.','reference_parser':result.strip(),'independent_audits':audits,'native_callback_tests':callback,'USB_calls':0}
(ROOT/'release').mkdir(exist_ok=True);(ROOT/'release/firmware-simulation.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
