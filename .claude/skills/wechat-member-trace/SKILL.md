---
name: wechat-member-trace
description: Trace and analyze all group messages sent by a specific WeChat member across multiple group chats. Searches by nickname or remark, finds all groups they belong to, extracts their messages, generates per-group and overall statistics, and exports results. Use when the user wants to see what someone said, trace a member's activity, analyze a person's messages across groups, or track chat behavior. Triggers on keywords like "追踪成员", "看xxx说了什么", "分析某人消息", "成员发言记录", "跨群消息", member message trace, user activity.
---

# 微信成员跨群消息追踪技能

根据成员昵称或备注，找出其所在的所有群聊，提取该成员的全部发言，生成统计分析并导出。

## 数据库位置

```
output/decrypted_db/Multi/MSG0.db    # 消息记录
output/decrypted_db/MicroMsg.db      # 联系人 & 群成员
output/decrypted_db/info.json        # 自己的 wxid
```

## Instructions

### Step 1: 搜索目标成员

```python
import sqlite3, json, csv, os, sys
from datetime import datetime
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')

micro_db = 'output/decrypted_db/MicroMsg.db'
conn_micro = sqlite3.connect(micro_db)
cur_micro = conn_micro.cursor()

keyword = '三叶草'  # 替换为用户输入
cur_micro.execute("""
    SELECT UserName, NickName, Remark FROM Contact
    WHERE NickName LIKE ? OR Remark LIKE ?
""", (f'%{keyword}%', f'%{keyword}%'))
targets = cur_micro.fetchall()

print(f'找到 {len(targets)} 个匹配联系人:')
for wxid, nick, remark in targets:
    print(f'  {wxid} | {nick} | {remark}')
```

### Step 2: 找出其所在群聊

```python
target_wxids = [t[0] for t in targets]
groups_for_member = {}   # { group_id: group_name }

for wxid in target_wxids:
    cur_micro.execute("""
        SELECT ChatRoomName FROM ChatRoom WHERE UserNameList LIKE ?
    """, (f'%{wxid}%',))
    for (room_id,) in cur_micro.fetchall():
        if room_id not in groups_for_member:
            cur_micro.execute('SELECT strNickName FROM Session WHERE strUsrName=?', (room_id,))
            row = cur_micro.fetchone()
            groups_for_member[room_id] = row[0] if row else room_id

print(f'\n该成员所在群聊: {len(groups_for_member)} 个')
for gid, gname in groups_for_member.items():
    print(f'  {gname} ({gid})')
```

### Step 3: 解析 BytesExtra

```python
def parse_bytes_extra(data):
    """从 BytesExtra 提取群消息发送者 wxid"""
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

### Step 4: 提取目标成员的所有消息

```python
msg_db = 'output/decrypted_db/Multi/MSG0.db'
conn_msg = sqlite3.connect(msg_db)
cur_msg = conn_msg.cursor()

type_text_map = {3:'[图片]',34:'[语音]',43:'[视频]',47:'[表情包]',49:'[链接/文件]',10000:'[系统消息]'}
all_messages = []   # (time, date, group_id, group_name, sender_wxid, type_name, text)

for group_id, group_name in groups_for_member.items():
    cur_msg.execute("""
        SELECT Type, IsSender, CreateTime, StrContent, BytesExtra
        FROM MSG WHERE StrTalker=? ORDER BY CreateTime
    """, (group_id,))

    for msg_type, is_sender, ts, content, bytes_extra in cur_msg.fetchall():
        sender_wxid = parse_bytes_extra(bytes_extra) if not is_sender else ''
        if sender_wxid not in target_wxids:
            continue   # 只保留目标成员消息

        ts_str   = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else '未知'
        date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d') if ts else '未知'
        type_map = {1:'文本',3:'图片',34:'语音',43:'视频',47:'表情包',10000:'系统消息',49:'链接/文件'}
        type_name = type_map.get(msg_type, f'类型{msg_type}')
        text = type_text_map.get(msg_type, content or '') if msg_type != 1 else (content or '')

        all_messages.append((ts_str, date_str, group_id, group_name, sender_wxid, type_name, text))
