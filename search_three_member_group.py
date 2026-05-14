#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜索包含烨林、风临野和自己的群聊，并提取最新聊天信息
"""

import sqlite3
from datetime import datetime
import os

# 数据库路径
MICROMSG_DB = "output/decrypted_db/MicroMsg.db"
MSG1_DB = "output/decrypted_db/Multi/MSG1.db"
MSG0_DB = "output/decrypted_db/Multi/MSG0.db"

# 已知的wxid（从记忆中获取）
TARGET_WXIDS = {
    'wxid_70920730612': '烨林',
    'wxid_5pppo6f5tpgz22': '风临野',
    'wxid_ucag2pjrmhm822': '我'
}

def find_common_groups():
    """查找包含三个目标成员的群聊"""
    print("=" * 80)
    print("步骤1: 查找包含三个目标成员的群聊")
    print("=" * 80)

    conn = sqlite3.connect(MSG1_DB)
    cursor = conn.cursor()

    # 从ChatRoom表查找包含所有三个wxid的群
    query = """
    SELECT ChatRoomName, UserNameList, DisplayName, Reserved1
    FROM ChatRoom
    WHERE 1=1
    """

    # 添加每个wxid的筛选条件
    for wxid in TARGET_WXIDS.keys():
     query += f" AND UserNameList LIKE '%{wxid}%'"

    query += " ORDER BY Reserved1 DESC"  # 按最后活跃时间倒序

    cursor.execute(query)
    groups = cursor.fetchall()

    conn.close()

    if not groups:
      print("❌ 未找到包含这三个成员的群聊")
     return []

    print(f"✅ 找到 {len(groups)} 个群聊:\n")

    group_info = []
    for idx, (chatroom_name, member_list, display_name, last_active) in enumerate(groups, 1):
        members = member_list.split('^G') if member_list else []
        member_count = len(members)

        # 转换时间戳
        if last_active:
            last_time = datetime.fromtimestamp(last_active).strftime('%Y-%m-%d %H:%M:%S')
        else:
            last_time = "未知"

      print(f"{idx}. 群ID: {chatroom_name}")
        print(f"   群名: {display_name or '(未命名)'}")
        print(f"   成员数: {member_count}")
        print(f"   最后活跃: {last_time}")
        print()

        group_info.append({
            'chatroom_name': chatroom_name,
            'display_name': display_name,
            'member_count': member_count,
            'last_active': last_active
        })

    return group_info

def get_group_latest_messages(chatroom_name, limit=50):
    """获取群聊的最新消息"""
    print("=" * 80)
    print(f"步骤2: 提取群聊最新消息 (最近{limit}条)")
    print("=" * 80)

    # 先尝试MSG1.db（最新消息）
    messages = []
    for db_path, db_name in [(MSG1_DB, "MSG1.db"), (MSG0_DB, "MSG0.db")]:
        if not os.path.exists(db_path):
            continue

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        query = """
        SELECT CreateTime, Message, StrTalker, Type, SubType
        FROM MSG
        WHERE StrTalker = ?
        ORDER BY CreateTime DESC
     LIMIT ?
        """

        cursor.execute(query, (chatroom_name, limit))
        rows = cursor.fetchall()

      if rows:
            print(f"✅ 从 {db_name} 找到 {len(rows)} 条消息")
            messages.extend(rows)

        conn.close()

        if messages:
            break  # 如果MSG1有消息就不查MSG0了

    if not messages:
        print("❌ 未找到消息")
        return

    # 获取发送者昵称映射
    sender_names = get_sender_names(chatroom_name)

    # 按时间正序排列（最早的在前）
    messages.sort(key=lambda x: x[0])

    print("\n" + "=" * 80)
    print("最新聊天记录:")
    print("=" * 80 + "\n")

    for create_time, message, str_talker, msg_type, sub_type in messages:
        # 转换时间戳
        time_str = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')

        # 获取发送者昵称
        sender = sender_names.get(str_talker, str_talker)

        # 标记目标成员
        if str_talker in TARGET_WXIDS:
       sender = f"【{TARGET_WXIDS[str_talker]}】{sender}"

        # 消息类型
        type_desc = get_message_type_desc(msg_type)

        # 打印消息
        if msg_type == 1:  # 文本消息
            print(f"[{time_str}] {sender}:")
            print(f"  {message}")
        else:
       print(f"[{time_str}] {sender}: [{type_desc}]")

        print()

def get_sender_names(chatroom_name):
    """获取群成员的昵称映射"""
    conn = sqlite3.connect(MICROMSG_DB)
    cursor = conn.cursor()

    # 从Contact表获取昵称
    query = """
    SELECT UserName, NickName, Remark
    FROM Contact
    WHERE UserName IN (
        SELECT DISTINCT StrTalker FROM (
            SELECT StrTalker FROM MSG WHERE StrTalker = ?
          UNION
            SELECT StrTalker FROM MSG WHERE StrTalker LIKE ?
        )
    )
    """

    cursor.execute(query, (chatroom_name, f"%@chatroom%"))

    # 同时查询群成员
    msg1_conn = sqlite3.connect(MSG1_DB)
    msg1_cursor = msg1_conn.cursor()

    msg1_cursor.execute("""
        SELECT UserNameList FROM ChatRoom WHERE ChatRoomName = ?
    "", (chatroom_name,))

    result = msg1_cursor.fetchone()
    member_wxids = []
    if result and result[0]:
      member_wxids = result[0].split('^G')

    msg1_conn.close()

    # 查询所有成员的昵称
    if member_wxids:
        placeholders = ','.join('?' * len(member_wxids))
     cursor.execute(f"""
         SELECT UserName, NickName, Remark
       FROM Contact
            WHERE UserName IN ({placeholders})
        """, member_wxids)

    sender_names = {}
    for username, nickname, remark in cursor.fetchall():
        # 优先使用备注名，其次昵称
        display_name = remark if remark else nickname
        sender_names[username] = display_name or username

    conn.close()

    return sender_names

def get_message_type_desc(msg_type):
    """获取消息类型描述""
    type_map = {
      1: "文本",
    3: "图片",
        34: "语音",
        43: "视频",
     47: "表情",
        49: "链接/文件",
        10000: "系统消息",
        10002: "撤回消息"
    }
    return type_map.get(msg_type, f"未知类型({msg_type})")

def main():
    print("\n🔍 搜索包含烨林、风临野和我的群聊\n")

    # 查找群聊
    groups = find_common_groups()

    if not groups:
        return

    # 提取第一个群的最新消息（最活跃的群）
    target_group = groups[0]
    print(f"\n📱 正在提取群聊: {target_group['display_name'] or '(未命名)'}")
    print(f"   群ID: {target_group['chatroom_name']}\n")

    get_group_latest_messages(target_group['chatroom_name'], limit=100)

    print("\n" + "=" * 80)
    print("✅ 搜索完成")
    print("=" * 80)

if __name__ == "__main__":
  main()
