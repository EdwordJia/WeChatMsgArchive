---
name: wechat-decrypt-db
description: Decrypt WeChat database and export group chat messages in one step. Use when the user wants to refresh WeChat data, update chat records, decrypt WeChat DB, or pull latest messages from a group chat. Triggers on keywords like "解密数据库", "刷新数据库", "更新聊天数据", "重新解密", "decrypt", "refresh db", "拉取消息", "同步微信".
---

# 微信消息同步技能

**一体化脚本**: `wechat_sync_facade.py` — 自动检测运行中的微信进程，自动路由 v3/v4 链路，最终将消息汇总到索引库 `output/wechat_index.db`。

## 前置条件

- 微信必须已登录并正在运行 (`WeChat.exe` 或 `Weixin.exe`)
- v3 链路需要管理员权限读取进程内存
- 必须使用项目 venv 环境: `./venv/Scripts/python`

## 快速用法

### 方式一：一键同步（推荐）

```bash
cd WeChatMsgArchive
./venv/Scripts/python wechat_sync_facade.py
```

- 自动检测进程：`WeChat.exe` → v3 链路；`Weixin.exe` → v4 链路
- 如两个进程都在运行，优先使用 v4
- 最终结果汇总到 `output/wechat_index.db` 的 `messages` 表
- 支持参数：
  - `--version v3` / `--version v4`：强制指定版本
  - `--decrypt-only`：只解密，不同步到索引库
  - `--dry-run`：只检测版本，不实际执行

### 方式二：分步执行（高级）

当只需要执行其中一环，或排查问题时使用。

**v3 链路（`WeChat.exe`）**

Step 1 — 解密数据库
```bash
./venv/Scripts/python decrypt_single.py
```
- 单线程解密，避免 Windows 多进程崩溃
- 输出到 `output/decrypted_db/`
- 自动清除旧解密文件

Step 2 — 增量同步到索引库
```bash
./venv/Scripts/python incremental_sync.py
```
- 将解密后的 MSG*.db 增量写入 `output/wechat_index.db`

**v4 链路（`Weixin.exe`）**

Step 1 — 解密数据库
```bash
./venv/Scripts/python _tools/wechat-decrypt/main.py decrypt
```
- 在 `_tools/wechat-decrypt/` 目录下运行
- 输出到 `_tools/wechat-decrypt/decrypted/`（默认）

Step 2 — 导出增量聊天记录
```bash
./venv/Scripts/python _tools/wechat-decrypt/export_all_chats.py -i
```
- `-i` 表示增量导出
- 生成 JSON 格式聊天记录

Step 3 — 导入索引库
```bash
./venv/Scripts/python import_ylytdeng_to_index.py
```
- 将 v4 导出的 JSON 消息合并到 `output/wechat_index.db`

## 技术细节

### 为什么用单线程解密？

`decrypt_v3.decrypt_db_files()` 内部使用 `ProcessPoolExecutor`，在 Windows 上会报错：
```
RuntimeError: An attempt has been made to start a new process before
the current process has finished its bootstrapping phase.
```

**解决方案**: `decrypt_single.py` 使用 `decrypt_db_file_v3()` 单文件函数逐个解密，配合 `freeze_support()`，Windows 稳定运行。

### 索引库结构

同步终点为 `output/wechat_index.db` 的 `messages` 表：

```sql
msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
local_id INTEGER,
talker TEXT,
sender_wxid TEXT,
msg_type INTEGER,
content TEXT,
create_time INTEGER,
is_sender INTEGER,
source_db TEXT,
indexed_at INTEGER
```

`talker` 对应微信群/私聊 ID（如 `xxx@chatroom`），`sender_wxid` 为发送者 wxid。索引库覆盖 v3/v4 全量消息，推荐优先查询。

### 群成员查找技巧

群成员列表在 `MicroMsg.db` 的 `ChatRoom` 表，字段 `UserNameList` 用字面字符 `^G`（ASCII 7，不是 `\x07`）分隔成员 wxid。

```python
conn = sqlite3.connect('output/decrypted_db/MicroMsg.db')
rows = conn.execute(
    "SELECT ChatRoomName, UserNameList FROM ChatRoom WHERE ChatRoomName = ?",
    ('44637051187@chatroom',)
).fetchall()
for room_id, members in rows:
    member_list = members.split('\x07')  # 实际是分格符
    print(f'{room_id}: {len(member_list)} 人')
```

## 输出示例

```
==================================================
微信消息同步工作流
开始时间: 2026-07-01 10:30:00
==================================================

[+] 使用微信 v4 同步链路
==================================================
  微信 v4 同步链路
==================================================
[*] D:\...\venv\Scripts\python.exe _tools\wechat-decrypt\main.py decrypt
[*] cwd=D:\...\WeChatMsgArchive\_tools\wechat-decrypt
...
[*] 耗时=120.0s, returncode=0
[*] D:\...\venv\Scripts\python.exe _tools\wechat-decrypt\export_all_chats.py -i
...
[*] 耗时=300.0s, returncode=0
[*] D:\...\venv\Scripts\python.exe import_ylytdeng_to_index.py
...
[*] 耗时=60.0s, returncode=0
索引库总消息: 2661633 条
最新消息时间: 2026-07-01 10:28:00

==================================================
同步报告
==================================================
版本: v4
开始: 2026-07-01 10:30:00
结束: 2026-07-01 11:00:00
结果: 成功
步骤:
  [OK] 版本检测 (2026-07-01 10:30:00)
  [OK] 解密数据库 (2026-07-01 10:32:00)
  [OK] 导出聊天记录 (2026-07-01 10:37:00)
  [OK] 导入索引库 (2026-07-01 10:59:00)
==================================================
```

## 文件说明

| 文件 | 用途 | 推荐 |
|---|---|---|
| `wechat_sync_facade.py` | 一键自动检测版本并执行 v3/v4 同步链路 | 首选 |
| `decrypt_single.py` | v3 单线程解密 | 备用 |
| `incremental_sync.py` | v3 增量同步到索引库 | 备用 |
| `_tools/wechat-decrypt/main.py` | v4 解密入口 | 备用 |
| `_tools/wechat-decrypt/export_all_chats.py` | v4 导出增量聊天记录 | 备用 |
| `import_ylytdeng_to_index.py` | 将 v4 JSON 消息导入索引库 | 备用 |

## 注意事项

- v3 链路解密前会自动删除 `output/decrypted_db/`，确保数据最新
- 必须以管理员权限运行 v3 链路
- 如果密钥获取失败，重启微信通常能解决
- 索引库 `output/wechat_index.db` 是 v3/v4 的汇总终点，查询优先使用
- 脚本内置 `freeze_support()` 和 `sys.stdout.reconfigure(encoding='utf-8')`，Windows 兼容
