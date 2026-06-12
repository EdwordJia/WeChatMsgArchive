# -*- coding: utf-8 -*-
import sqlite3

msg_db = 'output/decrypted_db/Multi/MSG0.db'
conn = sqlite3.connect(msg_db)
cur = conn.cursor()

# 搜索包含"轨道"或"论文"的消息，找到对应群ID
cur.execute("""
    SELECT StrTalker, StrContent FROM MSG
    WHERE (StrContent LIKE '%轨道%' OR StrContent LIKE '%论文%')
    AND StrTalker LIKE '%chatroom%'
    LIMIT 20
""")
rows = cur.fetchall()

with open('output/search_result.txt', 'w', encoding='utf-8') as f:
    for r in rows:
        f.write(f"群ID: {r[0]}\n内容: {r[1][:100]}\n\n")

print(f"找到 {len(rows)} 条结果")
conn.close()
