# -*- coding: utf-8 -*-
import sqlite3, json

with open('output/decrypted_db/info.json', encoding='utf-8') as f:
    my_wxid = json.load(f).get('wxid', '')

conn = sqlite3.connect('output/decrypted_db/MicroMsg.db')
cur = conn.cursor()

groups_named_wu = ['39041250276@chatroom', '45696329505@chatroom', '14046930877@chatroom', '24938988411@chatroom', '21647090223@chatroom']
lines = []
for g in groups_named_wu:
    cur.execute('SELECT UserNameList, DisplayNameList FROM ChatRoom WHERE ChatRoomName=?', (g,))
    r = cur.fetchone()
    if not r:
        continue
    ul = r[0] or ''
    dn = r[1] or ''
    members = [m for m in ul.split('^G') if m.strip()]
    dn_names = [n for n in dn.split('^G') if n.strip()]
    lines.append(f'\n群: {g}')
    lines.append(f'  群内昵称列表: {dn_names}')
    for wxid in members:
        cur.execute('SELECT NickName, Remark FROM Contact WHERE UserName=?', (wxid,))
        c = cur.fetchone()
        name = (c[1] or c[0]) if c else wxid
        lines.append(f'  {wxid} => {name}')

conn.close()

with open('output/wu_groups.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('Done: output/wu_groups.txt')
