#ifndef AppVersion
  #error AppVersion must be supplied by build_installer.ps1
#endif
[Setup]
AppId={{ABAA8717-87B1-4D77-90A1-64518210F92B}
AppName=LightMq
AppVersion={#AppVersion}
AppPublisher=PRANATHEESH S
AppVerName=LightMq {#AppVersion}
DefaultDirName={localappdata}\Programs\LightMq
DefaultGroupName=LightMq
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\..\release
OutputBaseFilename=LightMq-Setup-{#AppVersion}-x64
SetupIconFile=..\..\src\browser\resources\lightmq.ico
UninstallDisplayIcon={app}\LightMq.exe
LicenseFile=..\..\LICENSE
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=no

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\..\dist\LightMq\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\LightMq"; Filename: "{app}\LightMq.exe"
Name: "{userdesktop}\LightMq"; Filename: "{app}\LightMq.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\LightMq.exe"; Description: "Launch LightMq"; Flags: nowait postinstall skipifsilent

; Deliberately no user-data, registry, or profile removal directives.
