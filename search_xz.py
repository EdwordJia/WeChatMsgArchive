import sqlite3

db_path = r"output/decrypted_db/MicroMsg.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== 精确搜索：肖战表情包 ===")
cursor.execute(""
SELECT UserName, NickName, Remark
FROM Contact
WHERE (NickName LIKE "%肖战表情包%" OR Remark LIKE "%肖战表情包%")
AND UserName LIKE "%@chatroom"
""")

exact_results = cursor.fetchall()

if exact_results:
    for row in exact_results:
        chatroom_id = row[0]
        nickname = row[1] or ""
        remark = row[2] or ""
        cursor.execute("SELECT UserNameList FROM ChatRoom WHERE ChatRoomName = ?", (chatroom_id,))
        chatroom_row = cursor.fetchone()
        member_count = 0
        if chatroom_row and chatroom_row[0]:
            members = chatroom_row[0].split("^G")
            member_count = len(members)
        print(f"
群ID: {chatroom_id}")
        print(f"群名: {nickname}")
        print(f"备注: {remark}")
        print(f"成员数: {member_count}")
else:
    print("未找到精确匹配的群聊")
    print("=== 模糊搜索：包含'肖战'或'表情包' ===")
    cursor.execute("""
    SELECT UserName, NickName, Remark
    FROM Contact
    WHERE (NickName LIKE "%肖战%" OR NickName LIKE "%表情包%"
           OR Remark LIKE "%肖战%" OR Remark LIKE "%表情包%")
    AND UserName LIKE "%@chatroom"
    """)
    fuzzy_results = cursor.fetchall()
    if fuzzy_results:
        for row in fuzzy_results:
            chatroom_id = row[0]
       nickname = row[1] or ""
            remark = row[2] or ""
            cursor.execute("SELECT UserNameList FROM ChatRoom WHERE ChatRoomName = ?", (chatroom_id,))
            chatroom_row = cursor.fetchone()
            member_count = 0
            if chatroom_row and chatroom_row[0]:
              members = chatroom_row[0].split("^G")
                member_count = len(members)
            print(f"
群ID: {chatroom_id}")
            print(f"群名: {nickname}")
          print(f"备注: {remark}")
            print(f"成员数: {member_count}")
    else:
        print("未找到包含'肖战'或'表情包'的群聊")

conn.close()
