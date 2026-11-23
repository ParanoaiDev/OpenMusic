; Inno Setup: the installer of OpenMusic for Windows, made from dist\OpenMusic.
;   iscc /DVersion=0.9.0 packaging\windows\OpenMusic.iss
#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppId={{6F0B7C0E-3C5E-4B8B-9E0E-0A7D3F6B2C41}
AppName=OpenMusic
AppVersion={#Version}
AppPublisher=ParanoaiDev
AppPublisherURL=https://github.com/ParanoaiDev/OpenMusic
DefaultDirName={autopf}\OpenMusic
DefaultGroupName=OpenMusic
DisableProgramGroupPage=yes
; Installs for the current user, without asking for administrator rights.
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=OpenMusic-{#Version}-windows-setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\OpenMusic.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\..\dist\OpenMusic\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\OpenMusic"; Filename: "{app}\OpenMusic.exe"
Name: "{autodesktop}\OpenMusic"; Filename: "{app}\OpenMusic.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\OpenMusic.exe"; Description: "{cm:LaunchProgram,OpenMusic}"; Flags: nowait postinstall skipifsilent
