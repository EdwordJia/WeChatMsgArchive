# Watchdog Service Installation Script
# Install wechat_realtime_monitor_v2.py as Windows Service using nssm

$ErrorActionPreference = "Stop"

# Configuration
$ServiceName = "WeChatRealtimeMonitor"
$ProjectRoot = "D:\develoment_home\project_home\WeChatMsgArchive"
$PythonPath = "$ProjectRoot\venv\Scripts\python.exe"
$ScriptPath = "$ProjectRoot\wechat_realtime_monitor_v2.py"
$LogOut = "$ProjectRoot\output\realtime_monitor.out.log"
$LogErr = "$ProjectRoot\output\realtime_monitor.err.log"
$NssmPath = "$ProjectRoot\tools\nssm.exe"

Write-Host "=== Installing Watchdog Service ===" -ForegroundColor Cyan

# Check admin privileges
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "Please run as Administrator"
    exit 1
}

# Check Python
if (-not (Test-Path $PythonPath)) {
    Write-Error "Python not found: $PythonPath"
    exit 1
}

# Check script
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Script not found: $ScriptPath"
    exit 1
}

# Create directories
New-Item -ItemType Directory -Path "$ProjectRoot\output" -Force | Out-Null
New-Item -ItemType Directory -Path "$ProjectRoot\tools" -Force | Out-Null

# Download nssm if needed
if (-not (Test-Path $NssmPath)) {
    Write-Host "Downloading nssm..." -ForegroundColor Yellow
    $nssmZip = "$ProjectRoot\tools\nssm.zip"
    $nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
    
    try {
        Invoke-WebRequest -Uri $nssmUrl -OutFile $nssmZip -UseBasicParsing
        Expand-Archive -Path $nssmZip -DestinationPath "$ProjectRoot\tools" -Force
        
        if ([Environment]::Is64BitOperatingSystem) {
          Copy-Item "$ProjectRoot\tools\nssm-2.24\win64\nssm.exe" $NssmPath -Force
        } else {
            Copy-Item "$ProjectRoot\tools\nssm-2.24\win32\nssm.exe" $NssmPath -Force
        }
        
      Remove-Item $nssmZip -Force
        Remove-Item "$ProjectRoot\tools\nssm-2.24" -Recurse -Force
        Write-Host "nssm downloaded" -ForegroundColor Green
    } catch {
        Write-Error "Failed to download nssm: $_"
        Write-Host "Please download manually: https://nssm.cc/download" -ForegroundColor Yellow
        exit 1
    }
}

# Remove existing service
$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "Removing existing service..." -ForegroundColor Yellow
    & $NssmPath stop $ServiceName
    & $NssmPath remove $ServiceName confirm
    Start-Sleep -Seconds 2
}

Write-Host "Installing service..." -ForegroundColor Green

# Install service
& $NssmPath install $ServiceName $PythonPath $ScriptPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "Service installation failed"
    exit 1
}

# Configure service
& $NssmPath set $ServiceName AppDirectory $ProjectRoot
& $NssmPath set $ServiceName AppStdout $LogOut
& $NssmPath set $ServiceName AppStderr $LogErr
& $NssmPath set $ServiceName AppRotateFiles 1
& $NssmPath set $ServiceName AppRotateBytes 10485760
& $NssmPath set $ServiceName Start SERVICE_AUTO_START

Write-Host ""
Write-Host "=== Service Installed ===" -ForegroundColor Green
Write-Host ""
Write-Host "Starting service..." -ForegroundColor Cyan
& $NssmPath start $ServiceName

Start-Sleep -Seconds 3

$status = & $NssmPath status $ServiceName
Write-Host "Service status: $status" -ForegroundColor $(if ($status -eq "SERVICE_RUNNING") { "Green" } else { "Red" })

Write-Host ""
Write-Host "=== Verification ===" -ForegroundColor Cyan
Write-Host "1. Check service: Get-Service -Name '$ServiceName'"
Write-Host "2. View logs: Get-Content '$LogOut' -Wait"
Write-Host "3. Test: Send a WeChat message and check logs"
Write-Host ""
Write-Host "=== Management ===" -ForegroundColor Cyan
Write-Host "- Status: $NssmPath status $ServiceName"
Write-Host "- Start: $NssmPath start $ServiceName"
Write-Host "- Stop: $NssmPath stop $ServiceName"
Write-Host "- Restart: $NssmPath restart $ServiceName"
Write-Host "- Remove: $NssmPath remove $ServiceName confirm"
Write-Host ""
