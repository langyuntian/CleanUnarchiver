; ---------------------------------------------------------------------------
; 干净解压工具 CleanUnarchiver —— Windows 安装程序脚本
; 开发公司：深圳市研融科技有限公司
; 知识产权：归深圳市研融科技有限公司所有
; 编译方式："C:\Program Files (x86)\Inno Setup 6\ISCC.exe" setup_cleanunarchiver.iss
; ---------------------------------------------------------------------------

#define MyAppName "干净解压工具"
#define MyAppNameEn "CleanUnarchiver"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "深圳市研融科技有限公司"
#define MyAppExeName "CleanUnarchiver.exe"
#define MyAppCopyright "Copyright (C) 2026 深圳市研融科技有限公司"

[Setup]
AppId={{0C4E9B6A-2F7D-4A3E-9B1C-5D8A3E6F7A21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://www.yanrongtech.com
AppCopyright={#MyAppCopyright}
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoCopyright={#MyAppCopyright}
VersionInfoDescription={#MyAppName} - 无广告、无捆绑的本地解压缩工具
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}.0
VersionInfoTextVersion={#MyAppVersion}

; 安装位置：Program Files 下的研融科技目录
DefaultDirName={autopf}\YanrongTech\{#MyAppNameEn}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; 安装界面
WizardStyle=modern
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
LicenseFile=LICENSE.txt

; 输出
OutputDir=installer
OutputBaseFilename=研融科技_干净解压工具_Setup_{#MyAppVersion}
SetupLogging=yes
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标:"; Flags: unchecked
Name: "addcontextmenu"; Description: "在文件右键菜单中添加“用 干净解压工具 解压”"; GroupDescription: "右键菜单集成:"
Name: "assocdefault"; Description: "将 zip / 7z / rar / tar / 等设为默认解压工具"; GroupDescription: "文件关联:"

[Files]
Source: "{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
; 内置 UnRAR 工具（RARLAB 官方免费版，随软件分发，用于 RAR 解压）
Source: "UnRAR.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "UnRAR_LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Registry]
; ---- 压缩包类型（ProgID）与右键动作（写入当前用户 HKCU，卸载可完全清理）----
Root: HKCU; Subkey: "Software\Classes\CleanUnarchiver.File"; ValueType: string; ValueName: ""; ValueData: "干净解压工具压缩包"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\CleanUnarchiver.File\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\CleanUnarchiver.File\shell\open"; ValueType: string; ValueName: ""; ValueData: "用 {#MyAppName} 打开"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\CleanUnarchiver.File\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\CleanUnarchiver.File\shell\CleanUnarchiverHere"; ValueType: string; ValueName: ""; ValueData: "用 {#MyAppName} 解压到当前目录"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\CleanUnarchiver.File\shell\CleanUnarchiverHere\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --extract-here ""%1"""; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\CleanUnarchiver.File\shell\CleanUnarchiverInto"; ValueType: string; ValueName: ""; ValueData: "用 {#MyAppName} 解压到同名文件夹"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\CleanUnarchiver.File\shell\CleanUnarchiverInto\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --extract-into ""%1"""; Flags: uninsdeletekey

; ---- 各压缩扩展名的右键菜单（独立于默认关联，安装后即可用）----
; 右键动作：解压到当前目录 / 解压到同名文件夹（在下方 [Code] 中按扩展名循环写入）
; ---- 各压缩扩展名的默认关联（设为系统默认解压工具，见 [Code]）----

[Code]
var
  RightMenuExts: array of string;

function InitializeSetup(): Boolean;
begin
  RightMenuExts := ['zip', 'zipx', '7z', 'rar', 'rev', 'tar', 'gz', 'bz2', 'xz',
                    'zst', 'lz4', 'cab', 'tgz', 'tbz2', 'txz'];
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  i: Integer;
  Root: string;
  CmdHere, CmdInto: string;
  Ext: string;
begin
  if CurStep = ssPostInstall then
  begin
    Root := 'Software\Classes';
    CmdHere := '"' + ExpandConstant('{app}\{#MyAppExeName}') + '" --extract-here "%1"';
    CmdInto := '"' + ExpandConstant('{app}\{#MyAppExeName}') + '" --extract-into "%1"';

    // 1) 右键菜单：解压到当前目录 / 解压到同名文件夹
    if WizardIsTaskSelected('addcontextmenu') then
    begin
      for i := 0 to GetArrayLength(RightMenuExts) - 1 do
      begin
        Ext := RightMenuExts[i];
        RegWriteStringValue(HKCU, Root + '\' + Ext + '\shell\CleanUnarchiverHere',
                            '', '用 干净解压工具 解压到当前目录');
        RegWriteStringValue(HKCU, Root + '\' + Ext + '\shell\CleanUnarchiverHere\command',
                            '', CmdHere);
        RegWriteStringValue(HKCU, Root + '\' + Ext + '\shell\CleanUnarchiverInto',
                            '', '用 干净解压工具 解压到同名文件夹');
        RegWriteStringValue(HKCU, Root + '\' + Ext + '\shell\CleanUnarchiverInto\command',
                            '', CmdInto);
      end;
    end;

    // 2) 设为系统默认解压工具（文件关联到本工具）
    if WizardIsTaskSelected('assocdefault') then
    begin
      for i := 0 to GetArrayLength(RightMenuExts) - 1 do
        RegWriteStringValue(HKCU, Root + '\' + RightMenuExts[i], '',
                            'CleanUnarchiver.File');
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  i: Integer;
  Root, Ext: string;
begin
  if CurUninstallStep = usUninstall then
  begin
    Root := 'Software\Classes';
    for i := 0 to GetArrayLength(RightMenuExts) - 1 do
    begin
      Ext := RightMenuExts[i];
      RegDeleteKeyIncludingSubkeys(HKCU, Root + '\' + Ext + '\shell\CleanUnarchiverHere');
      RegDeleteKeyIncludingSubkeys(HKCU, Root + '\' + Ext + '\shell\CleanUnarchiverInto');
      // 若默认关联指向本工具，卸载时移除（恢复系统原有默认）
      RegDeleteValue(HKCU, Root + '\' + Ext, '');
    end;
  end;
end;

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即运行 {#MyAppName}"; Flags: nowait postinstall skipifsilent

; 中文界面文本（覆盖英文默认值）
[Messages]
SetupAppTitle=安装 {#MyAppName}
SetupWindowTitle=安装 - {#MyAppName}
WelcomeLabel1=欢迎使用 {#MyAppName} 安装向导
WelcomeLabel2=本向导将引导您完成 {#MyAppName} 的安装。%n%n本软件由深圳市研融科技有限公司开发，软件著作权及知识产权归深圳市研融科技有限公司所有。%n%n点击“下一步”继续。
SelectDirLabel3=安装程序将把 {#MyAppName} 安装到以下文件夹。%n%n点击“下一步”继续，或点击“浏览”选择其他文件夹。
SelectTasksLabel2=选择您希望安装程序执行的附加任务，然后点击“下一步”。
ReadyLabel1=准备安装
ReadyLabel2a=点击“安装”开始安装。如需检查或更改任何安装设置，请点击“上一步”。
FinishedHeadingLabel=正在完成 {#MyAppName} 安装向导
FinishedLabel=已成功安装 {#MyAppName}。%n%n点击“完成”退出安装向导。
FinishedLabelNoIcons={#MyAppName} 已成功安装。%n%n点击“完成”退出安装向导。
ClickFinish=点击“完成”退出安装向导。
BeveledLabel=深圳市研融科技有限公司
UninstallAppFullTitle=卸载 {#MyAppName}
UninstallAppTitle=卸载 {#MyAppName}
DiskSpaceMBLabel=至少需要 {mb} MB 的磁盘空间。
SelectDirBrowseLabel=要继续，请点击“下一步”。如果需要选择其他文件夹，请点击“浏览”。
