---
id: mod-sync-monitor
type: module-design
title: 数据同步与实时监控
status: draft
parent: arch-overview
depends-on:
  - mod-wxmanager
  - mod-config
references:
  - sub-realtime-monitor
---

# 数据同步与实时监控

## 职责

把解密产物变成可消费的明文数据资产，提供「全量 + 增量 + 实时」三档数据新鲜度：

- **全量同步**：`wechat_sync.py` 一键工作流——解密数据库 → 遍历所有 `MSG*.db` → 导出指定群聊/联系人 → 生成报告。Windows 多进程兼容（`freeze_support`），输出统一 UTF-8。
- **增量同步**：`incremental_sync.py` 按索引库中已有最大时间戳，仅同步新增消息到索引库；不依赖 wxManager/yara，可独立运行。
- **消息索引**：`wechat_index_db.py` 维护 `output/wechat_index.db`，索引联系人、群聊与全量消息，是分析层快速检索的数据基础。
- **实时监控**：`wechat_realtime_monitor_clean.py` 基于 watchdog 监听解密库文件变化，去抖后秒级捕获新消息，替代旧的 30 分钟轮询机制。实时监控的实现细节由子节点 spec `sub-realtime-monitor`（docs/realtime_monitor.md）描述，此处不重复。

## 输入

- 解密产物：`output/decrypted_db/` 下的明文 SQLite 库（由 mod-wxmanager 产出）。
- 配置：联系人/群 ID 等经 mod-config 提供。

## 输出

- 只写 `output/` 下的明文产物：导出数据、索引库、监控日志与报告。

## 边界

- **绝不回写微信原始库**；写操作只落在 `output/`。
- 解密动作只经 wxManager.decrypt（mod-wxmanager）进行，本模块不实现自有解密算法。
- 根目录 `search_*.py` 等一次性检索脚本在模块边界之外。
- 历史监控变体（`wechat_monitor*.py`、`wechat_realtime_monitor` 无后缀/_v2/_fixed）为遗留代码，实时监控以 `wechat_realtime_monitor_clean.py` 为准。
