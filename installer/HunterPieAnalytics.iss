; Inno Setup script — HunterPie Analytics desktop app (per-user install).
;
; Per-user (PrivilegesRequired=lowest): installs under %LOCALAPPDATA% with no
; UAC prompt and no admin rights — least privilege, and it doesn't look like a
; system-modifying installer. This script only lays files down, adds shortcuts,
; and registers an uninstaller. (Binaries may be code-signed in CI; currently
; unsigned.)
;
; Build (Windows, repo root, after packaging/build-windows.ps1):
;   iscc installer\HunterPieAnalytics.iss

#define AppName "HunterPie Analytics"
#define AppVersion "1.0.0"
#define AppPublisher "Diegoeyza"
#define AppExe "HunterPieAnalytics.exe"
#define ForkExe "HunterPie-Fork\HunterPie.exe"

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
; NOTE: no blanket [UninstallDelete] of {app} — the companion writes exported
; hunts to {app}\HunterPie-Fork\HuntExports, which is user data and must
; survive an uninstall. Inno still removes every file it installed.

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
#if DirExists(AddBackslash(SourcePath) + "..\dist\HunterPie-Fork")
Name: "companionicon"; Description: "Create a shortcut to the analytics companion (HunterPie)"; GroupDescription: "Shortcuts:"
#endif
Name: "launchapp"; Description: "Launch {#AppName} after setup"; GroupDescription: "Finish:"

[Files]
; The whole PyInstaller onedir build.
Source: "..\dist\HunterPieAnalytics\*"; DestDir: "{app}"; \
  Flags: recursesubdirs createallsubdirs ignoreversion
; End-user guide (plain language; covers the "already have HunterPie" case).
Source: "..\packaging\GETTING_STARTED.txt"; DestDir: "{app}"; Flags: ignoreversion
; REFramework mod (drop-in; installed manually by the user, never auto-copied).
Source: "..\reframework\hunt_dumper.lua"; DestDir: "{app}\HuntDumper"; Flags: ignoreversion
Source: "..\reframework\INSTALL.txt"; DestDir: "{app}\HuntDumper"; Flags: ignoreversion

; HunterPie analytics-export companion (built by CI) — the data source for
; DPS curves. Included only when present in dist/. The standard HunterPie does
; not export, so this is what "already have HunterPie" users should run.
#if DirExists(AddBackslash(SourcePath) + "..\dist\HunterPie-Fork")
Source: "..\dist\HunterPie-Fork\*"; DestDir: "{app}\HunterPie-Fork"; \
  Flags: recursesubdirs createallsubdirs ignoreversion
#endif

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
#if DirExists(AddBackslash(SourcePath) + "..\dist\HunterPie-Fork")
Name: "{group}\HunterPie Analytics companion"; Filename: "{app}\{#ForkExe}"
Name: "{autodesktop}\HunterPie Analytics companion"; Filename: "{app}\{#ForkExe}"; Tasks: companionicon
#endif

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; \
  Flags: nowait postinstall skipifsilent; Tasks: launchapp
#if DirExists(AddBackslash(SourcePath) + "..\dist\HunterPie-Fork")
Filename: "{app}\{#ForkExe}"; Description: "Launch the analytics companion (HunterPie)"; \
  Flags: nowait postinstall skipifsilent unchecked
#endif

[Code]
// Detect an existing (standard) HunterPie so we can tell the user why it won't
// feed the dashboard and point them at the bundled companion.
function ExistingHunterPiePath: String;
begin
  Result := '';
  if FileExists(ExpandConstant('{commonpf}\HunterPie\HunterPie.exe')) then
    Result := ExpandConstant('{commonpf}\HunterPie\HunterPie.exe')
  else if FileExists(ExpandConstant('{commonpf32}\HunterPie\HunterPie.exe')) then
    Result := ExpandConstant('{commonpf32}\HunterPie\HunterPie.exe')
  else if FileExists(ExpandConstant('{localappdata}\Programs\HunterPie\HunterPie.exe')) then
    Result := ExpandConstant('{localappdata}\Programs\HunterPie\HunterPie.exe');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ExistingPath: String;
begin
  if CurStep <> ssPostInstall then
    Exit;
  ExistingPath := ExistingHunterPiePath;
  if (ExistingPath <> '') and FileExists(ExpandConstant('{app}\{#ForkExe}')) then
    MsgBox('You already have HunterPie installed:' + #13#10 + ExistingPath + #13#10 + #13#10 +
           'The standard HunterPie does not save hunt data, so the dashboard cannot read it.' + #13#10 + #13#10 +
           'To record hunts, launch the bundled "HunterPie Analytics companion" ' +
           '(its own Start Menu / desktop shortcut). It is the same HunterPie with ' +
           'local hunt export added, and it reuses your existing HunterPie settings.' + #13#10 + #13#10 +
           'See GETTING_STARTED.txt in the install folder for details.',
           mbInformation, MB_OK);
end;
