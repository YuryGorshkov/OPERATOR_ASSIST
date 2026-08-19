#ifndef MyAppName
  #define MyAppName "OPERATOR_ASSIST"
#endif
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#ifndef MyAppPublisher
  #define MyAppPublisher "Yury Gorshkov"
#endif
#ifndef MyAppURL
  #define MyAppURL "https://github.com/YuryGorshkov/OPERATOR_ASSIST"
#endif
#ifndef MyAppExeName
  #define MyAppExeName "OPERATOR_ASSIST.exe"
#endif
#ifndef MyPortableRoot
  #define MyPortableRoot "..\..\release\portable\OPERATOR_ASSIST"
#endif
#ifndef MyOutputRoot
  #define MyOutputRoot "..\..\release\installer"
#endif
#ifndef MyOutputBaseFilename
  #define MyOutputBaseFilename "OPERATOR_ASSIST-Setup"
#endif

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
OutputBaseFilename={#MyOutputBaseFilename}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\..\assets\operator_assist.ico

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
