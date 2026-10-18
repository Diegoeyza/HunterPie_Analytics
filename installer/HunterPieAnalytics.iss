; Inno Setup script — HunterPie Analytics desktop app (per-user install).
;
; Per-user (PrivilegesRequired=lowest): installs under %LOCALAPPDATA% with no
; UAC prompt and no admin rights — least privilege, and it doesn't look like a
; system-modifying installer. The actual .exe is code-signed in CI; this script
; only lays files down, adds shortcuts, and registers an uninstaller.
;
; Build (Windows, repo root, after packaging/build-windows.ps1):
;   iscc installer\HunterPieAnalytics.iss

#define AppName "HunterPie Analytics"
#define AppVersion "1.0.0"
#define AppPublisher "Diegoeyza"
#define AppExe "HunterPieAnalytics.exe"

[Setup]
AppId={{7C3A2B1E-4F6D-4E2A-9B7C-1A2B3C4D5E6F}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\HunterPie Analytics
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
OutputDir=..\dist
OutputBaseFilename=HunterPieAnalytics-Setup-{#AppVersion}
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "launchapp"; Description: "Launch {#AppName} after setup"; GroupDescription: "Finish:"

[Files]
; The whole PyInstaller onedir build.
Source: "..\dist\HunterPieAnalytics\*"; DestDir: "{app}"; \
  Flags: recursesubdirs createallsubdirs ignoreversion
; REFramework mod (drop-in; installed manually by the user, never auto-copied).
Source: "..\reframework\hunt_dumper.lua"; DestDir: "{app}\HuntDumper"; Flags: ignoreversion
Source: "..\reframework\INSTALL.txt"; DestDir: "{app}\HuntDumper"; Flags: ignoreversion

; HunterPie analytics-export fork (built by CI) — included only when present
; in dist/. Needed by users whose only source is HunterPie.
#if DirExists(AddBackslash(SourcePath) + "..\dist\HunterPie-Fork")
Source: "..\dist\HunterPie-Fork\*"; DestDir: "{app}\HunterPie-Fork"; \
  Flags: recursesubdirs createallsubdirs ignoreversion
#endif

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; \
  Flags: nowait postinstall skipifsilent; Tasks: launchapp

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
