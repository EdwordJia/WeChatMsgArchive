---
id: mod-mcp-server
type: module-design
title: 微信数据 MCP 服务
status: draft
parent: arch-overview
depends-on:
  - mod-sync-monitor
---

# 微信数据 MCP 服务

## 职责

通过 MCP 协议（stdio 传输，`python -m mcp_servers.wechat_data.server` 启动）向 AI 工具（Claude Code 等）暴露标准化的**只读**查询接口：

- 消息搜索（关键词 + 最近 N 天时间范围）
- 指定联系人 / 群聊的消息记录（群聊支持按成员筛选）
- 联系人信息、群聊列表
- 高级分析类工具（`advanced_tools.py`）：消息统计、情感分析、趋势检测、关系强度、报告导出

## 结构

- `server.py`：MCP server 入口，注册工具并处理 list/call 请求。
- `tools.py`：`WeChatTools` 工具定义与参数校验。
- `database.py`：sqlite3 查询层，默认读 `output/wechat_index.db`，群聊查询直读 `output/decrypted_db/Multi/MSG*.db`。
- `advanced_tools.py`：基于查询结果的高级分析工具。

## 边界

- **只读**：服务对数据库不做任何写操作（代码中无 INSERT/UPDATE/CREATE）。
- 数据源是 `output/` 下的明文库（索引库 + 解密库），由同步/监控流程（mod-sync-monitor）产出；本服务**不做解密**，也不接触加密库或进程内存。
- 新增查询能力 = 在 `database.py` 加查询、在 `tools.py`/`server.py` 注册工具，不得绕过查询层直接拼 SQL 到 server。
