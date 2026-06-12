# -*- coding: utf-8 -*-
import sqlite3

# 1. 搜索同时含"轨道"+"论文"的消息
msg_db = 'output/decrypted_db/Multi/MSG0.db'
conn = sqlite3.connect(msg_db)
cur = conn.cursor()
cur.execute("""
    SELECT StrTalker, StrContent FROM MSG
    WHERE StrContent LIKE '%轨道%' AND StrContent LIKE '%论文%'
    AND StrTalker LIKE '%chatroom%'
    LIMIT 20
""")
rows = cur.fetchall()

# 2. 查 ChatRoom RoomData 中含"轨道"的
micro_db = 'output/decrypted_db/MicroMsg.db'
conn2 = sqlite3.connect(micro_db)
cur2 = conn2.cursor()
cur2.execute("SELECT ChatRoomName, RoomData FROM ChatRoom WHERE RoomData LIKE '%轨道%'")
rooms = cur2.fetchall()

with open('output/search_result2.txt', 'w', encoding='utf-8') as f:
    f.write("=== 同时含轨道+论文的消息 ===\n")
    for r in rows:
        f.write(f"群ID: {r[0]}\n内容: {r[1][:200]}\n\n")
    f.write(f"\n=== ChatRoom RoomData含轨道 ===\n")
    for r in rooms:
        f.write(f"群ID: {r[0]}\nRoomData: {str(r[1])[:200]}\n\n")

print(f"消息结果: {len(rows)} 条, RoomData结果: {len(rooms)} 条")
conn.close()
conn2.close()
