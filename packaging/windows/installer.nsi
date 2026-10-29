Unicode true
!include "MUI2.nsh"
Name "Ducky Lighting"
OutFile "..\..\release\Ducky-Lighting-Windows-x64-Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\Ducky Lighting"
RequestExecutionLevel user
SetCompressor /SOLID lzma
Icon "..\DuckyLighting.ico"
UninstallIcon "..\DuckyLighting.ico"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\DuckyLighting.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Open Ducky Lighting"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
Section
 SetOutPath "$INSTDIR"
 File /r "..\..\build\packaged\DuckyLighting\*.*"
 WriteUninstaller "$INSTDIR\Uninstall.exe"
 CreateDirectory "$SMPROGRAMS\Ducky Lighting"
 CreateShortCut "$SMPROGRAMS\Ducky Lighting\Ducky Lighting.lnk" "$INSTDIR\DuckyLighting.exe"
 WriteRegStr HKCU "Software\Classes\ducky-lighting" "" "URL:Ducky Lighting"
 WriteRegStr HKCU "Software\Classes\ducky-lighting" "URL Protocol" ""
 WriteRegStr HKCU "Software\Classes\ducky-lighting\shell\open\command" "" '$\"$INSTDIR\DuckyLighting.exe$\" $\"%1$\"'
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DuckyLighting" "DisplayName" "Ducky Lighting"
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DuckyLighting" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
 WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DuckyLighting" "InstallLocation" "$INSTDIR"
SectionEnd
Section "Uninstall"
 ; Remove protocol only if it still belongs to this installation.
 ReadRegStr $0 HKCU "Software\Classes\ducky-lighting\shell\open\command" ""
 StrCmp $0 '$\"$INSTDIR\DuckyLighting.exe$\" $\"%1$\"' 0 +2
 DeleteRegKey HKCU "Software\Classes\ducky-lighting"
 DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\DuckyLighting"
 Delete "$SMPROGRAMS\Ducky Lighting\Ducky Lighting.lnk"
 RMDir "$SMPROGRAMS\Ducky Lighting"
 RMDir /r "$INSTDIR"
 ; Profiles in LocalAppData\Ducky Lighting are deliberately retained.
SectionEnd
