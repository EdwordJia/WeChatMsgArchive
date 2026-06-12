# 🚀 快速启动指南

5 分钟完成 AutoPipeline 部署

## 第一步：测试环境（1 分钟）

```bash
# 运行测试脚本
./test_deployment.sh
```

**预期结果**：所有检查项显示 ✓（绿色）

如果有 ⚠（黄色）警告：
- `ANTHROPIC_API_KEY 未配置` → 可选，不影响基础功能
- `数据库更新时间过旧` → 正常，稍后会自动更新

如果有 ✗（红色）错误：
- 按照提示修复问题
- 查看 [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) 获取帮助

---

## 第二步：安装 Watchdog 服务（2 分钟）

**以管理员身份打开 PowerShell**：
1. 按 `Win + X`
2. 选择 "Windows PowerShell (管理员)" 或 "终端 (管理员)"

**运行安装脚本**：
```powershell
cd D:\develoment_home\project_home\WeChatMsgArchive

# 允许执行脚本（首次需要）
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 安装 Watchdog 服务
.\install_watchdog_service.ps1
```

**验证**：
```powershell
# 检查服务状态（应显示 Running）
Get-Service -Name WeChatRealtimeMonitor

# 查看实时日志（应显示 "启动实时监控"）
Get-Content output\realtime_monitor.out.log -Tail 10
```

**测试**：
1. 在微信发送一条消息
2. 等待 5-10 秒
3. 日志应显示 "检测到数据库变化"

---

## 第三步：配置定时任务（1 分钟）

**继续在管理员 PowerShell 中运行**：
```powershell
# 配置定时任务（每小时运行一次）
.\install_task_scheduler.ps1
```

**验证**：
```powershell
# 检查任务状态（应显示 Ready）
Get-ScheduledTask -TaskName WeChatAutoPipeline

# 手动运行测试
Start-ScheduledTask -TaskName WeChatAutoPipeline

# 查看执行日志（应显示 Stage 1-5 完整流程）
Get-Content output\task_scheduler.log -Tail 50
```

---

## 第四步：配置 API Key（可选，1 分钟）

**启用 LLM 语义识别模式**（推荐，识别准确率 > 90%）：

```powershell
# 设置环境变量（永久生效）
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-api03-你的密钥", "User")

# 验证
$env:ANTHROPIC_API_KEY
```

**获取 API Key**：https://console.anthropic.com/settings/keys

**不配置的影响**：
- 仍可使用规则关键词模式（准确率 > 70%）
- 无法进行语义理解和复杂需求识别

---

## 完成！🎉

系统已配置完成，现在会：
1. **实时监听**：Watchdog 持续监听微信数据库
2. **自动解密**：检测到变化后自动解密
3. **定时扫描**：每小时扫描新消息
4. **自动识别**：LLM/规则识别需求
5. **创建任务**：自动创建到 kanban-doc
6. **生成计划**：生成 MCP 调用计划

---

## 下一步

### 查看运行状态
```bash
# 查看待处理任务
cat .claude/state/runtime_pending_report.md

# 查看 MCP 调用计划
cat .claude/state/mcp_invocation_plan.md
```

### 手动触发一次完整流程
```bash
# 重置状态并运行（会重新识别所有消息）
./run_pipeline.sh --reset
```

### 调整配置

**添加新业务群**：
1. 编辑 `business_channels.py`
2. 添加群聊 ID 和项目映射
3. 重启 AutoPipeline

**调整扫描频率**：
1. 编辑 `install_task_scheduler.ps1`
2. 修改 `-RepetitionInterval` 参数
3. 重新运行安装脚本

**查看完整文档**：
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - 完整部署指南
- [README_AUTOPIPELINE.md](README_AUTOPIPELINE.md) - 系统说明

---

## 故障排查

### Watchdog 服务无法启动
```powershell
# 查看错误日志
Get-Content output\realtime_monitor.err.log

# 检查 Windows 事件查看器
eventvwr.msc
```
### 定时任务不执行
```powershell
# 查看任务历史
Get-ScheduledTaskInfo -TaskName WeChatAutoPipeline

# 查看执行日志
Get-Content output\task_scheduler.log
```

### AutoPipeline 无法识别需求
```bash
# 检查消息是否在白名单群
./venv/Scripts/python -c "from business_channels import CHANNEL_TO_PROJECT; print(CHANNEL_TO_PROJECT)"

# 手动测试识别
./run_pipeline.sh --reset
```

**更多帮助**：查看 [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#故障排查)

---

## 管理命令速查

### Watchdog 服务
```powershell
# 查看状态
Get-Service -Name WeChatRealtimeMonitor

# 启动/停止/重启
Start-Service -Name WeChatRealtimeMonitor
Stop-Service -Name WeChatRealtimeMonitor
Restart-Service -Name WeChatRealtimeMonitor

# 查看日志
Get-Content output\realtime_monitor.out.log -Wait
```

### 定时任务
```powershell
# 查看状态
Get-ScheduledTask -TaskName WeChatAutoPipeline

# 启用/禁用
Enable-ScheduledTask -TaskName WeChatAutoPipeline
Disable-ScheduledTask -TaskName WeChatAutoPipeline

# 手动运行
Start-ScheduledTask -TaskName WeChatAutoPipeline

# 查看日志
Get-Content output\task_scheduler.log -Tail 50
```

### AutoPipeline
```bash
# 完整运行
./run_pipeline.sh

# 重置状态后运行
./run_pipeline.sh --reset

# 仅测试（不入队）
./run_pipeline.sh --dry
```

---

**生成时间**: 2026-05-16
**预计完成时间**: 5 分钟
**难度**: ⭐⭐☆☆☆
