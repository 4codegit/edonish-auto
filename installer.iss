; ═══════════════════════════════════════════════════════════════════
; eDonish Auto — Inno Setup Installer Script for Windows
; Build with: iscc installer.iss
; ═══════════════════════════════════════════════════════════════════

#define APPNAME "eDonish Auto"
#define APPVERSION "3.0.2"
#define APPEXE "edonish-auto.exe"
#define CLIEXE "edonish-auto-cli.exe"
#define PUBLISHER "Edonish Auto Team"

[Setup]
AppName={#APPNAME}
AppVersion={#APPVERSION}
AppPublisher={#PUBLISHER}
AppPublisherURL=https://edonish.tj
AppSupportURL=https://github.com/4codegit/edonish-auto
DefaultDirName={autopf}\{#APPNAME}
DefaultGroupName={#APPNAME}
UninstallDisplayIcon={app}\{#APPEXE}
OutputDir=dist\windows
OutputBaseFilename=edonish-auto-{#APPVERSION}-setup
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupLogging=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[License]
LicenseFile: LICENSE.txt

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\windows\{#APPEXE}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\windows\{#CLIEXE}"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\logs"
Name: "{app}\output"

[Icons]
Name: "{group}\{#APPNAME}"; Filename: "{app}\{#APPEXE}"
Name: "{group}\CLI Mode"; Filename: "{app}\{#CLIEXE}"
Name: "{group}\{cm:UninstallProgram,{#APPNAME}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#APPNAME}"; Filename: "{app}\{#APPEXE}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#APPEXE}"; Description: "{cm:LaunchProgram,{#APPNAME}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandorsubdirs; Name: "{app}"
