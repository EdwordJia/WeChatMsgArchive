import sqlite3
import time
from datetime import datetime

# 5月9日的时间范围
start_time = int(datetime(2026, 5, 9, 0, 0, 0).timestamp())
end_time = int(datetime(2026, 5, 10, 0, 0, 0).timestamp())

print(f'搜索关键词: 图框')

# 连接MSG1.db
db_path = 'output/decrypted_db/Multi/MSG1.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 搜索包含"图框"的消息
cursor.execute('''
    SELECT CreateTime, StrTalker, StrContent, IsSender
    FROM MSG
    WHERE StrContent LIKE '%图框%' AND CreateTime >= ? AND CreateTime < ?
    ORDER BY CreateTime DESC
''', (start_time, end_time))

messages = cursor.fetchall()
print(f'\n找到 {len(messages)} 条消息')

if messages:
    for msg in messages:
        msg_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(msg[0]))
        content = msg[2]
        if isinstance(content, bytes):
            content = content.decode('utf-8', errors='ignore')
        print(f'\n时间: {msg_time}')
        print(f'群组: {msg[1]}')
        print(f'发送者: {"我" if msg[3] else "对方"}')
        print(f'内容: {content}')
else:
    print('\n未找到包含"图框"的消息')

conn.close()
