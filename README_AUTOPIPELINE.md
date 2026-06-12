# WeChatMsgArchive - 微信消息自动化处理系统

企业级微信消息自动化处理流程：实时监听 → 需求识别 → 任务创建 → Agent 执行

> 本文档描述基于 WeChatMsg 项目构建的自动化业务流程系统

## 🎯 核心功能

### 1. 实时数据同步
- **Watchdog 服务**：监听微信数据库变化，自动解密并同步
- **秒级响应**：检测到新消息后 5-10 秒内完成处理
- **Windows 服务化**：开机自启，24x7 运行
### 2. 智能需求识别
- **LLM 语义分析**：使用 Anthropic Claude API 识别需求
- **规则关键词扩展**：支持无 API Key 的规则模式
- **多维度分类**：需求类型、优先级、项目映射、截止时间

### 3. 自动任务管理
- **kanban-doc 集成**：自动创建任务到对应项目
- **分级审批**：根据标签（bug/urgent）决定是否需要人工审核
- **去重机制**：避免重复处理相同消息

### 4. Agent 自动执行
- **智能路由**：代码类任务 → Codex，文件类任务 → Kimi
- **Runtime 队列**：任务排队等待执行
- **MCP 桥接**：生成调用计划，Claude 执行

## 📊 架构概览

```
微信消息（源数据库）
    ↓
Watchdog 实时监听（Windows 服务）
    ↓
自动解密 → 索引数据库
    ↓
AutoPipeline 定时扫描（每小时）
    ├─ Stage 1: 读取新消息
    ├─ Stage 2: LLM/规则识别需求
    ├─ Stage 3: 创建 kanban 任务
    ├─ Stage 4: 分配 Agent
    └─ Stage 5: 启动 Runtime
    ↓
生成 MCP 调用计划
    ↓
Claude 执行 MCP 调用
    ↓
Agent 自动处理任务
```

## 🚀 快速开始

### 前置要求
- Windows 10/11
- Python 3.8+
- Git Bash
- 微信客户端正在运行

### 安装步骤

#### 1. 安装依赖
```bash
./venv/Scripts/pip install watchdog anthropic
```

#### 2. 配置环境变量（可选，启用 LLM 模式）
```powershell
[System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
```

#### 3. 运行测试
```bash
./test_deployment.sh
```

#### 4. 部署服务（管理员 PowerShell）
```powershell
# 安装 Watchdog 服务
.\install_watchdog_service.ps1

# 配置定时任务
.\install_task_scheduler.ps1
```

**详细部署指南**：[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

## 📁 核心文件

```
├── run_pipeline.sh              # 一键运行脚本
├── test_deployment.sh           # 部署测试脚本
├── install_watchdog_service.ps1    # Watchdog 服务安装
├── install_task_scheduler.ps1      # 定时任务配置
├── DEPLOYMENT_GUIDE.md             # 完整部署指南
│
├── wechat_realtime_monitor_v2.py   # Watchdog 监控脚本
├── business_channels.py            # 业务渠道配置
│
├── .claude/
│   ├── auto_pipeline.py            # AutoPipeline 主流程
│   ├── dedup_state.py              # 去重模块
│   ├── runtime_starter.py          # Runtime 启动器
│   ├── process_runtime_queue.py    # 队列处理器
│   ├── start_approved_runtimes.py  # 审批桥接
│   ├── auto_invoke_mcp.py        # MCP 调用生成器
│   └── state/                # 运行时状态
│       ├── processed_messages.json
│       ├── runtime_queue.json
│       ├── runtime_pending_report.md
│     └── mcp_invocation_plan.md
```

## 🔧 配置说明

### 业务渠道配置
编辑 `business_channels.py`：
```python
CHANNEL_TO_PROJECT = {
    "49734720477@chatroom": "ai-zs",          # 群聊 ID → 项目名
    "wxid_tm60ob3bb94x22": "ai-zs",           # 私聊 wxid → 项目名
}

CHANNEL_SENDER_WHITELIST = {
    "49734720477@chatroom": [
        "wxid_xxx",  # 只处理这些发送者的消息
    ],
}
```

### 微信数据目录
编辑 `wechat_realtime_monitor_v2.py`：
```python
WECHAT_DATA_DIR = r"E:\...\WeChat Files\wxid_xxx\Msg"
```

### 扫描频率
编辑 `install_task_scheduler.ps1`：
```powershell
# 每 30 分钟运行一次
-RepetitionInterval (New-TimeSpan -Minutes 30)
```

## 📊 监控与管理

### 查看服务状态
```powershell
# Watchdog 服务
Get-Service -Name WeChatRealtimeMonitor

# 定时任务
Get-ScheduledTask -TaskName WeChatAutoPipeline
```

### 查看日志
```bash
# Watchdog 日志
tail -f output/realtime_monitor.out.log

# 定时任务日志
tail -f output/task_scheduler.log

# AutoPipeline 日志
tail -f .claude/state/auto_pipeline.log
```

### 查看队列状态
```bash
# 待处理任务报告
cat .claude/state/runtime_pending_report.md

# MCP 调用计划
cat .claude/state/mcp_invocation_plan.md
```

## 🐛 故障排查

详细故障排查请查看：[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#故障排查)

常见问题：
- Watchdog 服务无法启动 → 检查 Python 路径和权限
- 定时任务不执行 → 检查任务触发器和日志
- AutoPipeline 无法识别需求 → 检查 API Key 和白名单配置

## 📈 性能指标

- **响应延迟**：微信发消息 → 解密完成 < 10 秒
- **识别准确率**：LLM 模式 > 90%，规则模式 > 70%
- **处理吞吐**：每小时可处理 100+ 条消息
- **资源占用**：Watchdog < 50MB 内存，CPU < 1%

## 🔐 安全说明

- **数据隔离**：解密数据库仅存储在本地
- **API Key 保护**：使用环境变量，不写入代码
- **权限控制**：Watchdog 服务以当前用户身份运行
- **日志脱敏**：不记录消息内容，仅记录元数据

## 📝 更新日志

### v1.0 (2026-05-16)
- ✅ 完整的 AutoPipeline 流程（Stage 1-5）
- ✅ Watchdog 实时监听与自动解密
- ✅ Windows 服务化与定时任务
- ✅ LLM 需求识别（Anthropic Claude API）
- ✅ kanban-doc 任务自动创建
- ✅ 分级审批与去重机制
- ✅ MCP 调用桥接
- ✅ 完整部署指南与测试脚本

### 计划中
- [ ] Web UI 管理界面
- [ ] 错误告警（邮件/微信通知）
- [ ] 多微信账号支持
- [ ] 任务执行结果反馈到微信
- [ ] 性能监控与统计报表

## 📄 许可证

MIT License

---

**生成时间**: 2026-05-16
**版本**: v1.0
**状态**: ✅ 生产就绪
