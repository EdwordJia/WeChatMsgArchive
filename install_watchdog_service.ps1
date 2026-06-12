# Watchdog 服务安装脚本（Windows Service）
# 使用 nssm 将 wechat_realtime_monitor.py 注册为 Windows 服务
#
# 前提：
#   1. 以管理员身份运行 PowerShell
#   2. 已安装 nssm（本脚本会自动下载）
#
# 用法：
#   .\install_watchdog_service.ps1

$ErrorActionPreference = "Stop"

# 配置参数
$ServiceName = "WeChatRealtimeMonitor"
$ProjectRoot = "D:\develoment_home\project_home\WeChatMsgArchive"
$PythonPath = "$ProjectRoot\venv\Scripts\python.exe"
$ScriptPath = "$ProjectRoot\wechat_realtime_monitor_v2.py"
$LogOut = "$ProjectRoot\output\realtime_monitor.out.log"
$LogErr = "$ProjectRoot\output\realtime_monitor.err.log"
$NssmPath = "$ProjectRoot\tools\nssm.exe"

Write-Host "=== Watchdog 服务安装 ===" -ForegroundColor Cyan
Write-Host ""

# 检查管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "请以管理员身份运行此脚本"
    Write-Host "右键点击 PowerShell -> 以管理员身份运行" -ForegroundColor Yellow
    exit 1
}

# 检查 Python 虚拟环境
if (-not (Test-Path $PythonPath)) {
    Write-Error "Python 虚拟环境未找到: $PythonPath"
    Write-Host "请先运行: python -m venv venv" -ForegroundColor Yellow
    exit 1
}

# 检查监控脚本
if (-not (Test-Path $ScriptPath)) {
    Write-Error "监控脚本未找到: $ScriptPath"
    exit 1
}

# 创建输出目录
$OutputDir = "$ProjectRoot\output"
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

# 创建工具目录
$ToolsDir = "$ProjectRoot\tools"
if (-not (Test-Path $ToolsDir)) {
    New-Item -ItemType Directory -Path $ToolsDir | Out-Null
}

# 下载 nssm（如果不存在）
if (-not (Test-Path $NssmPath)) {
    Write-Host "下载 nssm..." -ForegroundColor Yellow
    $nssmZip = "$ToolsDir\nssm.zip"
    $nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"

    try {
        Invoke-WebRequest -Uri $nssmUrl -OutFile $nssmZip -UseBasicParsing
      Expand-Archive -Path $nssmZip -DestinationPath $ToolsDir -Force

        # 根据系统架构选择正确的 nssm.exe
        if ([Environment]::Is64BitOperatingSystem) {
            Copy-Item "$ToolsDir\nssm-2.24\win64\nssm.exe" $NssmPath -Force
        } else {
            Copy-Item "$ToolsDir\nssm-2.24\win32\nssm.exe" $NssmPath -Force
        }

        Remove-Item $nssmZip -Force
        Remove-Item "$ToolsDir\nssm-2.24" -Recurse -Force
        Write-Host "nssm 下载完成" -ForegroundColor Green
    } catch {
     Write-Error "下载 nssm 失败: $_"
        Write-Host "请手动下载: https://nssm.cc/download" -ForegroundColor Yellow
        exit 1
    }
}

# 检查服务是否已存在
$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "服务已存在，正在删除..." -ForegroundColor Yellow
    & $NssmPath stop $ServiceName
    & $NssmPath remove $ServiceName confirm
    Start-Sleep -Seconds 2
}

Write-Host "安装服务..." -ForegroundColor Green

# 1. 安装服务
& $NssmPath install $ServiceName $PythonPath $ScriptPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "服务安装失败"
    exit 1
}

# 2. 配置工作目录
& $NssmPath set $ServiceName AppDirectory $ProjectRoot

# 3. 配置日志
& $NssmPath set $ServiceName AppStdout $LogOut
& $NssmPath set $ServiceName AppStderr $LogErr
& $NssmPath set $ServiceName AppRotateFiles 1
& $NssmPath set $ServiceName AppRotateBytes 10485760  # 10MB

# 4. 配置启动类型（自动启动）
& $NssmPath set $ServiceName Start SERVICE_AUTO_START

# 5. 配置环境变量（如果需要）
# & $NssmPath set $ServiceName AppEnvironmentExtra "PYTHONUNBUFFERED=1"

Write-Host ""
Write-Host "=== 服务安装完成 ===" -ForegroundColor Green
Write-Host "
Write-Host "启动服务..." -ForegroundColor Cyan
& $NssmPath start $ServiceName

Start-Sleep -Seconds 3

# 检查服务状态
$status = & $NssmPath status $ServiceName
Write-Host "服务状态: $status" -ForegroundColor $(if ($status -eq "SERVICE_RUNNING") { "Green" } else { "Red" })

Write-Host ""
Write-Host "=== 验证步骤 ===" -ForegroundColor Cyan
Write-Host "1. 检查服务状态："
Write-Host "   Get-Service -Name '$ServiceName'"
Write-Host ""
Write-Host "2. 查看实时日志："
Write-Host "   Get-Content '$LogOut' -Wait"
Write-Host ""
Write-Host "3. 测试监控功能："
Write-Host "   - 在微信发送一条消息"
Write-Host "   - 等待 5-10 秒"
Write-Host "   - 检查日志是否有 '检测到数据库变化' 记录"
Write-Host ""
Write-Host "4. 检查解密数据库更新："
Write-Host "   Get-Item '$ProjectRoot\output\decrypted_db\Multi\MSG*.db' | Select-Object Name, LastWriteTime"
Write-Host ""
Write-Host "=== 管理命令 ===" -ForegroundColor Cyan
Write-Host "- 查看状态: $NssmPath status $ServiceName"
Write-Host "- 启动服务: $NssmPath start $ServiceName"
Write-Host "- 停止服务: $NssmPath stop $ServiceName"
Write-Host "- 重启服务: $NssmPath restart $ServiceName"
Write-Host "- 删除服务: $NssmPath remove $ServiceName confirm"
Write-Host ""
Write-Host "=== 故障排查 ===" -ForegroundColor Cyan
Write-Host "- 服务无法启动: 检查 Windows 事件查看器（eventvwr.msc）"
Write-Host "- Python 错误: 查看 $LogErr"
Write-Host "- 监控无反应: 确认微信正在运行，数据库路径正确"
Write-Host "- 权限问题: 确认服务用户有读取微信数据库目录的权限"
Write-Host ""
