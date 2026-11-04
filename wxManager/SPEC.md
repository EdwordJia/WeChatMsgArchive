---
id: mod-wxmanager
type: module-design
title: 微信数据库解密与读写（wxManager）
status: draft
parent: arch-overview
---

# 微信数据库解密与读写（wxManager）

## 职责

继承自上游 WeChatMsg/MemoTrace 的核心包，是全系统唯一同时理解"微信加密存储"与"微信数据模型"的层，做三件事：

1. **密钥提取**：从运行中的微信进程内存读取解密密钥（pymem / psutil / pywin32 / ctypes `ReadProcessMemory`），支持个人微信 v3（`WeChat.exe`）、v4（`Weixin.exe`）与企业微信（`wxwork`）；版本特征偏移存于 `decrypt/version_list.json`。
2. **解密**：AES 分页解密本地 SQLite 库（v3：AES-256-CBC，算法 lineage 来自 PyWxDump；v3 增强版连同 WAL 文件一起解密；v4：AES + PBKDF2-HMAC-SHA512），以及 `.dat` 图片资源解密（`decrypt_dat`）。
3. **统一读写访问与数据模型**：`db_v3/`、`db_v4/` 按库拆分的读取器（Msg、MicroMsg、Contact、Message、Media 等），由 `manager_v3.DataBaseV3` / `manager_v4.DataBaseV4` 实现 `db_main.DataBaseInterface` 统一接口；`__init__.py` 的 `DatabaseConnection` 按版本号（3/4）选择实现。消息 XML / protobuf 解析在 `parser/`（v4 用 `FACTORY_REGISTRY` 工厂 + protobuf 定义），数据模型（`Message`、`Contact`、`Me`、`MessageType` 等）在 `model/`。

## 边界

- **唯一解密入口**：只有 `wxManager.decrypt` 允许接触加密数据库与微信进程内存；明文产物只写在 `output/` 下，不回写任何微信原始库（架构不变量 1、2）。
- 上层模块（导出、同步、分析、MCP）只消费本包产出的明文库或经 `DataBaseInterface` 访问的数据，不得自行实现解密。
- 本包**不含**分析与导出逻辑；`decrypt_dat` 的批量图片解码函数被 `exporter` 复用，这属于对明文资源的解码，不构成对加密数据库的依赖反转。
- `merge.py` 提供已解密库之间的合并能力（具体调用方未确认）。
