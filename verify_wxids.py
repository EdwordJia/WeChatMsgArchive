#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3

MICROMSG_DB = "output/decrypted_db/MicroMsg.db"

conn = sqlite3.connect(MICROMSG_DB)
cursor = conn.cursor()

# Step 1: Verify wxids by name
for name in ['烨林', '风临野']:
    cursor.execute(
     "SELECT UserName, NickName, Remark FROM Contact WHERE NickName LIKE ? OR Remark LIKE ?",
        ('%' + name + '%', '%' + name + '%')
    )
    rows = cursor.fetchall()
    print("=== Search: " + name + " ===")
    print("Found %d matches" % len(rows))
    for row in rows:
        print("  wxid=%s | nick=%s | remark=%s" % (row[0], row[1] or '', row[2] or ''))
    print()

# Step 2: For each known wxid, count groups
print("=== Group membership ===")
for wxid in ['wxid_70920730612', 'wxid_5pppo6f5tpgz22', 'wxid_ucag2pjrmhm822']:
    cursor.execute("SELECT COUNT(*) FROM ChatRoom WHERE UserNameList LIKE ?", ('%' + wxid + '%',))
    count = cursor.fetchone()[0]
    print("%s: %d groups" % (wxid, count))

conn.close()
