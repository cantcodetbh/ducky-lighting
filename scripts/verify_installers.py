"""Exercise native containers/installers on disposable CI runners, with NoUSB self-tests."""
from pathlib import Path
import json,os,plistlib,shutil,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
if os.environ.get('GITHUB_ACTIONS')!='true':
    raise SystemExit('Installer lifecycle checks run only on disposable GitHub Actions runners.')
def run(args,**kwargs):
    return subprocess.run([str(a) for a in args],check=True,**kwargs)
result={'platform':sys.platform,'USB_calls':0,'firmware_writes':0}
def verify_worker(directory):
    worker=directory/('DuckyFirmwareWorker.exe' if sys.platform=='win32' else 'DuckyFirmwareWorker')
    data=json.loads(subprocess.check_output([str(worker),'--self-test'],text=True))
    assert data['ok'] and data['actual_USB_calls']==0
    assert data['hid_backend']==('hidraw' if sys.platform.startswith('linux') else 'hid')
    result['installed_firmware_worker_verified']=True
if sys.platform=='darwin':
    image=next((ROOT/'release').glob('*.dmg'))
    mount=ROOT/'build/installer-mount';mount.mkdir(exist_ok=True)
    run(['hdiutil','attach','-readonly','-nobrowse','-mountpoint',mount,image])
    try:
        app=mount/'Ducky Lighting.app'
        run(['codesign','--verify','--deep','--strict',app])
        info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
        assert info['CFBundleURLTypes'][0]['CFBundleURLSchemes']==['ducky-lighting']
        run([app/'Contents/Resources/companion/ducky-companion','--self-test'])
        verify_worker(app/'Contents/Resources/companion')
        assert (mount/'Applications').is_symlink()
        result.update(container_mounted=True,signature_verified=True,frozen_self_test=True,url_scheme_declared=True)
    finally:run(['hdiutil','detach',mount])
elif sys.platform=='win32':
    import winreg
    installer=ROOT/'release/Ducky-Lighting-Windows-x64-Setup.exe'
    install=Path(os.environ['LOCALAPPDATA'])/'Programs/Ducky Lighting'
    assert not install.exists(),'Disposable runner unexpectedly has an installation.'
    run([installer,'/S'])
    try:
        run([install/'DuckyLighting.exe','--self-test'])
        verify_worker(install)
        keypath=r'Software\Classes\ducky-lighting\shell\open\command'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,keypath) as key:
            command=winreg.QueryValueEx(key,'')[0]
        assert command==f'"{install / "DuckyLighting.exe"}" "%1"',command
        result.update(installed=True,frozen_self_test=True,url_handler_registered=True)
    finally:
        run([install/'Uninstall.exe','/S'])
        for _ in range(100):
            if not (install/'DuckyLighting.exe').exists():break
            time.sleep(.1)
        assert not (install/'DuckyLighting.exe').exists(),'Uninstall did not remove app.'
        try:winreg.OpenKey(winreg.HKEY_CURRENT_USER,keypath)
        except FileNotFoundError:pass
        else:raise AssertionError('Uninstall left URL handler behind.')
        result['uninstall_verified']=True
else:
    package=next((ROOT/'release').glob('*.deb'))
    run(['sudo','dpkg','--install',package])
    try:
        run(['/opt/ducky-lighting/DuckyLighting','--self-test'])
        verify_worker(Path('/opt/ducky-lighting'))
        desktop=Path('/usr/share/applications/ducky-lighting.desktop').read_text()
        assert 'x-scheme-handler/ducky-lighting' in desktop
        assert '0416' in Path('/usr/lib/udev/rules.d/70-ducky-lighting.rules').read_text()
        result.update(installed=True,frozen_self_test=True,url_handler_declared=True)
    finally:
        run(['sudo','dpkg','--remove','ducky-lighting'])
        assert not Path('/opt/ducky-lighting/DuckyLighting').exists()
        assert not Path('/usr/share/applications/ducky-lighting.desktop').exists()
        result['uninstall_verified']=True
(ROOT/'release/installer-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
