#!/usr/bin/env bash
# Watchdog 服务化预备脚本（不自动执行，给用户审阅）
#
# 前提：
#   - 已安装 nssm（https://nssm.cc/download）放到 PATH
#   - 以管理员身份运行
#
# 该脚本仅打印命令供用户复制执行，不直接调用 nssm 修改系统状态。

set -e

PROJECT_ROOT="D:/develoment_home/project_home/WeChatMsgArchive"
PYTHON_PATH="${PROJECT_ROOT}/venv/Scripts/python.exe"
SCRIPT_PATH="${PROJECT_ROOT}/wechat_realtime_monitor.py"
LOG_OUT="${PROJECT_ROOT}/output/realtime_monitor.out.log"
LOG_ERR="${PROJECT_ROOT}/output/realtime_monitor.err.log"
SERVICE_NAME="WeChatRealtimeMonitor"

cat <<EOF
=== watchdog 服务化命令（管理员 PowerShell 执行）===

# 1. 安装服务
nssm install ${SERVICE_NAME} "${PYTHON_PATH}" "${SCRIPT_PATH}"

# 2. 配置工作目录与日志
nssm set ${SERVICE_NAME} AppDirectory "${PROJECT_ROOT}"
nssm set ${SERVICE_NAME} AppStdout "${LOG_OUT}"
nssm set ${SERVICE_NAME} AppStderr "${LOG_ERR}"
nssm set ${SERVICE_NAME} AppRotateFiles 1
nssm set ${SERVICE_NAME} AppRotateBytes 10485760

# 3. 设置开机自启 + 启动
nssm set ${SERVICE_NAME} Start SERVICE_AUTO_START
nssm start ${SERVICE_NAME}

# 4. 查看状态
nssm status ${SERVICE_NAME}

# 5. 卸载（如需）
# nssm stop ${SERVICE_NAME}
# nssm remove ${SERVICE_NAME} confirm

=== 验证步骤 ===
1. 微信里发条新消息
2. 等 5-10 秒
3. 看 ${LOG_OUT} 是否有解密日志
4. 看 ${PROJECT_ROOT}/output/decrypted_db/Multi/MSG1.db mtime 是否更新

=== 故障排查 ===
- 服务起不来：nssm 默认日志在 Windows 事件查看器
- 解密失败：微信版本更新后偏移变化，看 ${PROJECT_ROOT}/output/realtime_monitor.log
- 权限不足：检查 ${SERVICE_NAME} 用户是否有读源 db 目录权限
EOF
