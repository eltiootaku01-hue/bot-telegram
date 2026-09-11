#define MyAppName "Bot Telegram"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "eltiootaku01-hue"
#define MyAppExeName "BotManager.exe"

[Setup]
AppId={{D7E4A1A8-9E0C-4A5D-9E4D-4E8A7B1D0F31}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Bot Telegram
DefaultGroupName={#MyAppName}
OutputDir=..\dist-installer
OutputBaseFilename=BotTelegram-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
Uninstallable=yes

[Files]
Source: "..\dist\BotManager.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\bots\Cari.exe"; DestDir: "{app}\bots"; Flags: ignoreversion
Source: "..\dist\bots\Sunna.exe"; DestDir: "{app}\bots"; Flags: ignoreversion
Source: "..\dist\bots\Cami.exe"; DestDir: "{app}\bots"; Flags: ignoreversion
Source: "..\dist\bots\Chie.exe"; DestDir: "{app}\bots"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: isreadme

[Dirs]
Name: "{app}\data"
Name: "{app}\logs"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir Bot Manager"; Flags: nowait postinstall skipifsilent
