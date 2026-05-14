# -*- coding: utf-8 -*-
import sqlite3, os

base = r'output/decrypted_db'
micro_db = os.path.join(base, 'MicroMsg.db')
conn = sqlite3.connect(micro_db)
cur = conn.cursor()

keywords = ['无', '往事如风', 'henghenghaha', '嘿嘿']

lines = []
lines.append("=== 联系人搜索 ===\n")
found_wxids = {}
for kw in keywords:
    cur.execute('SELECT UserName, NickName, Remark FROM Contact WHERE NickName LIKE ? OR Remark LIKE ? LIMIT 10', (f'%{kw}%', f'%{kw}%'))
    rows = cur.fetchall()
    lines.append(f'\n关键词 [{kw}]:')
    for r in rows:
        lines.append(f'  wxid={r[0]}, 昵称={r[1]}, 备注={r[2]}')
        found_wxids[r[0]] = r[1] or r[2]

lines.append("\n\n=== 查找包含这些成员的群聊 ===")
cur.execute('SELECT ChatRoomName, UserNameList FROM ChatRoom')
rooms = cur.fetchall()

target_wxids = list(found_wxids.keys())
lines.append(f"目标wxid列表: {target_wxids}")

for room_name, user_list in rooms:
    if not user_list:
        continue
    members = user_list.split('^G')
    matched = [w for w in target_wxids if w in members]
    if len(matched) >= 2:
        lines.append(f'\n群ID: {room_name}')
        lines.append(f'匹配成员: {[found_wxids[w] for w in matched]}')
        lines.append(f'总成员数: {len(members)}')

conn.close()

with open('output/find_group_result.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print("Done, written to output/find_group_result.txt")
