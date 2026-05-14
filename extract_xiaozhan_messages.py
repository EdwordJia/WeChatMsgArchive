import sqlite3
from datetime import datetime

conn = sqlite3.connect('output/decrypted_db/Multi/MSG1.db')
cur = conn.cursor()

cur.execute('''
    SELECT CreateTime, Type, StrContent
    FROM MSG
    WHERE StrTalker="44601760933@chatroom"
    ORDER BY CreateTime DESC
    LIMIT 30
''')

print("=== 肖战表情包群 最近30条消息 ===\n")
for ts, msg_type, content in cur.fetchall():
    time_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    type_map = {1:'文本',3:'图片',47:'表情包',49:'文件'}
    type_name = type_map.get(msg_type, f'类型{msg_type}')
    if msg_type == 1 and content:
    print(f'[{time_str}] {type_name}')
        print(f'  {content[:200]}')
      print()
    else:
        print(f'[{time_str}] {type_name}')

conn.close()
