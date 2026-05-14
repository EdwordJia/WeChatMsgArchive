# 文件清单

## 📁 项目文件结构

```
WeChatMsgArchive/
├── snapshot/                           # 状态快照目录
│   └── 20260429_0919/                 # 本次快照
│       ├── 00_PROJECT_STATUS.md       # 项目状态总览
│       ├── 01_ARCHITECTURE.md         # 系统架构说明
│       ├── 02_QUICK_START.md          # 快速启动指南
│       ├── 03_TEST_RESULTS.md         # 测试结果报告
│       ├── 04_FILE_INVENTORY.md       # 文件清单（本文件）
│       ├── 05_TODO_LIST.md            # 待办事项
│       └── 06_CONFIG_REFERENCE.md     # 配置参考
│
├── output/                             # 输出目录
│   ├── wechat_index.db                # 索引数据库（138,947条消息）
│   ├── pending_kanban_tasks.json      # 完整任务列表（213个）
│   ├── tasks_to_create.json           # 待创建任务（47个）
│   ├── cron_logs/                     # 监控日志目录
│   │   └── monitor_v2_*.log           # 定时监控日志
│   └── 需求文档_林爱新B-boy前程群.md   # 需求文档示例
│
├── 核心系统文件/
│   ├── wechat_index_db.py             # 索引数据库系统（核心）
│   ├── auto_requirement_collector.py  # 智能需求收集器
│   ├── auto_workflow.py               # 自动化工作流
│   ├── wechat_monitor_v2.py           # 定时监控（优化版）
│   ├── create_kanban_tasks.py         # Kanban任务创建辅助
│   └── README_AUTO_SYSTEM.md          # 完整系统文档
│
├── 旧系统文件（参考）/
│   ├── wechat_monitor.py              # 旧版监控系统
│   ├── cron_analyze.py                # 简化测试脚本
│   ├── user_profiling.py              # 用户画像分析
│   └── social_graph_analysis.py       # 关系图谱分析
│
├── 测试脚本/
│   ├── test_search.py                 # 搜索功能测试
│   └── test_collector.py              # 需求收集测试
│
└── 其他文件/
    ├── check_msg_structure.py         # 消息结构检查
    ├── find_group.py                  # 查找群聊
    ├── list_groups.py                 # 列出所有群聊
    └── ...                            # 其他辅助脚本
```

## 📄 核心文件详解

### 1. wechat_index_db.py
**功能：** 索引数据库系统
**大小：** ~15KB
**行数：** ~400行
**依赖：** sqlite3, pywxdump

**核心类：**
- `WeChatIndexDB` - 索引数据库管理器

**核心方法：**
- `full_sync()` - 全量同步
- `incremental_sync()` - 增量同步
- `search_messages()` - 搜索消息
- `get_user_messages()` - 获取用户消息

**使用方式：**
```bash
# 全量同步
python wechat_index_db.py full

# 增量同步
python wechat_index_db.py incremental
```

### 2. auto_requirement_collector.py
**功能：** 智能需求收集器
**大小：** ~12KB
**行数：** ~350行
**依赖：** sqlite3, json

**核心类：**
- `RequirementCollector` - 需求收集器

**核心方法：**
- `collect_requirements()` - 收集需求
- `_is_requirement()` - 判断是否为需求
- `_is_bug()` - 判断是否为Bug
- `_get_priority()` - 获取优先级
- `_identify_project()` - 识别项目

**配置项：**
- 监控用户列表
- 需求关键词
- Bug关键词
- 项目关键词

**使用方式：**
```bash
python auto_requirement_collector.py
```

### 3. auto_workflow.py
**功能：** 自动化工作流编排
**大小：** ~8KB
**行数：** ~200行
**依赖：** wechat_index_db, auto_requirement_collector

**核心函数：**
- `decrypt_databases()` - 解密数据库
- `sync_to_index()` - 同步到索引
- `collect_requirements()` - 收集需求
- `filter_tasks()` - 筛选任务
- `main()` - 主流程

**使用方式：**
```bash
python auto_workflow.py
```

### 4. wechat_monitor_v2.py
**功能：** 定时监控系统
**大小：** ~10KB
**行数：** ~250行
**依赖：** auto_workflow

**核心功能：**
- 定时执行完整流程
- 生成监控日志
- 输出待创建任务列表

**使用方式：**
```bash
# 手动运行
python wechat_monitor_v2.py

# Windows任务计划程序
schtasks /create /tn "WeChatMonitor" /tr "python wechat_monitor_v2.py" /sc minute /mo 30
```

### 5. create_kanban_tasks.py
**功能：** Kanban任务创建辅助
**大小：** ~5KB
**行数：** ~120行
**依赖：** json, kanban-doc MCP

