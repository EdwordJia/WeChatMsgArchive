#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""列出所有群聊"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DECRYPTED_DB_DIR = os.path.join(BASE_DIR, 'output', 'decrypted_db')

micromsg_db = os.path.join(DECRYPTED_DB_DIR, 'MicroMsg.db')
conn = sqlite3.connect(micromsg_db)
cursor = conn.cursor()

cursor.execute("""
    SELECT strUsrName, strNickName
    FROM Session
    WHERE strUsrName LIKE '%chatroom%'
    ORDER BY strNickName
""")

results = cursor.fetchall()
conn.close()

print(f"找到 {len(results)} 个群聊:\n")

output_file = os.path.join(BASE_DIR, 'output', 'all_groups.txt')
with open(output_file, 'w', encoding='utf-8') as f:
    for usr_name, nick_name in results:
        line = f"{nick_name} | {usr_name}\n"
        f.write(line)
        print(line.strip())

print(f"\n已保存到: {output_file}")
