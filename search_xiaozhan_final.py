# -*- coding: utf-8 -*-
import sqlite3, os, sys

sys.stdout.reconfigure(encoding='utf-8')

base = r'output/decrypted_db'
micro_db = os.path.join(base, 'MicroMsg.db')

if not os.path.exists(micro_db):
    print(f'Database not found: {micro_db}')
    sys.exit(1)

conn = sqlite3.connect(micro_db)
cur = conn.cursor()

keyword = '肖战表情包'

print(f'=== 搜索群聊：{keyword} ===\n')

cur.execute('''
    SELECT UserName, NickName, Remark
    FROM Contact
    WHERE (NickName LIKE ? OR Remark LIKE ?)
    AND UserName LIKE "%@chatroom"
''', (f'%{keyword}%', f'%{keyword}%'))

groups = cur.fetchall()

if groups:
    print(f'找到 {len(groups)} 个群聊：\n')
    for group_id, nickname, remark in groups:
        print(f'群ID: {group_id}')
        print(f'群名: {nickname}')
        if remark:
            print(f'备注: {remark}')
        cur.execute('SELECT UserNameList FROM ChatRoom WHERE ChatRoomName = ?', (group_id,))
        row = cur.fetchone()
        if row and row[0]:
            members = row[0].split('^G')
            print(f'成员数: {len(members)}')
        print('-' * 60)
else:
    print(f'未找到名为 "{keyword}" 的群聊\n')
    print('尝试模糊搜索...\n')
    for part in ['肖战', '表情包']:
        cur.execute('''
            SELECT UserName, NickName
            FROM Contact
       WHERE NickName LIKE ?
            AND UserName LIKE "%@chatroom"
            LIMIT 5
        ''', (f'%{part}%',))
        results = cur.fetchall()
        if results:
         print(f'包含 "{part}" 的群聊：')
         for gid, gname in results:
             print(f'  - {gname} ({gid})')
            print()

conn.close()
