# -*- coding: utf-8 -*-
import sqlite3

conn = sqlite3.connect('output/decrypted_db/MicroMsg.db')
cur = conn.cursor()

cur.execute("SELECT ChatRoomName, SelfDisplayName FROM ChatRoom WHERE SelfDisplayName != ''")
rows = cur.fetchall()

lines = ['自己有群昵称的群:\n']
for r in rows:
    cur.execute("SELECT strNickName FROM Session WHERE strUsrName=?", (r[0],))
    s = cur.fetchone()
    lines.append(f'  {r[0]} | 群名:{s[0] if s else "无"} | 我的昵称:{r[1]}\n')

conn.close()

with open('output/self_names.txt', 'w', encoding='utf-8') as f:
    f.writelines(lines)
print('Done: output/self_names.txt')
