# PyInstaller spec: only runtime resources; no research tools or firmware images.
from pathlib import Path
import sys
from PyInstaller.utils.hooks import copy_metadata
root=Path(SPECPATH).parent
native=root/'build/ducky-rgb'
binaries=[(str(root/'build'/name),'build') for name in ('ducky-rgb','ducky-firmware')] if sys.platform=='darwin' else []
a=Analysis([str(root/'companion.py')],pathex=[str(root/'backend')],binaries=binaries,
 datas=[(str(root/'backend/firmware-patch.json'),'backend'),(str(root/'dist'),'dist'),(str(root/'src/data/layouts.json'),'src/data'),(str(root/'src/assets/Instrument-Sans-OFL.txt'),'licenses')]+copy_metadata('hidapi'),
 hiddenimports=['hid','portable_worker','hid_transport','firmware','runtime','firmware_hid','firmware_ipc'],hookspath=[],hooksconfig={},excludes=['tkinter','unittest','pytest'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='ducky-companion' if sys.platform=='darwin' else 'DuckyLighting',
 debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=sys.platform!='win32',
 icon=str(root/'packaging/DuckyLighting.ico') if sys.platform=='win32' else None)
# A console helper has reliable redirected stdio on Windows; the UI executable is windowed.
wa=Analysis([str(root/'backend/firmware_worker.py')],pathex=[str(root/'backend')],binaries=[],datas=[],hiddenimports=['hid','firmware_virtual'],excludes=['tkinter','unittest','pytest'])
wp=PYZ(wa.pure)
worker=EXE(wp,wa.scripts,[],exclude_binaries=True,name='DuckyFirmwareWorker',debug=False,strip=False,upx=False,console=True)
coll=COLLECT(exe,worker,a.binaries,a.datas,wa.binaries,wa.datas,strip=False,upx=False,name='companion' if sys.platform=='darwin' else 'DuckyLighting')
