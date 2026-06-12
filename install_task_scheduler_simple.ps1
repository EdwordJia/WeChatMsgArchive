# Task Scheduler Installation Script
# Create scheduled task to run AutoPipeline hourly

$ErrorActionPreference = "Stop"

# Configuration
$TaskName = "WeChatAutoPipeline"
$ProjectRoot = "D:\develoment_home\project_home\WeChatMsgArchive"
$BashPath = "C:\Program Files\Git\bin\bash.exe"
$ScriptPath = "$ProjectRoot\run_pipeline.sh"
$LogPath = "$ProjectRoot\output\task_scheduler.log"

Write-Host "=== Installing Task Scheduler ===" -ForegroundColor Cyan

# Check Git Bash
if (-not (Test-Path $BashPath)) {
    Write-Error "Git Bash not found: $BashPath"
    exit 1
}

# Check script
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Script not found: $ScriptPath"
    exit 1
}

# Create output directory
New-Item -ItemType Directory -Path "$ProjectRoot\output" -Force | Out-Null

# Remove existing task
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create task action
$Action = New-ScheduledTaskAction `
    -Execute $BashPath `
    -Argument "-c `"cd '$ProjectRoot' && ./run_pipeline.sh >> '$LogPath' 2>&1`"" `
    -WorkingDirectory $ProjectRoot

# Create trigger (hourly)
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Hours 1)

# Task settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

# Principal (current user, highest privileges)
$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType S4U `
    -RunLevel Highest

# Register task
Write-Host "Registering task..." -ForegroundColor Green
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "WeChat message automation pipeline" | Out-Null

Write-Host ""
Write-Host "=== Task Installed ===" -ForegroundColor Green
Write-Host ""
Write-Host "=== Verification ===" -ForegroundColor Cyan
Write-Host "1. Check task: Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "2. Manual run: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "3. View logs: Get-Content '$LogPath' -Tail 50"
Write-Host "4. Task history: Get-ScheduledTaskInfo -TaskName '$TaskName'"
Write-Host ""
Write-Host "=== Management ===" -ForegroundColor Cyan
Write-Host "- Enable: Enable-ScheduledTask -TaskName '$TaskName'"
Write-Host "- Disable: Disable-ScheduledTask -TaskName '$TaskName'"
Write-Host "- Remove: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
Write-Host ""
