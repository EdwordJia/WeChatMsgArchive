#!/usr/bin/env bash
# Windows Task Scheduler 安装脚本（导入 schedule_pipeline.xml，每小时第13分钟跑）
#
# 前提：管理员 PowerShell 执行
#
# 验证：
#   schtasks /query /tn "WeChatMsgArchive_AutoPipeline"
#   schtasks /run /tn "WeChatMsgArchive_AutoPipeline"     # 立即跑一次
#   tail -f output/pipeline_cron.log

set -e
TASK_NAME="WeChatMsgArchive_AutoPipeline"
XML_PATH="$(cd "$(dirname "$0")" && pwd)/schedule_pipeline.xml"

cat <<EOF
=== Task Scheduler 安装命令（管理员 PowerShell）===

# 1. 注册任务
schtasks /create /tn "${TASK_NAME}" /xml "${XML_PATH}" /f

# 2. 验证
schtasks /query /tn "${TASK_NAME}" /v

# 3. 立即跑一次（测试）
schtasks /run /tn "${TASK_NAME}"

# 4. 看日志
type output\\pipeline_cron.log

# 5. 卸载（如需）
# schtasks /delete /tn "${TASK_NAME}" /f

=== 注意 ===
- XML 默认 PT1H 每小时；Triggers/CalendarTrigger/Repetition/Interval 改为 PT30M = 30 分钟
- Action.Command 默认 Git Bash 路径 (C:\Program Files\\Git\\bin\\bash.exe)
  如不同请编辑 XML
- LogonType=InteractiveToken 需要用户登录后才会跑
  改成 S4U 或 Password 可后台跑
EOF