```

### Step 5: 统计分析

```python
total = len(all_messages)
group_cnt = Counter(m[3] for m in all_messages)
date_cnt  = Counter(m[1] for m in all_messages)
type_cnt  = Counter(m[5] for m in all_messages)

print(f'\n=== {keyword} 消息统计 ===')
print(f'总发言数: {total}')
print('\n【按群分布】')
for g, c in group_cnt.most_common():
    print(f'  {g}: {c}条')
print('\n【按日期分布】')
for d in sorted(date_cnt): print(f'  {d}: {date_cnt[d]}条')
print('\n【消息类型】')
for t, c in type_cnt.most_common(): print(f'  {t}: {c}条')
```

### Step 6: 导出结果

```python
out_dir = 'output'
safe_name = keyword.replace(' ', '_')

# CSV（完整记录）
csv_path = os.path.join(out_dir, f'trace_{safe_name}.csv')
with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['时间', '群名', '发送者wxid', '消息类型', '内容'])
    for m in all_messages:
        w.writerow([m[0], m[3], m[4], m[5], m[6]])

# TXT（按群分组）
txt_path = os.path.join(out_dir, f'trace_{safe_name}.txt')
with open(txt_path, 'w', encoding='utf-8') as f:
    f.write(f'=== {keyword} 跨群发言记录 ===\n总消息: {total}\n\n')
    for group_id, group_name in groups_for_member.items():
        msgs = [m for m in all_messages if m[2] == group_id]
        if not msgs: continue
        f.write(f'\n{"="*50}\n群: {group_name}\n消息数: {len(msgs)}\n{"="*50}\n\n')
        for m in msgs:
            f.write(f'[{m[0]}] ({m[5]})\n{m[6]}\n\n')

# 统计报告
stats_path = os.path.join(out_dir, f'trace_{safe_name}_stats.txt')
with open(stats_path, 'w', encoding='utf-8') as f:
    f.write(f'=== {keyword} 消息统计报告 ===\n\n总发言数: {total}\n\n')
    f.write('【按群分布】\n')
    for g, c in group_cnt.most_common(): f.write(f'  {g}: {c}条\n')
    f.write('\n【按日期分布】\n')
    for d in sorted(date_cnt): f.write(f'  {d}: {date_cnt[d]}条\n')
    f.write('\n【消息类型分布】\n')
    for t, c in type_cnt.most_common(): f.write(f'  {t}: {c}条\n')

print(f'\n已导出:\n  {csv_path}\n  {txt_path}\n  {stats_path}')
```

### Step 7: 关闭连接

```python
conn_msg.close()
conn_micro.close()
```

## 注意事项

- `BytesExtra` 仅在群消息中携带发送者信息，私聊消息通过 `IsSender` 判断
- 同一昵称可能对应多个 wxid，所有匹配的 wxid 都会被追踪
- `MSG0.db` 为近期消息，如需历史消息需遍历 `Multi/MSG*.db`
- 系统消息（Type=10000）通常无发送者，不计入统计

## 输出格式

```
=== 追踪成员：三叶草 ===
匹配联系人: 3 个
  wxid_pr7g6zk2fmvm22 | 三叶草 | （无备注）
  wxid_eh3bqdf46zzj22 | 三叶草 | 潘苗苗

所在群聊: 2 个
  群聊(49487213350@chatroom): 293条
  同袍一圈 交流群(45622088590@chatroom): 4条

总发言数: 297
时间跨度: 2026-03-04 ~ 2026-04-10
最活跃日: 2026-04-09 (91条)

已导出:
  output/trace_三叶草.csv
  output/trace_三叶草.txt
  output/trace_三叶草_stats.txt
```
