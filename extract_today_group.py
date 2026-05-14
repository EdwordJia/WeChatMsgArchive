import sqlite3
import json
from datetime import datetime
from collections import Counter

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
        if sub[j]==0x08 and j+1<len(sub) and sub[j+1]==0x01 and j+2<len(sub) and sub[j+2]==0x12:
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

group_id = '49734720477@chatroom'
micro_db = 'output/decrypted_db/MicroMsg.db'
msg_db = 'output/decrypted_db/Multi/MSG1.db'

with open('output/decrypted_db/info.json') as f:
    my_wxid = json.load(f).get('wxid', '')

conn_micro = sqlite3.connect(micro_db)
cur_micro = conn_micro.cursor()

cur_micro.execute('SELECT UserNameList FROM ChatRoom WHERE ChatRoomName=?', (group_id,))
row = cur_micro.fetchone()

member_map = {my_wxid: '我'}
if row and row[0]:
    for wxid in row[0].split('^G'):
        if not wxid:
          continue
        cur_micro.execute('SELECT NickName, Remark FROM Contact WHERE UserName=?', (wxid,))
        c = cur_micro.fetchone()
        member_map[wxid] = (c[1] or c[0]) if c else wxid

cur_micro.execute('SELECT NickName, Remark FROM Contact WHERE UserName=?', (group_id,))
group_info = cur_micro.fetchone()
group_name = (group_info[1] or group_info[0]) if group_info else group_id

conn_micro.close()

today_start = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

conn_msg = sqlite3.connect(msg_db)
cur_msg = conn_msg.cursor()

cur_msg.execute("""
    SELECT Type, IsSender, CreateTime, StrContent, BytesExtra, CompressContent
    FROM MSG WHERE StrTalker=? AND CreateTime >= ? ORDER BY CreateTime
""", (group_id, today_start))

messages = []
for msg_type, is_sender, ts, content, bytes_extra, compress_content in cur_msg.fetchall():
    sender_wxid = my_wxid if is_sender else (parse_bytes_extra(bytes_extra) or '')
    sender_name = member_map.get(sender_wxid, sender_wxid or '未知')
    ts_str = datetime.fromtimestamp(ts).strftime('%H:%M:%S')

    type_map = {1:'文本',3:'图片',34:'语音',43:'视频',47:'表情包',10000:'系统',49:'文件/链接'}
    type_name = type_map.get(msg_type, f'类型{msg_type}')

    if msg_type == 49:
        file_info = '[文件]'
        if compress_content:
            try:
              text_data = compress_content.decode('utf-8', errors='ignore')
              if '<title>' in text_data:
                    start = text_data.find('<title>') + 7
                    end = text_data.find('</title>')
                 if end > start:
                   file_info = f'[文件: {text_data[start:end]}]'
            except:
                pass
    text = file_info
    elif msg_type == 3:
        text = '[图片]'
    elif msg_type == 34:
        text = '[语音]'
    elif msg_type == 43:
        text = '[视频]'
    elif msg_type == 47:
        text = '[表情包]'
    elif msg_type == 10000:
        text = content or '[系统消息]'
    else:
     text = content or f'[{type_name}]'

    messages.append((ts_str, sender_name, type_name, text, msg_type))

conn_msg.close()

print('='*60)
print(f'群聊分析: {group_name}')
print('='*60)
print(f'群ID: {group_id}')
print(f'成员数: {len(member_map)}')
print(f'今天消息数: {len(messages)}')
print()

print('今天的消息记录:')
print('-'*60)
for ts, name, type_name, text, msg_type in messages:
  if msg_type in [1, 49, 10000]:
     print(f'[{ts}] {name}')
        if len(text) > 150:
            print(f'  {text[:150]}...')
        else:
            print(f'  {text}')
        print()

real_msgs = [m for m in messages if m[4] != 10000]
sender_cnt = Counter(m[1] for m in real_msgs)
type_cnt = Counter(m[2] for m in messages)

print('='*60)
print('统计信息')
print('='*60)
print('\n[发言排行]')
for name, cnt in sender_cnt.most_common():
    pct = cnt * 100 / len(real_msgs) if real_msgs else 0
    print(f'  {name}: {cnt}条 ({pct:.0f}%)')

print('\n[消息类型]')
for t, c in type_cnt.most_common():
    print(f'  {t}: {c}条')
