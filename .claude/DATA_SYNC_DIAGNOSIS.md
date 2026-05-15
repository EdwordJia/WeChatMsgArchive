# 数据同步问题诊断与解决方案

## 🚨 问题确认

### 用户反馈
- 今天是5月15日
- 查询到的最新消息是5月12日
- watchdog机制说了但没有实际运行
- 不是企业级功能，只是空谈

### 根本原因

**问题1：数据不是实时的**
```
微信源数据库（实时更新）
  位置: E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822\Msg\Multi\MSG1.db
  状态: 实时更新（每次收发消息都会写入）

  ↓ 需要手动运行解密

output/decrypted_db/Multi/MSG1.db（静态副本）
  最后更新: 5月13日 09:55
  状态: 静态副本，不会自动更新

  ↓ 查询这个副本

得到3天前的数据 ❌
```

**问题2：watchdog没有运行**
```
wechat_realtime_monitor.py 存在 ✅
但是没有启动 ❌
所以不会自动同步 ❌
```

---

## ✅ 解决方案

### 方案A：手动刷新（临时方案）

**步骤**：
```bash
# 每次需要最新数据时手动运行
./venv/Scripts/python wxManager/decrypt/decrypt_v3_enhanced.py
```

**优点**：
- 简单直接
- 可控

**缺点**：
- 需要手动触发
- 不是自动化
- 不是企业级

---

### 方案B：启动watchdog监听（推荐）

**原理**：
```
watchdog监听微信源数据库目录
  ↓ 检测到MSG*.db文件修改
防抖动（5秒）
  ↓ 触发自动解密
output/decrypted_db/ 自动更新
  ↓ AutoPipeline查询
始终获取最新数据 ✅
```

**实现步骤**：

#### 1. 修改监听脚本配置

编辑 `wechat_realtime_monitor.py`，确保配置正确：

```python
# 微信源数据库目录
WECHAT_MSG_DIR = r"E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822\Msg"

# 解密输出目录
OUTPUT_DIR = "output/decrypted_db"

# 防抖动时间（秒）
DEBOUNCE_SECONDS = 5
```

#### 2. 启动监听进程

**方式1：前台运行（测试用）**
```bash
./venv/Scripts/python wechat_realtime_monitor.py
```

**方式2：后台运行（生产用）**
```bash
# Windows后台运行
start /B pythonw wechat_realtime_monitor.py

# 或者用nohup（Git Bash）
nohup ./venv/Scripts/python wechat_realtime_monitor.py > output/monitor.log 2>&1 &
```
**方式3：Windows服务（最佳）**
```bash
# 使用NSSM将Python脚本注册为Windows服务
nssm install WeChatMonitor "D:\develoment_home\project_home\WeChatMsgArchive\venv\Scripts\python.exe" "D:\develoment_home\project_home\WeChatMsgArchive\wechat_realtime_monitor.py"
nssm start WeChatMonitor
```

#### 3. 验证监听是否工作

```bash
# 检查进程
ps aux | grep wechat_realtime_monitor

# 查看日志
tail -f output/realtime_monitor.log
```

**优点**：
- ✅ 真正的实时同步
- ✅ 自动化
- ✅ 企业级
- ✅ 无需手动干预

**缺点**：
- 需要持续运行
- 占用一定资源

---

### 方案C：定时同步（折中方案）
**原理**：
```
CronCreate定时任务
  ↓ 每小时自动运行解密
output/decrypted_db/ 定时更新
  ↓ AutoPipeline查询
最多延迟1小时 ⚠️
```

**实现**：
```python
from .claude.project_manager import CronCreate

# 每小时第7分钟自动解密
CronCreate(
    cron="7 * * *",
    prompt="./venv/Scripts/python wxManager/decrypt/decrypt_v3_enhanced.py",
    recurring=True
)
```

**优点**：
- 自动化
- 资源占用少
- 不需要持续运行进程

**缺点**：
- 不是实时的（最多延迟1小时）
- 可能错过紧急消息

---

