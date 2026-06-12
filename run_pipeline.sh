#!/usr/bin/env bash
# AutoPipeline 一键运行脚本（企业级链路 6 stage）
#
# 用法:
#   ./run_pipeline.sh         # 完整跑 + 渲染报告
#   ./run_pipeline.sh --reset # 重置 dedup state 后再跑（强制重新识别所有消息）
#   ./run_pipeline.sh --dry   # 只 dry-run 看消息状态，不入队
#
# 输出:
#   .claude/state/runtime_pending_report.md  → 用户审视
#   .claude/state/start_runtime_invocations.json → Claude 调 MCP
#   .claude/state/mcp_invocation_plan.md  → 调用模板说明

set -e
cd "$(dirname "$0")"

PYTHON="./venv/Scripts/python"
STATE_DIR=".claude/state"

if [[ "$1" == "--reset" ]]; then
    echo "[reset] 清空 dedup + queue state"
    rm -f "$STATE_DIR/processed_messages.json" "$STATE_DIR/runtime_queue.json" \
        "$STATE_DIR/runtime_pending_report.md" "$STATE_DIR/start_runtime_invocations.json" \
        "$STATE_DIR/mcp_invocation_plan.md"
fi

echo
echo "===== Stage 1: 跑 AutoPipeline 主流程 ====="
$PYTHON -c "
import sys
sys.path.insert(0, '.')
sys.path.insert(0, '.claude')
sys.stdout.reconfigure(encoding='utf-8')
from auto_pipeline import AutoPipeline
print(AutoPipeline().run('manual'))
"

if [[ "$1" == "--dry" ]]; then
    echo "[dry-run] 跳过队列渲染"
    exit 0
fi

echo
echo "===== Stage 5.5: 渲染队列报告 ====="
$PYTHON .claude/process_runtime_queue.py

echo
echo "===== Stage 6 准备: 生成调用清单 ====="
$PYTHON .claude/start_approved_runtimes.py
$PYTHON .claude/auto_invoke_mcp.py

echo
echo "===== 状态总览 ====="
echo "队列报告:    $STATE_DIR/runtime_pending_report.md"
echo "调用清单:    $STATE_DIR/start_runtime_invocations.json"
echo "调用计划:    $STATE_DIR/mcp_invocation_plan.md"
echo
echo "请 Claude 会话:"
echo "  1) 阅读 $STATE_DIR/mcp_invocation_plan.md"
echo "  2) 对每条 source=auto 项调 mcp__kanban-doc__create_workspace + start_runtime"
echo "  3) 调 auto_invoke_mcp.mark_invoked(task_id, process_id) 同步队列"
