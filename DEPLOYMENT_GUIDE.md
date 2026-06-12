# AutoPipeline 24x7 自动化部署指南

本指南帮助你配置完整的自动化流程：微信消息 → 需求识别 → 任务创建 → Agent 执行

## 架构概览

```
微信消息
    ↓
Watchdog 实时监听（Windows 服务）
    ↓
解密数据库自动更新
    ↓
AutoPipeline 定时扫描（每小时）
    ↓
LLM 识别需求 + 创建任务
    ↓
Agent 自动执行
```

## 前置要求

### 1. 系统环境
- ✅ Windows 10/11
- ✅ Git Bash（已安装）
- ✅ Python 3.8+（已配置虚拟环境）
- ✅ 微信客户端正在运行

### 2. 项目依赖
```bash
# 检查虚拟环境
./venv/Scripts/python --version

# 安装依赖（如果还没有）
./venv/Scripts/pip install watchdog anthropic
```

### 3. API 密钥配置
```powershell
# 设置环境变量（用户级别，永久生效）
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")

# 验证
$env:ANTHROPIC_API_KEY
```

**获取 API Key**: https://console.anthropic.com/settings/keys

---

## 部署步骤

### 第一步：安装 Watchdog 服务

**作用**：实时监听微信数据库变化，自动解密并同步到索引数据库

**操作**：
```powershell
# 1. 以管理员身份打开 PowerShell
# 右键点击 PowerShell 图标 -> 以管理员身份运行

# 2. 进入项目目录
cd D:\develoment_home\project_home\WeChatMsgArchive

# 3. 允许执行脚本（首次需要）
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 4. 运行安装脚本
.\install_watchdog_service.ps1
```

**验证**：
```powershell
# 检查服务状态
Get-Service -Name WeChatRealtimeMonitor

# 查看实时日志
Get-Content output\realtime_monitor.out.log -Wait

# 测试：在微信发送一条消息，5-10秒后日志应显示 "检测到数据库变化"
```

**预期结果**：
- 服务状态：Running
- 日志显示：`[INFO] 启动实时监控: output/decrypted_db/Multi`
- 微信发消息后，日志显示：`[INFO] 检测到数据库变化: MSG1.db`

---

### 第二步：配置定时任务

**作用**：每小时运行 AutoPipeline，扫描新消息并处理

**操作**：
```powershell
# 1. 以管理员身份打开 PowerShell（同上）

# 2. 运行安装脚本
.\install_task_scheduler.ps1
```

**验证**：
```powershell
# 查看任务状态
Get-ScheduledTask -TaskName WeChatAutoPipeline | Format-List

# 手动运行测试
Start-ScheduledTask -TaskName WeChatAutoPipeline

# 查看执行日志
Get-Content output\task_scheduler.log -Tail 50

# 查看任务历史
Get-ScheduledTaskInfo -TaskName WeChatAutoPipeline
```

**预期结果**：
- 任务状态：Ready
- 触发器：每小时运行一次
- 最后运行结果：Success (0x0)
- 日志显示完整的 Stage 1-6 执行过程

---

### 第三步：端到端测试

**测试场景**：客户在微信群发送需求消息

**步骤**：
1. **发送测试消息**（在已配置的业务群）：
   ```
   老师，可以加个导出功能吗？今天要用
   ```

2. **等待 Watchdog 同步**（5-10秒）：
   ```powershell
   Get-Content output\realtime_monitor.out.log -Tail 10
   # 应显示：[INFO] 检测到数据库变化: MSG1.db
   ```

3. **手动触发 AutoPipeline**（或等待下一个整点）：
   ```bash
   ./run_pipeline.sh
   ```

4. **检查处理结果**：
   ```bash
   # 查看识别的需求
   cat .claude/state/runtime_pending_report.md

   # 查看创建的任务
   ./venv/Scripts/python -c "
   from mcp_servers.kanban_doc import list_tasks
   print(list_tasks('项目名'))
   "
   ```

**预期结果**：
- ✅ Watchdog 检测到消息
- ✅ AutoPipeline 识别出需求
- ✅ 自动创建 kanban 任务
- ✅ 任务进入 runtime_queue
- ✅ 生成 MCP 调用计划

---

## 运行状态监控

### 查看 Watchdog 状态
```powershell
# 服务状态
Get-Service -Name WeChatRealtimeMonitor

# 实时日志
Get-Content output\realtime_monitor.out.log -Wait

# 最近 50 条日志
Get-Content output\realtime_monitor.out.log -Tail 50
```

### 查看定时任务状态
```powershell
# 任务状态
Get-ScheduledTask -TaskName WeChatAutoPipeline

# 执行历史
Get-ScheduledTaskInfo -TaskName WeChatAutoPipeline

# 执行日志
Get-Content output\task_scheduler.log -Tail 100
```

### 查看 AutoPipeline 状态
```bash
# 查看队列报告
cat .claude/state/runtime_pending_report.md

# 查看调用计划
cat .claude/state/mcp_invocation_plan.md

# 查看去重状态
cat .claude/state/processed_messages.json | jq '.processed_count'

# 查看 AutoPipeline 日志
cat .claude/state/auto_pipeline.log
```