**核心功能：**
- 读取tasks_to_create.json
- 通过kanban-doc MCP创建任务
- 批量创建支持

**使用方式：**
```python
# 在Claude Code中运行
python create_kanban_tasks.py
```

### 6. README_AUTO_SYSTEM.md
**功能：** 完整系统文档
**大小：** ~25KB
**内容：**
- 系统概述
- 核心功能
- 使用方式
- 配置说明
- 性能指标
- 扩展建议

## 📊 数据文件详解

### 1. output/wechat_index.db
**类型：** SQLite数据库
**大小：** ~50MB
**记录数：** 138,947条消息

**表结构：**
```sql
-- 联系人表
contacts (wxid, nickname, remark, first_seen, last_seen)

-- 群聊表
chatrooms (chatroom_id, name, member_count, first_seen, last_seen)

-- 消息表
messages (id, msg_id, talker, type, content, create_time, db_file)

-- 同步状态表
sync_state (db_file, last_sync_time, message_count)
```

### 2. output/pending_kanban_tasks.json
**类型：** JSON文件
**大小：** ~150KB
**记录数：** 213个任务

**格式：**
```json
{
  "user": "用户昵称",
  "content": "消息内容",
  "time": "2026-04-29 12:00:00",
  "priority": "high",
  "type": "bug",
  "project": "syc-player"
}
```

### 3. output/tasks_to_create.json
**类型：** JSON文件
**大小：** ~35KB
**记录数：** 47个任务（筛选后）

**筛选条件：**
- 时间范围：最近7天
- 优先级：medium及以上

### 4. output/cron_logs/
**类型：** 日志目录
**文件数：** 11个
**总大小：** ~50KB

**日志格式：**
```
monitor_v2_20260429_0200.log
monitor_v2_20260429_0230.log
...
```

## 🔧 测试文件详解

### 1. test_search.py
**功能：** 测试索引数据库搜索
**大小：** ~3KB
**测试项：**
- 关键词搜索
- 用户消息查询
- 搜索性能

### 2. test_collector.py
**功能：** 测试需求收集器
**大小：** ~4KB
**测试项：**
- 需求识别
- Bug识别
- 优先级判断
- 项目识别

## 📋 旧系统文件（参考）

### 1. wechat_monitor.py
**状态：** 已被wechat_monitor_v2.py替代
**保留原因：** 参考和备份
**主要问题：** 只搜索MSG0.db，搜索慢

### 2. cron_analyze.py
**状态：** 简化测试脚本
**用途：** 快速测试用户画像分析

### 3. user_profiling.py
**状态：** 独立功能模块
**用途：** 用户画像分析（未集成到主流程）

### 4. social_graph_analysis.py
**状态：** 独立功能模块
**用途：** 关系图谱分析（未集成到主流程）

## 📦 依赖文件

### Python依赖
```
pywxdump  - 微信数据库解密
sqlite3   - 数据库操作（内置）
json      - JSON处理（内置）
datetime  - 时间处理（内置）
```

### 外部依赖
```
kanban-doc MCP  - 任务管理系统
微信数据库      - 数据源
```

## 🗂️ 文件大小统计

```
核心系统文件:     ~50KB
测试脚本:         ~7KB
文档文件:         ~100KB
数据文件:         ~50MB
日志文件:         ~50KB
快照文件:         ~150KB

总计:             ~50.4MB
```

## 📝 文件版本

**创建时间：** 2026-04-29 02:00
**最后更新：** 2026-04-29 09:19
**版本：** 1.0

## 🔄 文件依赖关系

```
wechat_monitor_v2.py
    ↓
auto_workflow.py
    ↓
    ├── wechat_index_db.py
    │       ↓
    │   微信数据库
    │
    └── auto_requirement_collector.py
            ↓
        wechat_index_db.py
            ↓
        output/pending_kanban_tasks.json
            ↓
        output/tasks_to_create.json
            ↓
        create_kanban_tasks.py
            ↓
        kanban-doc MCP
```

## 🎯 关键文件优先级

**必须保留：**
1. wechat_index_db.py
2. auto_requirement_collector.py
3. auto_workflow.py
4. output/wechat_index.db

**建议保留：**
1. wechat_monitor_v2.py
2. create_kanban_tasks.py
3. README_AUTO_SYSTEM.md
4. snapshot/

**可选保留：**
1. test_*.py
2. 旧系统文件
3. 日志文件

## 📞 文件问题排查

**如果缺少核心文件：**
- 查看snapshot/目录的备份
- 查看git历史记录
- 重新生成（如果是数据文件）

**如果数据文件损坏：**
- 删除output/wechat_index.db
- 运行 `python wechat_index_db.py full`
- 重新生成索引
