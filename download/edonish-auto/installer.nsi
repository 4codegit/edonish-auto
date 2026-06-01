; ═══════════════════════════════════════════════════════════════════
; eDonish Auto — NSIS Installer Script for Windows
; Build with: makensis installer.nsi
; ═══════════════════════════════════════════════════════════════════

!define APPNAME "eDonish Auto"
!define APPVERSION "2.0.0"
!define APPEXE "edonish-auto.exe"
!define CLIEXE "edonish-auto-cli.exe"
!define COMPANY "Edonish Auto Team"

; Modern UI
!include "MUI2.nsh"

!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"

; Installer pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "Russian"
!insertmacro MUI_LANGUAGE "English"

Name "${APPNAME} ${APPVERSION}"
OutFile "edonish-auto-${APPVERSION}-setup.exe"
InstallDir "$PROGRAMFILES\${APPNAME}"
RequestExecutionLevel admin

Section "Core Files" SecCore
    SectionIn RO
    SetOutPath $INSTDIR

    ; Main executables
    File "dist\windows\${APPEXE}"
    File "dist\windows\${CLIEXE}"

    ; Config files
    File "config.py"
    File "api_client.py"
    File "grade_engine.py"
    File "requirements.txt"

    ; Create directories
    CreateDirectory "$INSTDIR\logs"
    CreateDirectory "$INSTDIR\output"

    ; Desktop shortcut
    CreateShortCut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\${APPEXE}"

    ; Start Menu shortcuts
    CreateDirectory "$SMPROGRAMS\${APPNAME}"
    CreateShortCut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\${APPEXE}"
    CreateShortCut "$SMPROGRAMS\${APPNAME}\CLI Mode.lnk" "$INSTDIR\${CLIEXE}"
    CreateShortCut "$SMPROGRAMS\${APPNAME}\Uninstall.lnk" "$INSTDIR\uninstall.exe"

    ; Write uninstaller
    WriteUninstaller "$INSTDIR\uninstall.exe"

    ; Registry
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
        "DisplayName" "${APPNAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
        "UninstallString" "$INSTDIR\uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
        "DisplayVersion" "${APPVERSION}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}" \
        "Publisher" "${COMPANY}"
SectionEnd

Section "Uninstall"
    ; Remove files
    Delete "$INSTDIR\*.*"
    RMDir /r "$INSTDIR"

    ; Remove shortcuts
    Delete "$DESKTOP\${APPNAME}.lnk"
    Delete "$SMPROGRAMS\${APPNAME}\*.*"
    RMDir "$SMPROGRAMS\${APPNAME}"

    ; Remove registry
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"
SectionEnd
