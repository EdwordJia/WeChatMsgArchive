---
name: wechat-contact-search
description: Search WeChat contacts by nickname or remark name in MicroMsg.db, then find which group chats they belong to. Use when the user wants to find a contact, look up a member, search for someone by name, or locate which groups a person is in. Triggers on keywords like "查找联系人", "找成员", "谁在哪个群", "搜索用户", "找到xxx", contact name lookup.
---

# 微信联系人搜索技能

在解密后的微信数据库中，按昵称或备注名搜索联系人，并找出其所在的所有群聊。

## 数据库位置

首选索引库：

```
output/wechat_index.db                  # v3/v4 汇总索引库（定位 talker/sender_wxid）
```

联系人/群成员详细信息：

```
output/decrypted_db/MicroMsg.db         # 联系人 & 群聊数据（昵称/备注/群成员）
```

## Instructions

### Step 0: 优先 — 从索引库定位联系人发言

如果已知联系人 wxid，可以先从索引库反查其出现过的 talker：

```python
import sqlite3

index_db = 'output/wechat_index.db'
conn = sqlite3.connect(index_db)
cur = conn.cursor()

target_wxid = 'wxid_xxx'  # 替换为目标 wxid

# 该联系人作为发送者出现过的所有 talker
cur.execute("""
    SELECT DISTINCT talker
    FROM messages
    WHERE sender_wxid = ?
""", (target_wxid,))
talkers = [row[0] for row in cur.fetchall()]
print(f'联系人 {target_wxid} 在以下 talker 中有发言:')
for t in talkers:
    print(f'  {t}')
```

也可以列出索引库中所有已知的发送者 wxid，用于交叉定位：

```python
cur.execute("""
    SELECT DISTINCT sender_wxid
    FROM messages
    WHERE sender_wxid IS NOT NULL AND sender_wxid != ''
    ORDER BY sender_wxid
""")
wxids = [row[0] for row in cur.fetchall()]
print(f'索引库中共有 {len(wxids)} 个不同 sender_wxid')
```

> 联系人昵称、备注、群成员列表仍需 `MicroMsg.db`。先尝试索引库反查 talker，必要时再解密 MicroMsg.db。

### Step 1: 连接数据库

```python
import sqlite3, os, sys
sys.stdout.reconfigure(encoding='utf-8')

db_path = 'output/decrypted_db/MicroMsg.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
```

### Step 2: 按昵称/备注搜索联系人

```python
keyword = '三叶草'   # 替换为用户输入的关键词

cur.execute("""
    SELECT UserName, NickName, Remark
    FROM Contact
    WHERE NickName LIKE ? OR Remark LIKE ?
""", (f'%{keyword}%', f'%{keyword}%'))

contacts = cur.fetchall()
for wxid, nickname, remark in contacts:
    print(f'wxid: {wxid} | 昵称: {nickname} | 备注: {remark}')
```

### Step 3: 查找联系人所在群聊

```python
for wxid, nickname, remark in contacts:
    cur.execute("""
        SELECT ChatRoomName, UserNameList
        FROM ChatRoom
        WHERE UserNameList LIKE ?
    """, (f'%{wxid}%',))

    rooms = cur.fetchall()
    for room_id, _ in rooms:
        # 获取群显示名
        cur.execute("""
            SELECT strNickName FROM Session WHERE strUsrName = ?
        """, (room_id,))
        row = cur.fetchone()
        room_name = row[0] if row else room_id
        print(f'  → 群: {room_name} ({room_id})')
```

### Step 4: 输出汇总结果

以表格形式展示：
- 找到的联系人列表（wxid / 昵称 / 备注）
- 每个联系人所在的群聊列表（群名 / 群ID）

### Step 5: 关闭连接

```python
conn.close()
```

## 注意事项

- `UserNameList` 字段以 `^G` 分隔多个成员 wxid
- 企业微信成员 wxid 格式为 `xxxxx@openim`，群 ID 格式为 `xxxxx@chatroom`
- 同一昵称可能对应多个不同 wxid（同名用户）
- 索引库 `output/wechat_index.db` 可快速定位联系人在哪些 talker 中有发言，推荐优先反查
- 若 `Session` 表无群名，则使用 `Contact` 表的 `NickName` 字段兜底

## 输出格式

```
=== 搜索结果：[关键词] ===

找到 N 个联系人：
  1. wxid_xxx | 昵称: 三叶草 | 备注: 潘苗苗
     所在群聊：
       - 同袍一圈 交流群 (45622088590@chatroom)
       - 群聊 (49487213350@chatroom)

  2. wxid_yyy | 昵称: 三叶草 | 备注: （无）
     所在群聊：（未加入任何已知群聊）
```
