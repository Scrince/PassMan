#define AppName "PassMan"

#ifndef AppVersion
  #define AppVersion "1.0.7"
#endif

#ifndef AppExePath
  #define AppExePath "..\release\v1.0.7\windows\PassMan.exe"
#endif

[Setup]
AppId={{9eaba8a5-bf76-47d7-a9bf-7d518e65aa92}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=PassMan
DefaultDirName={autopf}\PassMan
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\PassMan.exe
OutputDir=..\dist
OutputBaseFilename=PassMan-Setup-{#AppVersion}
SetupIconFile=..\src\assets\passman_icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#AppExePath}"; DestDir: "{app}"; DestName: "PassMan.exe"; Flags: ignoreversion

[Icons]
Name: "{group}\PassMan"; Filename: "{app}\PassMan.exe"
Name: "{autodesktop}\PassMan"; Filename: "{app}\PassMan.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PassMan.exe"; Description: "Launch PassMan"; Flags: postinstall nowait skipifsilent
