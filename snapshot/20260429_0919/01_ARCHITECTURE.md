# 系统架构说明

## 🏗️ 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      微信数据源                              │
│  E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files │
│                   wxid_ucag2pjrmhm822                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   解密层 (PyWxDump)                          │
│  - 解密微信数据库（MSG*.db, MicroMsg.db等）                  │
│  - 获取解密密钥                                              │
│  - 支持微信版本: v3 (3.9.12.57)                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              索引层 (wechat_index_db.py)                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  本地SQLite数据库: wechat_index.db                  │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │  contacts      - 联系人表                           │   │
│  │  chatrooms     - 群聊表                             │   │
│  │  messages      - 消息索引表（138,947条）            │   │
│  │  sync_state    - 同步状态表                         │   │
│  └─────────────────────────────────────────────────────┘   │
│  - 全量同步: 索引所有42个MSG*.db                            │
│  - 增量同步: 只同步新消息                                   │
│  - 快速搜索: SQL索引，0.1秒响应                             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         分析层 (auto_requirement_collector.py)               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  需求识别引擎                                       │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │  1. 关键词匹配                                      │   │
│  │     - 需求类: 需要、想要、能不能、可以...           │   │
│  │     - Bug类: bug、问题、错误、不行...               │   │
│  │     - 反馈类: 反馈、意见、体验...                   │   │
│  │                                                      │   │
│  │  2. 优先级判断                                      │   │
│  │     - critical: 崩溃、数据丢失                      │   │
│  │     - high: 紧急、严重、重要                        │   │
│  │     - medium: 希望、建议、优化                      │   │
│  │     - low: 其他                                     │   │
│  │                                                      │   │
│  │  3. 项目识别                                        │   │
│  │     - syc-player: 播放器相关                        │   │
│  │     - qt-lens: 镜片检测相关                         │   │
│  │     - wechat-archive: 微信归档相关                  │   │
│  └─────────────────────────────────────────────────────┘   │
│  - 监控6个用户                                              │
│  - 输出: pending_kanban_tasks.json                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            筛选层 (auto_workflow.py)                         │
│  - 时间范围筛选（默认7天）                                   │
│  - 优先级筛选（默认medium+）                                 │
│  - 去重处理                                                 │
│  - 输出: tasks_to_create.json                               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│          执行层 (create_kanban_tasks.py)                     │
│  - 读取tasks_to_create.json                                 │
│  - 通过kanban-doc MCP创建任务                               │
│  - 自动分配到对应项目                                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Kanban-doc 项目管理                         │
│  - syc-player: 播放器项目                                   │
│  - qt-lens: 镜片检测项目                                    │
│  - wechat-archive: 微信归档项目                             │
└─────────────────────────────────────────────────────────────┘
```

## 🔄 数据流

### 1. 全量同步流程
```
微信数据库 → 解密 → 遍历所有MSG*.db → 提取消息 → 写入索引数据库
```

### 2. 增量同步流程
```
检查sync_state → 获取最后同步时间 → 只提取新消息 → 更新索引数据库
```

### 3. 需求收集流程
```
索引数据库 → 查询监控用户消息 → 关键词匹配 → 分类优先级 → 识别项目 → 生成任务列表
```

### 4. 任务创建流程
```
任务列表JSON → 筛选（时间/优先级） → 通过MCP创建 → Kanban项目
```

## 📦 核心模块

### wechat_index_db.py
**职责：** 索引数据库管理
**核心类：** `WeChatIndexDB`
**核心方法：**
- `full_sync()` - 全量同步
- `incremental_sync()` - 增量同步
- `search_messages()` - 搜索消息
- `get_user_messages()` - 获取用户消息

**数据库表结构：**
```sql
-- 联系人表
CREATE TABLE contacts (
    wxid TEXT PRIMARY KEY,
    nickname TEXT,
    remark TEXT,
    first_seen INTEGER,
    last_seen INTEGER
);

-- 群聊表
CREATE TABLE chatrooms (
    chatroom_id TEXT PRIMARY KEY,
    name TEXT,
    member_count INTEGER,
    first_seen INTEGER,
    last_seen INTEGER
);

