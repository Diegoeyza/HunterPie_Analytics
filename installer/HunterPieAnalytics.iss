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
#define AppVersion "1.0.10"
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
// --- WebView2 Evergreen runtime ---------------------------------------------
// The dashboard window uses WebView2 (Edge). It ships with Windows 11 and most
// updated Windows 10, but not guaranteed. Detect it and, only if missing,
// download and install the Evergreen Bootstrapper so the window can't fail.
const
  WebView2KeyMachine = 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2KeyUser = 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2Url = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';
  WebView2File = 'MicrosoftEdgeWebview2Setup.exe';

var
  DownloadPage: TDownloadWizardPage;

function WebView2Installed: Boolean;
var
  Version: String;
begin
  Version := '';
  if not RegQueryStringValue(HKLM, WebView2KeyMachine, 'pv', Version) then
    RegQueryStringValue(HKCU, WebView2KeyUser, 'pv', Version);
  Result := (Version <> '') and (Version <> '0.0.0.0');
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing),
    SetupMessage(msgPreparingDesc), nil);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID <> wpReady) or WebView2Installed then
    Exit;
  DownloadPage.Clear;
  DownloadPage.Add(WebView2Url, WebView2File, '');
  DownloadPage.Show;
  try
    try
      DownloadPage.Download;
    except
      if MsgBox('Could not download the WebView2 runtime. The dashboard window ' +
                'will not open without it.' + #13#10 + #13#10 +
                'Install it manually from ' + WebView2Url + ' then relaunch ' +
                'HunterPie Analytics.' + #13#10 + #13#10 +
                'Continue the installation anyway?', mbError, MB_YESNO) = IDNO then
        Result := False;
    end;
  finally
    DownloadPage.Hide;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  InstallerPath: String;
begin
  Result := '';
  if WebView2Installed then
    Exit;
  InstallerPath := ExpandConstant('{tmp}\' + WebView2File);
  if FileExists(InstallerPath) then
    // Per-user install when not elevated (no UAC); best effort, non-fatal.
    Exec(InstallerPath, '/silent /install', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
end;

// --- Existing HunterPie detection -------------------------------------------
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

// --- Carry over settings from an existing HunterPie --------------------------
// HunterPie keeps its settings in its INSTALL folder (config.json, the
// internal\ state, and any user Modules\ / Themes\), not under %APPDATA%. So
// when an existing install is found and the bundled companion has never run,
// copy those across so the user keeps their overlays, theme and modules. The
// original install is left untouched (acts as a backup). Never overwrite once
// the companion already has a config.
const
  FA_DIRECTORY = $10;

function CopyDirRecursive(const Src, Dst: String): Boolean;
var
  FindRec: TFindRec;
  SrcPath, DstPath: String;
begin
  Result := True;
  if not DirExists(Dst) then
    ForceDirectories(Dst);
  if not FindFirst(AddBackslash(Src) + '*', FindRec) then
    Exit;
  try
    repeat
      if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
      begin
        SrcPath := AddBackslash(Src) + FindRec.Name;
        DstPath := AddBackslash(Dst) + FindRec.Name;
        if (FindRec.Attributes and FA_DIRECTORY) <> 0 then
          CopyDirRecursive(SrcPath, DstPath)
        else
          FileCopy(SrcPath, DstPath, False);
      end;
    until not FindNext(FindRec);
  finally
    FindClose(FindRec);
  end;
end;

// Returns the source install folder if settings were copied, else ''.
function ImportExistingSettings(const DestFork: String): String;
var
  SrcDir, DstDir, Item: String;
  I: Integer;
  SubDirs: array[0..2] of String;
begin
  Result := '';
  if FileExists(AddBackslash(DestFork) + 'config.json') then
    Exit;  // companion already configured — never overwrite the user's setup
  SrcDir := ExtractFileDir(ExistingHunterPiePath);
  if (SrcDir = '') or not FileExists(AddBackslash(SrcDir) + 'config.json') then
    Exit;
  DstDir := DestFork;
  ForceDirectories(DstDir);
  FileCopy(AddBackslash(SrcDir) + 'config.json', AddBackslash(DstDir) + 'config.json', False);
  if FileExists(AddBackslash(SrcDir) + 'config.json.bak') then
    FileCopy(AddBackslash(SrcDir) + 'config.json.bak', AddBackslash(DstDir) + 'config.json.bak', False);
  SubDirs[0] := 'internal';
  SubDirs[1] := 'Modules';
  SubDirs[2] := 'Themes';
  for I := 0 to 2 do
  begin
    Item := AddBackslash(SrcDir) + SubDirs[I];
    if DirExists(Item) then
      CopyDirRecursive(Item, AddBackslash(DstDir) + SubDirs[I]);
  end;
  Result := SrcDir;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ExistingPath, ImportedFrom: String;
begin
  if CurStep <> ssPostInstall then
    Exit;
  if not FileExists(ExpandConstant('{app}\{#ForkExe}')) then
    Exit;
  ExistingPath := ExistingHunterPiePath;
  if ExistingPath = '' then
    Exit;
  ImportedFrom := ImportExistingSettings(ExpandConstant('{app}\HunterPie-Fork'));
  if ImportedFrom <> '' then
    MsgBox('You already have HunterPie installed:' + #13#10 + ExistingPath + #13#10 + #13#10 +
           'Your settings (overlays, theme, modules) have been copied into the bundled ' +
           '"Analytics companion", so it starts exactly like your current HunterPie. ' +
           'Your existing installation is left untouched.' + #13#10 + #13#10 +
           'The standard HunterPie does not save hunt data, so launch the bundled ' +
           '"HunterPie Analytics companion" shortcut to record hunts for the dashboard.' + #13#10 + #13#10 +
           'See GETTING_STARTED.txt in the install folder for details.',
           mbInformation, MB_OK)
  else
    MsgBox('You already have HunterPie installed:' + #13#10 + ExistingPath + #13#10 + #13#10 +
           'The standard HunterPie does not save hunt data, so the dashboard cannot read it.' + #13#10 + #13#10 +
           'To record hunts, launch the bundled "HunterPie Analytics companion" ' +
           '(its own Start Menu / desktop shortcut). It is the same HunterPie with ' +
           'local hunt export added.' + #13#10 + #13#10 +
           'See GETTING_STARTED.txt in the install folder for details.',
           mbInformation, MB_OK);
end;
