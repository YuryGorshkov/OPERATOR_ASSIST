#define MyAppName "OPERATOR_ASSIST"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Yury Gorshkov"
#define MyAppURL "https://github.com/YuryGorshkov/OPERATOR_ASSIST"
#define MyAppExeName "OPERATOR_ASSIST.exe"
#define MyPortableRoot "..\..\release\portable\OPERATOR_ASSIST"
#define MyOutputRoot "..\..\release\installer"

[Setup]
AppId={{D5B8745B-D081-4B47-A1C8-237C462D935F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\OPERATOR_ASSIST
DefaultGroupName=OPERATOR_ASSIST
DisableProgramGroupPage=yes
OutputDir={#MyOutputRoot}
OutputBaseFilename=OPERATOR_ASSIST-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MyPortableRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\OPERATOR_ASSIST"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\OPERATOR_ASSIST"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,OPERATOR_ASSIST}"; Flags: nowait postinstall skipifsilent
