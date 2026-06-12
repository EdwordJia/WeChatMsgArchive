import sqlite3, json, sys
from datetime import datetime, timedelta
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')

users = ['三叶草', '编程仝芷硕', 'Estelle', '烨林', '沐光', '密码机']

micro_db = 'output/decrypted_db/MicroMsg.db'
conn_micro = sqlite3.connect(micro_db)
cur_micro = conn_micro.cursor()

now = datetime.now()
thirty_min_ago = now - timedelta(minutes=30)
timestamp_30min = int(thirty_min_ago.timestamp())

print(f'当前时间: {now.strftime("%Y-%m-%d %H:%M:%S")}')
print(f'30分钟前: {thirty_min_ago.strftime("%Y-%m-%d %H:%M:%S")}\n')

# 搜索所有用户
all_target_wxids = {}
for keyword in users:
    cur_micro.execute(
        'SELECT UserName, NickName, Remark FROM Contact WHERE NickName LIKE ? OR Remark LIKE ?',
        (f'%{keyword}%', f'%{keyword}%')
    )
    targets = cur_micro.fetchall()
    if targets:
        wxids = [t[0] for t in targets]
        all_target_wxids[keyword] = wxids
        print(f'✓ {keyword}: {len(targets)}个匹配')
    else:
        print(f'✗ {keyword}: 未找到')

# 查找所有用户所在群聊
all_groups = {}
all_wxid_to_user = {}
for keyword, wxids in all_target_wxids.items():
    for wxid in wxids:
        all_wxid_to_user[wxid] = keyword
        cur_micro.execute('SELECT ChatRoomName FROM ChatRoom WHERE UserNameList LIKE ?', (f'%{wxid}%',))
        for (room_id,) in cur_micro.fetchall():
            if room_id not in all_groups:
                cur_micro.execute('SELECT strNickName FROM Session WHERE strUsrName=?', (room_id,))
                row = cur_micro.fetchone()
                all_groups[room_id] = row[0] if row else room_id

conn_micro.close()
print(f'\n涉及群聊: {len(all_groups)} 个')


def parse_bytes_extra(data):
    if not data:
        return None
    try:
        i = 0
        while i < len(data):
            if data[i] == 0x1a:
                i += 1
                if i >= len(data):
                    break
                length = data[i]
                i += 1
                sub = data[i:i+length]
                j = 0
                while j < len(sub):
                    if sub[j] == 0x08 and j+1 < len(sub) and sub[j+1] == 0x01 and j+2 < len(sub) and sub[j+2] == 0x12:
                        j += 3
                        wxid_len = sub[j]
                        j += 1
                        return sub[j:j+wxid_len].decode('utf-8', errors='ignore')
                    j += 1
                i += length
            else:
                i += 1
    except:
        pass
    return None


msg_db = 'output/decrypted_db/Multi/MSG0.db'
conn_msg = sqlite3.connect(msg_db)
cur_msg = conn_msg.cursor()

type_map = {1: '文本', 3: '图片', 34: '语音', 43: '视频', 47: '表情包', 10000: '系统消息', 49: '链接/文件'}
recent_by_user = {}

cur_msg.execute(
    'SELECT Type, IsSender, CreateTime, StrContent, BytesExtra, StrTalker FROM MSG WHERE CreateTime > ? ORDER BY CreateTime DESC',
    (timestamp_30min,)
)

for msg_type, is_sender, ts, content, bytes_extra, talker in cur_msg.fetchall():
    sender_wxid = parse_bytes_extra(bytes_extra) if not is_sender else ''
    if sender_wxid not in all_wxid_to_user:
        continue

    user = all_wxid_to_user[sender_wxid]
    ts_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    type_name = type_map.get(msg_type, f'类型{msg_type}')
    text = content if msg_type == 1 else f'[{type_name}]'
    group_name = all_groups.get(talker, talker)

    if user not in recent_by_user:
        recent_by_user[user] = []
    recent_by_user[user].append({'time': ts_str, 'type': type_name, 'content': text, 'group': group_name})

conn_msg.close()

print(f'\n{"="*50}')
print(f'最近30分钟消息统计')
print(f'{"="*50}\n')

total = 0
for user in users:
    count = len(recent_by_user.get(user, []))
    total += count
    print(f'{user}: {count} 条')

if total > 0:
    print(f'\n{"="*50}')
    print(f'详细消息')
    print(f'{"="*50}')
    for user, msgs in recent_by_user.items():
        print(f'\n--- {user} ({len(msgs)}条) ---')
        for msg in msgs:
            print(f'[{msg["time"]}] {msg["group"]}')
            print(f'  {msg["type"]}: {msg["content"][:200]}')
            print()
else:
    print(f'\n总计: 0 条，无新增消息')

# 保存结果
with open('temp_cron_result.json', 'w', encoding='utf-8') as f:
    json.dump({'total': total, 'by_user': recent_by_user, 'time': now.strftime('%Y-%m-%d %H:%M:%S')}, f, ensure_ascii=False)
