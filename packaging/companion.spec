# PyInstaller spec: only runtime resources; no research tools or firmware images.
from pathlib import Path
import sys
from PyInstaller.utils.hooks import copy_metadata
root=Path(SPECPATH).parent
native=root/'build/ducky-rgb'
binaries=[(str(root/'build'/name),'build') for name in ('ducky-rgb','ducky-firmware')] if sys.platform=='darwin' else []
a=Analysis([str(root/'companion.py')],pathex=[str(root/'backend')],binaries=binaries,
 datas=[(str(root/'backend/firmware-patch.json'),'backend'),(str(root/'dist'),'dist'),(str(root/'src/data/layouts.json'),'src/data'),(str(root/'src/assets/Instrument-Sans-OFL.txt'),'licenses')]+copy_metadata('hidapi'),
 hiddenimports=['hid','portable_worker','hid_transport','firmware','runtime'],hookspath=[],hooksconfig={},excludes=['tkinter','unittest','pytest'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='ducky-companion' if sys.platform=='darwin' else 'DuckyLighting',
 debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=sys.platform!='win32',
 icon=str(root/'packaging/DuckyLighting.ico') if sys.platform=='win32' else None)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='companion' if sys.platform=='darwin' else 'DuckyLighting')
