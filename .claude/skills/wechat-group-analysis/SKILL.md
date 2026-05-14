---
name: wechat-group-analysis
description: Extract and analyze all messages from a specific WeChat group chat using decrypted MSG0.db and MicroMsg.db. Exports full conversation history with sender names, statistics by date and member, and outputs CSV and TXT files. Use when the user wants to view a group chat, analyze group messages, export group history, see who said what in a group, or get group statistics. Triggers on keywords like "看群聊", "导出群消息", "分析群聊", "群聊记录", "群成员发言", group chat export.
---

# 微信群聊分析技能

提取指定群聊的完整聊天记录，识别发送者真实昵称，生成统计报告并导出文件。

## 数据库位置

```
output/decrypted_db/Multi/MSG0.db    # 消息记录
output/decrypted_db/MicroMsg.db      # 联系人 & 群成员信息
output/decrypted_db/info.json        # 自己的 wxid
```

## Instructions

### Step 1: 解析 BytesExtra 获取发送者 wxid

群消息的发送者存储在 `BytesExtra` 字段（protobuf 格式），需手动解析：

```python
def parse_bytes_extra(data):
    """从 BytesExtra 中提取发送者 wxid"""
    if not data:
        return None
    try:
        i = 0
        while i < len(data):
            if data[i] == 0x1a:
                i += 1
                if i >= len(data): break
                length = data[i]; i += 1
                sub = data[i:i+length]
                j = 0
                while j < len(sub):
                    if sub[j]==0x08 and j+1<len(sub) and sub[j+1]==0x01 and j+2<len(sub) and sub[j+2]==0x12:
                        j += 3
                        wxid_len = sub[j]; j += 1
                        return sub[j:j+wxid_len].decode('utf-8', errors='ignore')
                    j += 1
                i += length
            else:
                i += 1
    except:
        pass
    return None
```

### Step 2: 加载群成员映射

```python
import sqlite3, json

micro_db = 'output/decrypted_db/MicroMsg.db'
conn_micro = sqlite3.connect(micro_db)
cur_micro = conn_micro.cursor()

# 读取自己的 wxid
with open('output/decrypted_db/info.json') as f:
    my_wxid = json.load(f).get('wxid', '')

# 从 ChatRoom 表获取群成员列表
group_id = '49487213350@chatroom'   # 替换为目标群 ID
cur_micro.execute('SELECT UserNameList FROM ChatRoom WHERE ChatRoomName=?', (group_id,))
row = cur_micro.fetchone()

member_map = {my_wxid: '我'}
if row and row[0]:
    for wxid in row[0].split('^G'):
        if not wxid: continue
        cur_micro.execute('SELECT NickName, Remark FROM Contact WHERE UserName=?', (wxid,))
        c = cur_micro.fetchone()
        member_map[wxid] = (c[1] or c[0]) if c else wxid
```

### Step 3: 提取群消息

```python
msg_db = 'output/decrypted_db/Multi/MSG0.db'
conn_msg = sqlite3.connect(msg_db)
cur_msg = conn_msg.cursor()

cur_msg.execute("""
    SELECT Type, IsSender, CreateTime, StrContent, BytesExtra
    FROM MSG WHERE StrTalker=? ORDER BY CreateTime
""", (group_id,))

messages = []
for msg_type, is_sender, ts, content, bytes_extra in cur_msg.fetchall():
    sender_wxid = my_wxid if is_sender else (parse_bytes_extra(bytes_extra) or '')
    sender_name = member_map.get(sender_wxid, sender_wxid or '未知')
    ts_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else '未知'

    type_map = {1:'文本',3:'图片',34:'语音',43:'视频',47:'表情包',10000:'系统消息',49:'链接/文件'}
    type_name = type_map.get(msg_type, f'类型{msg_type}')

    text_map = {3:'[图片]',34:'[语音]',43:'[视频]',47:'[表情包]',49:'[链接/文件]'}
    text = text_map.get(msg_type, content or f'[{type_name}]') if msg_type != 1 else (content or '')

    messages.append((ts_str, sender_name, type_name, text, msg_type))
```

### Step 4: 生成统计数据

```python
from collections import Counter
from datetime import datetime

# 排除系统消息
real_msgs = [m for m in messages if m[4] != 10000]
sender_cnt = Counter(m[1] for m in real_msgs)
date_cnt   = Counter(m[0][:10] for m in real_msgs)
type_cnt   = Counter(m[2] for m in messages)
```

### Step 5: 导出文件

```python
import csv, os

safe_name = group_id.replace('@chatroom', '')
out_dir = 'output'

# TXT
with open(f'{out_dir}/group_{safe_name}_full.txt', 'w', encoding='utf-8') as f:
    f.write(f'群ID: {group_id}\n总消息数: {len(messages)}\n\n')
    for ts, name, type_name, text, _ in messages:
        f.write(f'[{ts}] {name}\n{text}\n\n')

# CSV
with open(f'{out_dir}/group_{safe_name}_full.csv', 'w', newline='', encoding='utf-8-sig') as f:
    csv.writer(f).writerows([['时间','发送者','消息类型','内容']] +
                             [(m[0],m[1],m[2],m[3]) for m in messages])

# 统计报告
with open(f'{out_dir}/group_{safe_name}_stats.txt', 'w', encoding='utf-8') as f:
    f.write(f'总消息: {len(messages)}\n\n【发言排行】\n')
    for name, cnt in sender_cnt.most_common():
        f.write(f'  {name}: {cnt}条\n')
    f.write('\n【按日期】\n')
    for d in sorted(date_cnt): f.write(f'  {d}: {date_cnt[d]}条\n')
    f.write('\n【消息类型】\n')
    for t, c in type_cnt.most_common(): f.write(f'  {t}: {c}条\n')
```

### Step 6: 控制台汇总输出

以结构化格式展示：群名、成员数、消息总数、时间跨度、发言排行 Top5、类型分布

## 注意事项

- `IsSender=1` 表示消息为自己发送，无需解析 BytesExtra
- 群 ID 格式固定为 `xxxxx@chatroom`
- 企业微信成员 wxid 为 `xxxxx@openim`，在 Contact 表中可能查不到昵称
- MSG0.db 只包含近期消息，历史消息可能在 Multi/MSG1.db 等文件中

## 输出格式

```
=== 群聊分析：[群名] ===
群ID: 49487213350@chatroom
成员数: 4
总消息数: 535
时间跨度: 2026-04-05 ~ 2026-04-10

【发言排行】
  三叶草:     285条 (53%)
  我:         229条 (43%)
  往事如风:     9条 ( 2%)

【消息类型】
  文本: 401 | 链接/文件: 79 | 图片: 28 | 视频: 13

已导出:
  output/group_49487213350_full.txt
  output/group_49487213350_full.csv
  output/group_49487213350_stats.txt
```
