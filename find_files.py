# -*- coding: utf-8 -*-
import sqlite3

msg_db = 'output/decrypted_db/Multi/MSG0.db'
conn = sqlite3.connect(msg_db)
cur = conn.cursor()

# 查找轨道论文群的文件类消息（Type=49 链接/文件）
group_id = None

# 先找群ID
micro_db = 'output/decrypted_db/MicroMsg.db'
conn2 = sqlite3.connect(micro_db)
cur2 = conn2.cursor()
cur2.execute("SELECT UserName FROM Contact WHERE UserName LIKE '%chatroom%' AND NickName LIKE '%轨道%'")
row = cur2.fetchone()
if row:
    group_id = row[0]
    print(f"群ID: {group_id}")
conn2.close()

# 如果没找到，从MSG里搜含"轨道"的群
if not group_id:
    cur.execute("""
        SELECT DISTINCT StrTalker FROM MSG
        WHERE StrContent LIKE '%轨道%' AND StrTalker LIKE '%chatroom%'
    """)
    rows = cur.fetchall()
    print("含轨道消息的群:")
    for r in rows:
        print(r[0])
    if rows:
        group_id = rows[0][0]

print(f"\n使用群ID: {group_id}")

# 查该群的文件消息
cur.execute("""
    SELECT Type, CreateTime, StrContent, BytesExtra
    FROM MSG WHERE StrTalker=? AND Type=49
    ORDER BY CreateTime DESC LIMIT 20
""", (group_id,))
rows = cur.fetchall()

with open('output/file_messages.txt', 'w', encoding='utf-8') as f:
    f.write(f"群ID: {group_id}\n文件消息数: {len(rows)}\n\n")
    for r in rows:
        f.write(f"时间戳: {r[1]}\n内容: {str(r[2])[:500]}\n\n")

print(f"找到 {len(rows)} 条文件消息，写入 output/file_messages.txt")
conn.close()
