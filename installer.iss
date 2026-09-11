; BOT-IA Windows installer
#define MyAppName "BOT-IA"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "BOT-IA"
#define MyAppExeName "BOT-IA.exe"

[Setup]
AppId={{9D2C5E3C-6F1C-4B8A-8D4A-9F10A0B1C200}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\BOT-IA
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=release
OutputBaseFilename=BOT-IA-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "release\BOT-IA.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "release\BOT-IA-Core.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "release\config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "release\biblioteca\*"; DestDir: "{app}\biblioteca"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "release\.env.example"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{autodesktop}\BOT-IA"; Filename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\BOT-IA"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar BOT-IA"; Flags: nowait postinstall skipifsilent
