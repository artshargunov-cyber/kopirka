#define MyAppName "Копирка"
#define MyAppVersion "1.5.0"
#define MyAppPublisher "Art Shargunov"
#define MyAppURL "https://github.com/artshargunov-cyber/kopirka"
#define MyAppExeName "Kopirka.exe"

[Setup]
AppId={{8A3F2D1C-6E4B-4F7A-9C2D-1B8E5A3F9D7C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\Kopirka
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Не требует прав администратора
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer_output
OutputBaseFilename=KopirkaSetup-{#MyAppVersion}
SetupIconFile=dist\Kopirka\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; Красивый заголовок
WizardImageFile=compiler:WizModernImage-IS.bmp
WizardSmallImageFile=compiler:WizModernSmallImage-IS.bmp
UninstallDisplayName={#MyAppName}
; Сохранять данные пользователя при удалении
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Копируем всё содержимое собранной папки
Source: "dist\Kopirka\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; НЕ удаляем пользовательские данные (список класса)
; Папка %APPDATA%\Kopirka\ остаётся нетронутой
