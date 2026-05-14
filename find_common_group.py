#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查找包含烨林、风临野和我共同所在的群聊"""

import sqlite3
from datetime import datetime

MICROMSG_DB = "output/decrypted_db/MicroMsg.db"

TARGET_WXIDS = {
    'wxid_70920730612': '烨林',
    'wxid_5pppo6f5tpgz22': '风临野',
    'wxid_ucag2pjrmhm822': '我'
}

def find_common_groups():
    conn = sqlite3.connect(MICROMSG_DB)
    cursor = conn.cursor()

    query = "SELECT ChatRoomName, UserNameList, Reserved1 FROM ChatRoom WHERE 1=1"
    for wxid in TARGET_WXIDS.keys():
        query += f" AND UserNameList LIKE '%{wxid}%'"
    query += " ORDER BY Reserved1 DESC"

    cursor.execute(query)
    groups = cursor.fetchall()
    conn.close()

    print("找到 %d 个共同群聊:\n" % len(groups))
    for idx, row in enumerate(groups, 1):
        chatroom_name, member_list, last_active = row
        members = member_list.split('^G') if member_list else []
        if last_active:
            last_time = datetime.fromtimestamp(last_active).strftime('%Y-%m-%d %H:%M:%S')
        else:
            last_time = "unknown"
        print("%d. ChatRoom: %s" % (idx, chatroom_name))
        print("   Members: %d" % len(members))
        print("   LastActive: %s" % last_time)
        print()

    return groups

if __name__ == "__main__":
    find_common_groups()
