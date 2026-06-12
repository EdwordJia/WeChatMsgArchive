---
name: wechat-decrypt-db
description: Decrypt WeChat database and export group chat messages in one step. Use when the user wants to refresh WeChat data, update chat records, decrypt WeChat DB, or pull latest messages from a group chat. Triggers on keywords like "解密数据库", "刷新数据库", "更新聊天数据", "重新解密", "decrypt", "refresh db", "拉取消息", "同步微信".
---

# 微信消息同步技能

**一体化脚本**: `wechat_sync.py` — 一键完成解密 + 导出群聊 + 生成报告。

## 前置条件

- 微信必须已登录并正在运行 (`WeChat.exe` 或 `Weixin.exe`)
- 需要管理员权限读取进程内存
- 必须使用项目 venv 环境: `./venv/Scripts/python`

## 快速用法

### 方式一：一键同步（推荐）

```bash
cd WeChatMsgArchive
./venv/Scripts/python wechat_sync.py [群ID]
```

- 不带参数：默认导出群 `44637051187@chatroom`
- 带参数：导出指定群，如 `wechat_sync.py 123456789@chatroom`

### 方式二：分步执行（高级）

如果只需要解密或只需要导出：

**Step 1 — 解密数据库**
```bash
./venv/Scripts/python decrypt_single.py
```
- 单线程解密，避免 Windows 多进程崩溃
- 输出到 `output/decrypted_db/`
- 自动清除旧解密文件

**Step 2 — 导出群聊**
```bash
./venv/Scripts/python export_chat.py
```
- ⚠️ **只查 MSG1.db**，适合已知消息都在一个文件的情况
- 如需遍历所有 MSG*.db，使用 `wechat_sync.py`

## 技术细节

### 为什么用单线程解密？

`decrypt_v3.decrypt_db_files()` 内部使用 `ProcessPoolExecutor`，在 Windows 上会报错：
```
RuntimeError: An attempt has been made to start a new process before
the current process has finished its bootstrapping phase.
```

**解决方案**: `decrypt_single.py` 和 `wechat_sync.py` 都使用 `decrypt_db_file_v3()` 单文件函数逐个解密，配合 `freeze_support()`，Windows 稳定运行。

### 为什么遍历所有 MSG*.db？

微信消息按时间分片存储：
- `MSG0.db` — 较早的消息
- `MSG1.db` — 较新的消息
- `MSG2.db` — 更新的消息（群活跃时可能出现）

**只查 MSG1.db 会漏消息**。`wechat_sync.py` 自动发现并遍历所有 `MSG*.db`。

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
目标群: 44637051187@chatroom
开始时间: 2026-05-21 10:30:00

==================================================
Step 1: 解密微信数据库...
  WeChat v3: 运行中
  获取成功: wxid=wxid_ucag2pjrmhm822
  已清除旧解密文件
  解密完成: 39 个数据库
  info.json 已生成

==================================================
Step 2: 导出群聊消息...
  目标群: 44637051187@chatroom
  发现 2 个消息数据库: ['MSG0.db', 'MSG1.db']
    MSG0.db: 0 条消息
    MSG1.db: 128 条消息

  报告已生成: output/group_44637051187_latest.txt
  消息总数: 128

==================================================
最新 10 条消息摘要:
--------------------------------------------------
  [2026-05-21 08:04:18] 我
    ok，我理解下

==================================================
全部完成!
  报告文件: D:\...\output\group_44637051187_latest.txt
  导出消息: 128 条
==================================================
```

## 文件说明

| 文件 | 用途 | 推荐 |
|---|---|---|
| `wechat_sync.py` | 一键解密+导出+摘要 | ⭐ 首选 |
| `decrypt_single.py` | 仅解密（单线程） | 备用 |
| `export_chat.py` | 仅导出（只查MSG1） | 简单场景 |
| `decrypt_now.py` | 仅解密（多进程） | ❌ Windows 会崩溃 |

## 注意事项

- 解密前会自动删除 `output/decrypted_db/`，确保数据最新
- 必须以管理员权限运行
- 如果密钥获取失败，重启微信通常能解决
- 脚本内置 `freeze_support()` 和 `sys.stdout.reconfigure(encoding='utf-8')`，Windows 兼容
