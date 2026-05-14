import sqlite3
import glob
from datetime import datetime

# 1. 先从Contact表找到"小瓶盖粑粑"的wxid
conn_micro = sqlite3.connect('output/decrypted_db/MicroMsg.db')
cursor_micro = conn_micro.cursor()

cursor_micro.execute('''
    SELECT UserName, NickName, Remark
    FROM Contact
    WHERE NickName LIKE '%小瓶盖%' OR Remark LIKE '%小瓶盖%'
''')
contacts = cursor_micro.fetchall()
print("=== 查找'小瓶盖粑粑'的联系人信息 ===")
for wxid, nickname, remark in contacts:
    print(f"wxid: {wxid}")
    print(f"昵称: {nickname}")
    print(f"备注: {remark}")
    print()

if not contacts:
    print("未找到'小瓶盖粑粑'相关联系人")
    conn_micro.close()
    exit()

target_wxid = contacts[0][0]
target_name = contacts[0][2] if contacts[0][2] else contacts[0][1]
print(f"目标用户: {target_name} ({target_wxid})")
print()

conn_micro.close()

# 2. 遍历所有MSG*.db文件获取聊天记录
msg_dbs = sorted(glob.glob('output/decrypted_db/Multi/MSG*.db'))
print(f"=== 找到 {len(msg_dbs)} 个消息数据库 ===")
for db in msg_dbs:
    print(f"  - {db}")
print()

all_messages = []

for db_path in msg_dbs:
    conn_msg = sqlite3.connect(db_path)
    cursor_msg = conn_msg.cursor()

    # 查询与目标用户的私聊消息（StrTalker就是对方wxid，不带@chatroom）
    cursor_msg.execute('''
        SELECT CreateTime, IsSender, Type, StrContent, CompressContent
        FROM MSG
        WHERE StrTalker = ?
        ORDER BY CreateTime DESC
        LIMIT 50
    ''', (target_wxid,))

    messages = cursor_msg.fetchall()
    all_messages.extend([(db_path, *msg) for msg in messages])
    conn_msg.close()

# 按时间倒序排序（最新的在前）
all_messages.sort(key=lambda x: x[1], reverse=True)

print(f"=== 最新 {min(30, len(all_messages))} 条聊天记录 ===\n")
for i, (db_path, create_time, is_sender, msg_type, content, compress_content) in enumerate(all_messages[:30], 1):
    dt = datetime.fromtimestamp(create_time)
    sender = "我" if is_sender == 1 else target_name

    # 解析消息内容
    message_text = ""
    if msg_type == 1:  # 文本消息
        message_text = content if content else ""
    elif msg_type == 3:
        message_text = "[图片]"
    elif msg_type == 34:
        message_text = "[语音]"
    elif msg_type == 43:
        message_text = "[视频]"
    elif msg_type == 47:
        message_text = "[表情包]"
    elif msg_type == 49:
        # 文件/链接消息
        if compress_content:
            try:
                text = compress_content.decode('utf-8', errors='ignore')
           if '<title>' in text:
                    start = text.find('<title>') + 7
                    end = text.find('</title>')
                if end > start:
                filename = text[start:end]
                        message_text = f"[文件: {filename}]"
                 else:
                message_text = "[文件/链接]"
            else:
                 message_text = "[文件/链接]"
            except:
            message_text = "[文件/链接]"
        else:
            message_text = "[文件/链接]"
    elif msg_type == 10000:
        message_text = f"[系统消息: {content}]"
    else:
        message_text = f"[类型{msg_type}消息]"

    db_name = db_path.split('\\')[-1]
    print(f"{i}. [{dt.strftime('%Y-%m-%d %H:%M:%S')}] {sender}: {message_text}")
    print(f"   (来源: {db_name})")
    print()

print(f"\n总共找到 {len(all_messages)} 条聊天记录")
