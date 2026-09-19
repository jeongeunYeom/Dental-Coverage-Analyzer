#include "..\packaging\version.iss"
#define AppName "Dental Coverage Analyzer"
#define AppExeName "DentalCoverageAnalyzer.exe"

[Setup]
AppId={{7A834503-7785-43DF-90E1-9BC6600601A8}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
DefaultDirName={autopf}\Dental Coverage Analyzer
DefaultGroupName=Dental Coverage Analyzer
OutputDir=..\dist\installer
OutputBaseFilename=DentalCoverageAnalyzer-Setup-{#AppVersion}
SetupIconFile=..\build\generated\app_icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Uninstallable=yes
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "바탕화면 바로가기 만들기"; GroupDescription: "추가 바로가기:"; Flags: unchecked

[Files]
Source: "..\dist\DentalCoverageAnalyzer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\치아보험 보장분석표 생성기"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\치아보험 보장분석표 생성기"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "치아보험 보장분석표 생성기 실행"; Flags: nowait postinstall skipifsilent
