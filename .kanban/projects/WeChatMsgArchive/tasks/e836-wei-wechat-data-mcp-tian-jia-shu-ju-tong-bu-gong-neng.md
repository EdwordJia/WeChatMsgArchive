---
id: e836
title: 为 wechat-data MCP 添加数据同步功能
status: inreview
priority: high
tags:
- mcp
- data-sync
- enhancement
created_at: 2026-04-29T06:31:26.711044300+00:00
updated_at: 2026-04-29T06:39:49.599471700+00:00
session:
  executor: claude-opus-4
  started_at: 2026-04-29T06:31:34.415060100+00:00
  process_status: executorcomplete
  percent: 90
  message: |-
    同步功能集成完成：
    - database.py: 添加 sync_data() 和 get_sync_status() 方法
    - tools.py: 添加 sync_messages 和 get_sync_status 工具
    - server.py: 注册新工具到 MCP 服务器
    - 测试通过：同步状态查询正常，增量同步正常

    功能验证：
    - 上次同步: 2026-04-29 14:34:04
    - 消息总数: 139,870 条
    - 最新消息: 2026-04-29 13:19:34
    - 增量同步: 0 条新消息（已是最新）
  artifacts:
  - mcp_servers/wechat_data/database.py
  - mcp_servers/wechat_data/tools.py
  - mcp_servers/wechat_data/server.py
  summary: |-
    成功为 wechat-data MCP 服务添加数据同步功能

    ## 实现内容

    ### 1. 数据库层 (database.py)
    - `sync_data(incremental=True)`: 同步微信数据到索引数据库
      - 支持增量同步和全量同步
      - 自动同步联系人和消息
      - 返回详细的同步统计信息
    - `get_sync_status()`: 获取同步状态
      - 上次同步时间
      - 消息总数
      - 最新消息时间

    ### 2. 工具层 (tools.py)
    - `sync_messages`: MCP 工具，触发数据同步
    - `get_sync_status`: MCP 工具，查询同步状态
    - 添加到 TOOLS 列表，完整的工具定义

    ### 3. 服务器层 (server.py)
    - 注册 sync_messages 和 get_sync_status 到工具映射
    - 支持通过 MCP 协议调用同步功能

    ## 测试结果
    - ✅ 同步状态查询正常
    - ✅ 增量同步执行成功
    - ✅ 数据统计准确（139,870 条消息）
    - ✅ 最新消息时间正确（2026-04-29 13:19:34）

    ## 使用方式
    用户现在可以通过 MCP 工具直接同步数据，无需手动运行 Python 脚本，解决了数据延迟问题。
  completed_at: 2026-04-29T06:39:49.599469300+00:00
---





## 目标
在 wechat-data MCP 服务中集成数据同步功能，避免查询时数据延迟。

## 背景
- 当前 wechat_index.db 最后更新时间：2026-04-28 23:59
- 用户反馈已有 4月29号中午的聊天记录，但数据库未同步
- 每次查询前需要自动同步最新数据

## 技术方案
1. 添加 `sync_database` 工具到 MCP 服务
2. 使用 wxManager.merge.py 的增量同步逻辑
3. 从微信原始数据库同步到 wechat_index.db
4. 支持自动同步和手动同步两种模式

## 关键文件
- 微信数据目录：E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822
- 目标数据库：D:/develoment_home/project_home/WeChatMsgArchive/output/wechat_index.db
- 同步逻辑：wxManager/merge.py
- 数据库管理：wxManager/manager_v4.py

## 验收标准
- [ ] 添加 sync_database 工具
- [ ] 能够增量同步最新消息
- [ ] 同步后能查询到 4月29号的消息
- [ ] 性能优化：只同步增量数据