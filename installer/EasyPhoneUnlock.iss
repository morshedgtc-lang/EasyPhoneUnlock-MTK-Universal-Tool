; EasyPhoneUnlock — Windows installer (Inno Setup 6).
; Build the EXE first (build_windows.ps1 -> dist\EasyPhoneUnlock.exe), then:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\EasyPhoneUnlock.iss
; Output: installer\Output\EasyPhoneUnlock-Setup.exe

#define AppName "EasyPhoneUnlock MTK Universal Tool"
#define AppShort "EasyPhoneUnlock"
#define AppVersion "2.0.0"
#define AppPublisher "EasyPhoneUnlock"
#define AppExe "EasyPhoneUnlock.exe"

[Setup]
AppId={{B6E1B6A0-EPU0-4A10-9C21-EASYPHONEUNLK01}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppShort}
DefaultGroupName={#AppShort}
UninstallDisplayIcon={app}\{#AppExe}
OutputDir=Output
OutputBaseFilename={#AppShort}-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "driver"; Description: "Install MediaTek USB VCOM / preloader drivers"; GroupDescription: "Drivers:"; Flags: unchecked

[Files]
; The built single-file app.
Source: "..\dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion
; Optional bundled driver package — drop installers into installer\drivers\ before building.
; (Operator supplies the driver package; nothing proprietary is shipped by default.)
Source: "drivers\*"; DestDir: "{app}\drivers"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppShort}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppShort}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; Optional driver install step (only if a driver installer is bundled).
Filename: "{app}\drivers\install_drivers.bat"; Description: "Installing USB drivers"; \
  Flags: runascurrentuser shellexec waituntilterminated skipifdoesntexist; Tasks: driver
; Offer to launch after install.
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppShort}"; Flags: nowait postinstall skipifsilent
