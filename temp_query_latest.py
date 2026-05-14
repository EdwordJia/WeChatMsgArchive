import sqlite3
from datetime import datetime
import sys
import re
sys.stdout.reconfigure(encoding='utf-8')

db_path = 'output/decrypted_db/MSG0.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

start_time = int(datetime(2026, 5, 8, 0, 0, 0).timestamp())
end_time = int(datetime.now().timestamp())

print(f'查询时间范围: {datetime.fromtimestamp(start_time)} 到 {datetime.fromtimestamp(end_time)}')
print(f'时间戳范围: {start_time} 到 {end_time}\n')

cursor.execute('''
    SELECT CreateTime, IsSender, Type, StrContent
    FROM MSG
    WHERE StrTalker = 'wxid_tm60ob3bb94x22'
    AND CreateTime >= ? AND CreateTime <= ?
    ORDER BY CreateTime DESC
    LIMIT 30
''', (start_time, end_time))

results = cursor.fetchall()
print(f'找到 {len(results)} 条消息\n')
print('='*80)

for row in results:
    create_time, is_sender, msg_type, content = row
    dt = datetime.fromtimestamp(create_time)
    sender = '我' if is_sender == 1 else '对方'
    if msg_type == 1:
        print(f'[{dt.strftime("%Y-%m-%d %H:%M:%S")}] {sender}: {content}')
    elif msg_type == 3:
        print(f'[{dt.strftime("%Y-%m-%d %H:%M:%S")}] {sender}: [图片]')
  elif msg_type == 49:
        print(f'[{dt.strftime("%Y-%m-%d %H:%M:%S")}] {sender}: [转发/链接]')
        if content and '<title>' in content:
        title_match = re.search(r'<title>(.*?)</title>', content)
          if title_match:
             print(f'    标题: {title_match.group(1)}')
    elif msg_type == 34:
        print(f'[{dt.strftime("%Y-%m-%d %H:%M:%S")}] {sender}: [语音]')
    else:
        print(f'[{dt.strftime("%Y-%m-%d %H:%M:%S")}] {sender}: [类型{msg_type}]')

conn.close()
print('='*80)
