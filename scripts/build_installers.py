"""Build native preview installers on their target OS; never publishes or flashes."""
from pathlib import Path
import hashlib,json,os,platform,plistlib,shutil,subprocess,sys,tarfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from runtime import VERSION
OUT=ROOT/'release';STAGE=ROOT/'build/packaged';OUT.mkdir(exist_ok=True)
def run(args,**kwargs):return subprocess.run([str(a) for a in args],cwd=ROOT,check=True,**kwargs)
if sys.platform=='win32':
    cli=Path(shutil.which('npm.cmd') or '').parent/'node_modules/npm/bin/npm-cli.js'
    if not cli.is_file():raise SystemExit('Cannot locate the Node.js npm CLI.')
    run([shutil.which('node') or 'node',cli,'run','build'])
else:run(['npm','run','build'])
if sys.platform=='darwin':run([sys.executable,ROOT/'scripts/build_native.py'])
run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--distpath',STAGE,'--workpath',ROOT/'build/pyinstaller',ROOT/'packaging/companion.spec'])
arch=platform.machine().lower();arch='arm64' if arch in ('arm64','aarch64') else 'x64'
worker=STAGE/('companion' if sys.platform=='darwin' else 'DuckyLighting')/('DuckyFirmwareWorker.exe' if sys.platform=='win32' else 'DuckyFirmwareWorker')
worker_result=json.loads(subprocess.check_output([str(worker),'--self-test'],text=True))
assert worker_result['ok'] and worker_result['actual_USB_calls']==0
assert worker_result['hid_backend']==('hidraw' if sys.platform.startswith('linux') else 'hid')
(OUT/'portable-firmware-worker.json').write_text(json.dumps(worker_result,indent=2)+'\n')
if sys.platform=='darwin':
    app=STAGE/'Ducky Lighting.app';contents=app/'Contents';(contents/'MacOS').mkdir(parents=True,exist_ok=True);(contents/'Resources').mkdir(exist_ok=True)
    shutil.copytree(STAGE/'companion',contents/'Resources/companion',dirs_exist_ok=True)
    shutil.copy2(ROOT/'packaging/DuckyLighting.icns',contents/'Resources/DuckyLighting.icns')
    run(['swiftc','-target',('arm64' if arch=='arm64' else 'x86_64')+'-apple-macos12.0',ROOT/'packaging/MacLauncher.swift','-framework','AppKit','-o',contents/'MacOS/DuckyLighting'])
    info={'CFBundleIdentifier':'uk.co.nodeyard.duckylighting','CFBundleExecutable':'DuckyLighting','CFBundleName':'Ducky Lighting','CFBundleDisplayName':'Ducky Lighting','CFBundlePackageType':'APPL','CFBundleIconFile':'DuckyLighting.icns','CFBundleShortVersionString':'0.5.1','CFBundleVersion':'6','LSMinimumSystemVersion':'12.0','NSHighResolutionCapable':True,'NSPrincipalClass':'NSApplication','CFBundleURLTypes':[{'CFBundleURLName':'Ducky Lighting','CFBundleTypeRole':'Viewer','CFBundleURLSchemes':['ducky-lighting']}]}
    (contents/'Info.plist').write_bytes(plistlib.dumps(info))
    # Local preview is ad-hoc signed. Real Developer ID/notarization is a release gate.
    identity=os.environ.get('DUCKY_DEVELOPER_ID','-')
    signing=['codesign','--force','--deep','--sign',identity]
    if identity!='-':signing+=['--options','runtime','--timestamp']
    run([*signing,app]);run(['codesign','--verify','--deep','--strict',app])
    binary=contents/'Resources/companion/ducky-companion';run([binary,'--self-test'])
    image=OUT/f'Ducky-Lighting-macOS-{arch}.dmg';image.unlink(missing_ok=True)
    disk=ROOT/'build/dmg-staging';shutil.rmtree(disk,ignore_errors=True);disk.mkdir();shutil.copytree(app,disk/app.name,symlinks=True);(disk/'Applications').symlink_to('/Applications')
    run(['hdiutil','create','-volname','Ducky Lighting','-srcfolder',disk,'-format','UDZO','-ov',image])
    container=image
elif sys.platform=='win32':
    binary=STAGE/'DuckyLighting/DuckyLighting.exe';run([binary,'--self-test'],env={**os.environ,'DUCKY_SELF_TEST':'1'})
    # NSIS paths are relative to its script; no administrator request or driver installation.
    nsis=shutil.which('makensis') or r'C:\Program Files (x86)\NSIS\makensis.exe'
    run([nsis,ROOT/'packaging/windows/installer.nsi']);container=OUT/'Ducky-Lighting-Windows-x64-Setup.exe'
else:
    binary=STAGE/'DuckyLighting/DuckyLighting';run([binary,'--self-test'])
    deb=ROOT/'build/deb';shutil.rmtree(deb,ignore_errors=True)
    shutil.copytree(STAGE/'DuckyLighting',deb/'opt/ducky-lighting',symlinks=True)
    for dest,src in [('usr/share/applications/ducky-lighting.desktop','packaging/linux/ducky-lighting.desktop'),('usr/lib/udev/rules.d/70-ducky-lighting.rules','packaging/linux/70-ducky-lighting.rules'),('usr/share/icons/hicolor/256x256/apps/ducky-lighting.png','packaging/icon.png'),('DEBIAN/postinst','packaging/linux/postinst')]:
        path=deb/dest;path.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/src,path)
    (deb/'DEBIAN/control').write_text(f'Package: ducky-lighting\nVersion: 0.5.1~experimental1\nSection: utils\nPriority: optional\nArchitecture: {"arm64" if arch=="arm64" else "amd64"}\nMaintainer: Ducky Lighting maintainers\nDepends: libc6 (>= 2.35), libudev1\nDescription: Local Ducky keyboard lighting editor and guarded HID companion\n Experimental cross-platform RGB and fixed-image firmware setup.\n')
    container=OUT/f'Ducky-Lighting-Linux-{arch}.deb';run(['dpkg-deb','--build','--root-owner-group',deb,container])
    shutil.copy2(ROOT/'packaging/linux/70-ducky-lighting.rules',STAGE/'DuckyLighting/70-ducky-lighting.rules')
    portable=OUT/f'Ducky-Lighting-Linux-{arch}.tar.gz'
    with tarfile.open(portable,'w:gz') as t:t.add(STAGE/'DuckyLighting',arcname='DuckyLighting')
record={'version':VERSION,'platform':sys.platform,'architecture':arch,'installer':container.name,'sha256':hashlib.sha256(container.read_bytes()).hexdigest(),'firmware_writer_present':True,'images_bundled':False,'published':False,'physical_validation':False,'prior_transport_evidence':'custom9004 static RGB, onboard static saving, and Wave/Breathing/Reactive/Ripple were physically verified on one DKME2061ST using macOS; packaged runtime and Windows/Linux hardware need separate validation','public_release_ready':False,'remaining_gates':['Developer signing/notarization or code signing','Real-device validation per target OS','Experimental firmware; interrupted-flash recovery unproven']}
(OUT/f'build-{sys.platform}-{arch}.json').write_text(json.dumps(record,indent=2)+'\n')
(OUT/'SHA256SUMS.txt').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in sorted(OUT.iterdir()) if p.suffix in ('.dmg','.exe','.deb','.gz'))+'\n')
print(json.dumps(record,indent=2))
