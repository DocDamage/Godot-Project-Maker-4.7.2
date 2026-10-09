; Inno Setup script for rpggen. Built by tools/package.py (which passes /DAppVersion=... and
; creates dist\LICENSE_AND_NOTICES.txt first).  iscc /DAppVersion=1.2.0 packaging\installer.iss
#ifndef AppVersion
  #define AppVersion "1.2.0"
#endif

[Setup]
AppId={{6C1F6E0A-6A33-4B7E-9C0B-52B7E4A9D1C4}
AppName=rpggen
AppVersion={#AppVersion}
AppPublisher=rpggen contributors
AppPublisherURL=https://github.com/DocDamage/Godot-Project-Maker-4.7.2
AppSupportURL=https://github.com/DocDamage/Godot-Project-Maker-4.7.2/issues
AppUpdatesURL=https://github.com/DocDamage/Godot-Project-Maker-4.7.2/releases
DefaultDirName={autopf}\rpggen
DefaultGroupName=rpggen
; Per-user by default: no administrator rights needed. The user can still choose "all users".
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\dist\LICENSE_AND_NOTICES.txt
OutputDir=..\dist
OutputBaseFilename=rpggen-{#AppVersion}-setup
SetupIconFile=rpggen.ico
UninstallDisplayIcon={app}\rpggen.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\rpggen\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\rpggen"; Filename: "{app}\rpggen.exe"
Name: "{autodesktop}\rpggen"; Filename: "{app}\rpggen.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\rpggen.exe"; Description: "Start rpggen"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Settings, caches and generated projects are left alone; only the program folder is removed.
Type: filesandordirs; Name: "{app}"
