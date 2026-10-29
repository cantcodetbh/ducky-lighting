"""Compile the existing verified macOS RGB helper; no device access."""
import subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if sys.platform!='darwin':print('Non-macOS host: hardware adapter unavailable; Demo Mode enabled.');raise SystemExit(0)
binary=root/'build/ducky-rgb';binary.parent.mkdir(exist_ok=True)
try:
    subprocess.run(['clang','-mmacosx-version-min=12.0','-std=c11','-Wall','-Wextra','-Werror',str(root/'backend/native/rgb.c'),'-framework','IOKit','-framework','CoreFoundation','-o',str(binary)],check=True)
except (OSError,subprocess.SubprocessError):
    binary.unlink(missing_ok=True)
    print('Native helper could not be built. Editor will run without RGB hardware control. Install Apple command-line tools and relaunch to enable it.')
else:print('Built native helper. No HID reports sent.')

writer=root/'build/ducky-firmware'
subprocess.run(['clang','-mmacosx-version-min=12.0','-std=c11','-Wall','-Wextra','-Werror','-Wno-deprecated-declarations',str(root/'backend/native/firmware/writer.c'),'-framework','IOKit','-framework','CoreFoundation','-o',str(writer)],check=True)
print('Built fixed-image firmware helper. No device access.')
