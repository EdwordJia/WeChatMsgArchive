#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
from datetime import datetime
import os

CHATROOM = '54026338684@chatroom'
MSG_DBS = ['output/decrypted_db/Multi/MSG1.db', 'output/decrypted_db/Multi/MSG0.db']
MICROMSG_DB = 'output/decrypted_db/MicroMsg.db'

# Get nicknames
conn = sqlite3.connect(MICROMSG_DB)
cursor = conn.cursor()
cursor.execute('SELECT UserNameList FROM ChatRoom WHERE ChatRoomName = ?', (CHATROOM,))
row = cursor.fetchone()
members = row[0].split('^G') if row else []

nicknames = {}
for m in members:
    cursor.execute('SELECT NickName, Remark FROM Contact WHERE UserName = ?', (m,))
    r = cursor.fetchone()
    if r:
        nicknames[m] = r[1] if r[1] else r[0]
conn.close()

# Extract messages
all_messages = []
for db_path in MSG_DBS:
    if not os.path.exists(db_path):
        continue
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
      'SELECT CreateTime, StrContent, Type, IsSender, BytesExtra FROM MSG WHERE StrTalker = ? ORDER BY CreateTime DESC LIMIT 100',
        (CHATROOM,)
    )
    rows = cursor.fetchall()
    all_messages.extend(rows)
    conn.close()
    if rows:
        print("Found %d messages in %s" % (len(rows), os.path.basename(db_path)))

all_messages.sort(key=lambda x: x[0])

print("\n=== Latest messages (you, 烨林, 风临野) ===\n")

for create_time, content, msg_type, is_sender, bytes_extra in all_messages:
    time_str = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')

    # Determine sender
    if is_sender == 1:
        sender = '我'
    else:
        # Try to extract sender wxid from BytesExtra
    sender_wxid = None
        if bytes_extra:
            try:
          data = bytes(bytes_extra)
                idx = data.find(b'wxid_')
           if idx >= 0:
             end = idx
                    while end < len(data) and (data[end:end+1].isalnum() or data[end] == ord('_')):
                        end += 1
          sender_wxid = data[idx:end].decode('utf-8', errors='ignore')
            except:
                pass
        sender = nicknames.get(sender_wxid, sender_wxid or 'unknown')

    # Print message
    if msg_type == 1:
        print("[%s] %s:" % (time_str, sender))
        print("  %s" % content)
    elif msg_type == 3:
        print("[%s] %s: [Image]" % (time_str, sender))
    elif msg_type == 34:
        print("[%s] %s: [Voice]" % (time_str, sender))
    elif msg_type == 43:
     print("[%s] %s: [Video]" % (time_str, sender))
    elif msg_type == 47:
     print("[%s] %s: [Emoji]" % (time_str, sender))
    elif msg_type == 49:
        print("[%s] %s: [Link/File]" % (time_str, sender))
    elif msg_type == 10000:
        print("[%s] [System: %s]" % (time_str, content))
    else:
        print("[%s] %s: [Type %d]" % (time_str, sender, msg_type))
    print()
