#define MyAppName "Santri Exportações"
#define MyAppVersion "2.2.1"
#define MyAppPublisher "Grupo SH"
#define MyAppExeName "Santri Exportações.exe"

[Setup]
AppId={{F88902F1-B811-4D76-A9D1-2F2AD5E2195A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Santri Exportações
DefaultGroupName=Grupo SH
OutputDir=..\dist
OutputBaseFilename=Santri-Exportacoes-Setup-{#MyAppVersion}
SetupIconFile=..\src\santri_automation\resources\ui\assets\sh-app-icon.ico
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\santri-exportacoes-release.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\santri-exportacoes-sbom.cdx.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Grupo SH\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: checkedonce

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar {#MyAppName}"; Flags: nowait postinstall skipifsilent
