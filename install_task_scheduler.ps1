# Windows 任务计划配置脚本
# 替代 Linux cron，实现定时运行 AutoPipeline
#
# 用法（管理员 PowerShell）：
#   .\install_task_scheduler.ps1
#
# 功能：
#   - 创建 Windows 任务计划，每小时运行一次 run_pipeline.sh
#   - 日志输出到 output/task_scheduler.log

$ErrorActionPreference = "Stop"

# 配置参数
$TaskName = "WeChatAutoPipeline"
$ProjectRoot = "D:\develoment_home\project_home\WeChatMsgArchive"
$BashPath = "C:\Program Files\Git\bin\bash.exe"
$ScriptPath = "$ProjectRoot\run_pipeline.sh"
$LogPath = "$ProjectRoot\output\task_scheduler.log"
$WorkingDir = $ProjectRoot

# 检查 Git Bash 是否存在
if (-not (Test-Path $BashPath)) {
    Write-Error "Git Bash 未找到: $BashPath"
    Write-Host "请安装 Git for Windows: https://git-scm.com/download/win"
    exit 1
}

# 检查脚本是否存在
if (-not (Test-Path $ScriptPath)) {
    Write-Error "脚本未找到: $ScriptPath"
    exit 1
}

# 创建输出目录
$OutputDir = "$ProjectRoot\output"
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

Write-Host "=== 配置 Windows 任务计划 ===" -ForegroundColor Cyan
Write-Host "任务名称: $TaskName"
Write-Host "执行脚本: $ScriptPath"
Write-Host "日志路径: $LogPath"
Write-Host ""

# 删除已存在的任务（如果有）
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "删除已存在的任务..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# 创建任务动作（运行 bash 脚本，重定向输出到日志）
$Action = New-ScheduledTaskAction `
    -Execute $BashPath `
    -Argument "-c `"cd '$WorkingDir' && ./run_pipeline.sh >> '$LogPath' 2>&1`"" `
    -WorkingDirectory $WorkingDir

# 创建触发器（每小时运行一次，从 :07 分开始）
$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).Date `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration ([TimeSpan]::MaxValue)

# 设置任务配置
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

# 使用当前用户身份运行
$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType S4U `
    -RunLevel Highest

# 注册任务
Write-Host "注册任务计划..." -ForegroundColor Green
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "微信消息自动化处理流程：每小时扫描新消息，识别需求，创建任务" | Out-Null

Write-Host ""
Write-Host "=== 任务计划配置完成 ===" -ForegroundColor Green
Write-Host ""
Write-Host "验证步骤：" -ForegroundColor Cyan
Write-Host "1. 查看任务状态："
Write-Host "   Get-ScheduledTask -TaskName '$TaskName' | Format-List"
Write-Host ""
Write-Host "2. 手动运行测试："
Write-Host "   Start-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "3. 查看日志："
Write-Host "   Get-Content '$LogPath' -Tail 50"
Write-Host ""
Write-Host "4. 查看任务历史："
Write-Host "   Get-ScheduledTaskInfo -TaskName '$TaskName'"
Write-Host ""
Write-Host "管理命令：" -ForegroundColor Cyan
Write-Host "- 启用任务: Enable-ScheduledTask -TaskName '$TaskName'"
Write-Host "- 禁用任务: Disable-ScheduledTask -TaskName '$TaskName'"
Write-Host "- 删除任务: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
Write-Host ""