## 🎯 推荐方案：watchdog + AutoPipeline

### 完整架构

```
┌─────────────────────────┐
│   微信源数据库（实时更新）              │
│   E:\...\Msg\Multi\MSG*.db          │
└──────────┬────────────────────┘
           ↓ watchdog监听
┌────────────────────────────────┐
│   WeChatDBChangeHandler             │
│   - 检测文件修改                      │
│   - 防抖动（5秒）                 │
│   - 触发解密                    │
└──────────┬────────────────────────┘
           ↓ 自动解密
┌──────────────────────────────────┐
│   output/decrypted_db/（实时副本）    │
│   - 自动更新                          │
│   - 始终最新             │
└──────────┬──────────────────────────┘
         ↓ AutoPipeline查询
┌─────────────────────┐
│   [1/5] 获取最新消息 ✅               │
│   [2/5] 识别需求（LLM）            │
│   [3/5] 创建kanban任务         │
│   [4/5] 分配agent（Kimi/Codex）      │
│   [5/5] 启动执行                    │
└──────────────────────────────┘
```

### 工作流程

1. **客户发消息** → 微信源数据库更新
2. **watchdog检测到变化** → 等待5秒（防抖动）
3. **自动触发解密** → output/decrypted_db/更新
4. **AutoPipeline查询** → 获取最新消息
5. **LLM识别需求** → 提取需求信息
6. **创建kanban任务** → 自动创建
7. **分配agent** → Kimi/Codex
8. **启动执行** → 自动处理

**用户体验**：
```
客户发消息（5月15日 10:00）
  ↓ 5秒后
watchdog触发解密（10:00:05）
  ↓ 1分钟后
AutoPipeline识别需求（10:01）
  ↓ 30秒后
创建kanban任务（10:01:30）
  ↓ 10秒后
分配给Codex执行（10:01:40）

总延迟：< 2分钟 ✅
```

---

## 📋 实施计划

### 阶段1：修复数据同步（立即）

**任务**：
- [x] 诊断问题（已完成）
- [ ] 运行解密刷新数据库（进行中）
- [ ] 验证数据是否最新（5月15日）
- [ ] 启动watchdog监听进程
- [ ] 验证watchdog是否工作

**预计时间**：30分钟

### 阶段2：实现AutoPipeline（1周）

**任务**：
- [ ] 实现 `_fetch_latest_messages()`
- [ ] 实现 `_identify_requirements()`（集成LLM）
- [ ] 实现 `_create_kanban_tasks()`
- [ ] 实现 `_assign_agents()`
- [ ] 实现 `_start_executions()`

**预计时间**：1周

### 阶段3：端到端测试（3天）

**任务**：
- [ ] 测试watchdog触发解密
- [ ] 测试AutoPipeline识别需求
- [ ] 测试kanban任务创建
- [ ] 测试agent自动执行
- [ ] 测试完整流程

**预计时间**：3天
---

## 🔍 验证清单

### 数据同步验证

- [ ] MSG1.db最后修改时间是今天
- [ ] 查询到5月15日的消息
- [ ] watchdog进程在运行
- [ ] 日志显示监听正常

### AutoPipeline验证

- [ ] 能获取最新消息
- [ ] LLM能识别需求
- [ ] 能创建kanban任务
- [ ] 能分配agent
- [ ] 能启动执行

### 端到端验证

- [ ] 客户发消息 → 2分钟内识别需求
- [ ] 自动创建kanban任务
- [ ] 自动分配agent
- [ ] 自动执行
- [ ] 汇报结果

---

## 📝 当前状态

### 已完成
- ✅ 诊断问题根因
- ✅ 设计解决方案
- ✅ 创建实施计划

### 进行中
- 🔄 运行解密刷新数据库

### 待完成
- ⏳ 验证数据是否最新
- ⏳ 启动watchdog监听
- ⏳ 实现AutoPipeline
- ⏳ 端到端测试

---

**评估人**：Claude
**创建日期**：2026-05-15
**状态**：问题已确认，解决方案已设计，待实施
