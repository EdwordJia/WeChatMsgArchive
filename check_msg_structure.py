# -*- coding: utf-8 -*-
"""
检查 MSG 表结构和数据样本
"""
import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

db_file = 'output/decrypted_db/Multi/MSG1.db'
conn = sqlite3.connect(db_file)
cur = conn.cursor()

# 查看表结构
print("MSG 表结构:")
cur.execute("PRAGMA table_info(MSG)")
columns = cur.fetchall()
for col in columns:
    print(f"  {col[1]} ({col[2]})")

print("\n" + "=" * 80)

# 查看群聊 54065935658@chatroom 最近的消息样本
print("\n群聊 54065935658@chatroom 最近的消息样本:")
cur.execute("""
    SELECT CreateTime, StrTalker, StrContent, IsSender, Type, SubType, BytesExtra
    FROM MSG
    WHERE StrTalker = '54065935658@chatroom'
    ORDER BY CreateTime DESC
    LIMIT 20
""")

from datetime import datetime
rows = cur.fetchall()
for i, row in enumerate(rows, 1):
    time_str = datetime.fromtimestamp(row[0]).strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n[{i}] {time_str}")
    print(f"  StrTalker: {row[1]}")
    print(f"  IsSender: {row[3]}")
    print(f"  Type: {row[4]}, SubType: {row[5]}")
    print(f"  StrContent: {row[2][:200] if row[2] else 'None'}")
    if row[6]:
        print(f"  BytesExtra: {row[6][:100]}")

conn.close()
