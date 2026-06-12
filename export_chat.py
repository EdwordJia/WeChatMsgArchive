import sqlite3
from datetime import datetime

group_id = '44637051187@chatroom'

msg_db = sqlite3.connect('output/decrypted_db/Multi/MSG1.db')
msg_cursor = msg_db.cursor()

msg_cursor.execute('''
    SELECT Type, IsSender, CreateTime, StrContent
    FROM MSG
    WHERE StrTalker=?
    ORDER BY CreateTime
''', (group_id,))

results = msg_cursor.fetchall()

with open('output/group_44637051187_chat.txt', 'w', encoding='utf-8') as f:
    f.write('群聊: 分销管理系统\n')
    f.write(f'群ID: {group_id}\n')
    f.write(f'消息总数: {len(results)}\n\n')

    for msg_type, is_sender, ts, content in results:
        create_time = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        sender = '我' if is_sender else '对方'
        text = content if content else '[无内容]'
        f.write(f'[{create_time}] {sender}\n{text}\n\n')

msg_db.close()
print('Done')