-- 消息表
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_id INTEGER,
    talker TEXT,
    type INTEGER,
    content TEXT,
    create_time INTEGER,
    db_file TEXT,
    UNIQUE(msg_id, db_file)
);
CREATE INDEX idx_talker ON messages(talker);
CREATE INDEX idx_time ON messages(create_time);
CREATE INDEX idx_content ON messages(content);

-- 同步状态表
CREATE TABLE sync_state (
    db_file TEXT PRIMARY KEY,
    last_sync_time INTEGER,
    message_count INTEGER
);
```

### auto_requirement_collector.py
**职责：** 智能需求收集
**核心类：** `RequirementCollector`
**核心方法：**
- `collect_requirements()` - 收集需求
- `_is_requirement()` - 判断是否为需求
- `_is_bug()` - 判断是否为Bug
- `_get_priority()` - 获取优先级
- `_identify_project()` - 识别项目

**配置参数：**
```python
# 监控用户
monitor_users = ['三叶草', '编程仝芷硕', 'Estelle', '烨林', '沐光', '密码机']

# 需求关键词
requirement_keywords = ['需要', '想要', '能不能', '可以', '希望', '建议', '增加', '添加', '修改']

# Bug关键词
bug_keywords = ['bug', '问题', '错误', '不行', '失败', '崩溃', '报错', '异常']

# 项目关键词
project_keywords = {
    'syc-player': ['播放器', '视频', '音频', 'player', '三叶草'],
    'qt-lens': ['镜片', '检测', 'Qt', '林爱新', 'B-boy'],
    'wechat-archive': ['微信', '聊天记录', '解密', '数据库']
}
```

### auto_workflow.py
**职责：** 自动化工作流编排
**核心函数：**
- `decrypt_databases()` - 解密数据库
- `sync_to_index()` - 同步到索引
- `collect_requirements()` - 收集需求
- `filter_tasks()` - 筛选任务
- `main()` - 主流程

**可配置参数：**
```python
days = 7              # 时间范围（天）
min_priority = 'medium'  # 最低优先级
```

### wechat_monitor_v2.py
**职责：** 定时监控
**核心功能：**
- 定时执行完整流程
- 生成监控日志
- 输出待创建任务列表

**运行方式：**
```bash
# 手动运行
python wechat_monitor_v2.py

# Windows任务计划程序（每30分钟）
schtasks /create /tn "WeChatMonitor" /tr "python wechat_monitor_v2.py" /sc minute /mo 30
```

### create_kanban_tasks.py
**职责：** Kanban任务创建
**核心功能：**
- 读取tasks_to_create.json
- 通过kanban-doc MCP创建任务
- 批量创建支持

**使用方式：**
```python
# 在Claude Code中运行
python create_kanban_tasks.py
```

## 🔧 技术栈

- **语言：** Python 3.x
- **数据库：** SQLite3
- **微信解密：** PyWxDump
- **任务管理：** kanban-doc MCP
- **定时任务：** Windows任务计划程序 / Cron

## 📊 性能优化

### 1. 索引优化
- 在talker、create_time、content字段建立索引
- 搜索速度从2分钟降至0.1秒

### 2. 增量同步
- 记录最后同步时间
- 只同步新消息，避免重复处理

### 3. 批量操作
- 使用executemany批量插入
- 减少数据库I/O次数

### 4. 内存优化
- 分批处理大量消息
- 及时释放不需要的数据

## 🔐 安全考虑

- 微信数据库密钥本地存储
- 不上传敏感信息到云端
- 索引数据库本地保存
- 任务列表不包含完整聊天内容

## 🚀 扩展性

### 支持的扩展方向
1. **多渠道支持：** 邮件、钉钉、Slack等
2. **LLM集成：** 更智能的内容分析
3. **自动回复：** 自动回复用户反馈
4. **数据分析：** 需求趋势分析、用户画像
5. **通知系统：** 邮件/微信通知新任务

### 扩展接口
- `RequirementCollector` 可继承扩展识别规则
- `WeChatIndexDB` 可扩展支持其他数据源
- `auto_workflow.py` 可插入自定义处理步骤