---

## 故障排查

### Watchdog 服务无法启动
**症状**：`Get-Service` 显示 Stopped

**排查**：
1. 检查 Python 路径是否正确：
   ```powershell
   Test-Path D:\develoment_home\project_home\WeChatMsgArchive\venv\Scripts\python.exe
   ```

2. 检查错误日志：
   ```powershell
   Get-Content output\realtime_monitor.err.log
   ```

3. 检查 Windows 事件查看器：
   ```powershell
   eventvwr.msc
   # 导航到：Windows 日志 -> 应用程序
   # 筛选来源：WeChatRealtimeMonitor
   ```

4. 手动测试脚本：
   ```bash
   ./venv/Scripts/python wechat_realtime_monitor.py
   # 应显示：[INFO] 启动实时监控
   ```

### 定时任务不执行
**症状**：任务历史显示从未运行

**排查**：
1. 检查任务触发器：
   ```powershell
   Get-ScheduledTask -TaskName WeChatAutoPipeline | Select-Object -ExpandProperty Triggers
   ```

2. 手动运行测试：
   ```powershell
   Start-ScheduledTask -TaskName WeChatAutoPipeline
   Get-ScheduledTaskInfo -TaskName WeChatAutoPipeline
   ```

3. 检查 Git Bash 路径：
   ```powershell
   Test-Path "C:\Program Files\Git\bin\bash.exe"
   ```

4. 查看执行日志：
   ```powershell
   Get-Content output\task_scheduler.log
   ```

### AutoPipeline 无法识别需求
**症状**：日志显示 "0 requirements identified"

**排查**：
1. 检查 API Key 配置：
   ```powershell
   $env:ANTHROPIC_API_KEY
   # 应显示：sk-ant-...
   ```

2. 检查消息是否在白名单群：
   ```bash
   ./venv/Scripts/python -c "
   from business_channels import BUSINESS_CHANNELS
   print([c['chatroom_id'] for c in BUSINESS_CHANNELS])
   "
   ```

3. 检查消息是否被去重：
   ```bash
   cat .claude/state/processed_messages.json | jq '.messages | length'
   ```

4. 手动测试识别：
   ```bash
   ./venv/Scripts/python -c "
   from llm_requirement_analyzer import analyze_requirements
   messages = [{'content': '老师，可以加个导出功能吗？今天要用', 'sender': '客户'}]
   print(analyze_requirements(messages))
   "
   ```

### MCP 调用失败
**症状**：任务创建失败或 runtime 启动失败

**排查**：
1. 检查 kanban-doc MCP 服务：
   ```bash
   # 在 Claude Code 中运行
   /mcp status
   ```

2. 检查项目是否配置了 agent：
   ```bash
   ./venv/Scripts/python -c "
   from mcp_servers.kanban_doc import get_agent_config
   print(get_agent_config('项目名'))
   "
   ```

3. 查看调用清单：
   ```bash
   cat .claude/state/start_runtime_invocations.json | jq
   ```

---

## 性能优化

### 调整扫描频率
```powershell
# 修改为每 30 分钟运行一次
$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).Date `
    -RepetitionInterval (New-TimeSpan -Minutes 30) `
    -RepetitionDuration ([TimeSpan]::MaxValue)

Set-ScheduledTask -TaskName WeChatAutoPipeline -Trigger $Trigger
```

### 调整 Watchdog 防抖时间
编辑 `wechat_realtime_monitor.py`:
```python
self.debounce_seconds = 10  # 从 5 秒改为 10 秒
```
### 减少 API 调用
编辑 `llm_requirement_analyzer.py`，启用缓存：
```python
# 相同消息内容 1 小时内不重复调用 API
```

---

## 卸载指南

### 停止并删除 Watchdog 服务
```powershell
# 停止服务
.\tools\nssm.exe stop WeChatRealtimeMonitor

# 删除服务
.\tools\nssm.exe remove WeChatRealtimeMonitor confirm
```

### 删除定时任务
```powershell
Unregister-ScheduledTask -TaskName WeChatAutoPipeline -Confirm:$false
```

### 清理状态文件
```bash
rm -rf .claude/state/*
```

---

## 下一步

配置完成后，系统将 24x7 自动运行：

1. **实时监听**：Watchdog 持续监听微信数据库
2. **定时扫描**：每小时扫描新消息
3. **自动识别**：LLM 分析需求并创建任务
4. **自动执行**：Agent 自动处理任务

**建议**：
- 前 3 天每天检查日志，确保稳定运行
- 根据实际情况调整扫描频率
- 定期查看 `runtime_pending_report.md` 审核待处理任务
- 监控 API 使用量，避免超额
**进一步优化**：
- 配置错误告警（邮件/微信通知）
- 开发 Web UI 查看运行状态
- 接入更多业务群和项目
- 优化 LLM prompt 提升识别准确率

---

**生成时间**: 2026-05-16
**版本**: v1.0
**维护者**: Claude Code
