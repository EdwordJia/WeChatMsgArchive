# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime

msg_db = 'output/decrypted_db/Multi/MSG0.db'
conn = sqlite3.connect(msg_db)
cur = conn.cursor()

# 查表结构
cur.execute('PRAGMA table_info(MSG)')
cols = [r[1] for r in cur.fetchall()]

group_id = '44341649440@chatroom'

# 取所有字段
cur.execute(f"SELECT * FROM MSG WHERE StrTalker=? AND Type=49 ORDER BY CreateTime DESC", (group_id,))
files = cur.fetchall()

with open('output/group_files.txt', 'w', encoding='utf-8') as f:
    f.write(f"列名: {cols}\n\n")
    for i, row in enumerate(files):
        ts = row[cols.index('CreateTime')] if 'CreateTime' in cols else 0
        ts_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else str(ts)
        f.write(f"=== 第{i+1}条 {ts_str} ===\n")
        for col, val in zip(cols, row):
            if val and col not in ('BytesExtra', 'Reserved'):
                f.write(f"  {col}: {str(val)[:300]}\n")
        # BytesExtra 尝试解码
        if 'BytesExtra' in cols:
            be = row[cols.index('BytesExtra')]
            if be:
                try:
                    f.write(f"  BytesExtra(text): {be.decode('utf-8', errors='replace')[:300]}\n")
                except:
                    f.write(f"  BytesExtra(hex): {be.hex()[:200]}\n")
        f.write("\n")

print(f"列名: {cols}")
print(f"找到 {len(files)} 条，写入 output/group_files.txt")
conn.close()
