"""Run production IOKit helper against RAM-only SDK mocks, never real devices."""
from pathlib import Path
import subprocess,sys
root=Path(__file__).resolve().parents[1]
if sys.platform!='darwin':print('SKIP: native SDK tests require macOS.');raise SystemExit(0)
binary=root/'build/rgb-policy-test';binary.parent.mkdir(exist_ok=True)
subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror','-pedantic','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(root/'backend/native/rgb_test.c'),'-framework','IOKit','-framework','CoreFoundation','-o',str(binary)],check=True)
r=subprocess.run([str(binary)],capture_output=True,text=True,check=True)
(root/'evidence/native-policy.txt').write_text(r.stdout+r.stderr);print(r.stdout)
