#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
提取"数据分析派单1️⃣1️⃣"群的所有消息记录并分析需求
"""

import os
import sys
import sqlite3
import json
from datetime import datetime
from wxManager.parser.util.protocbuf.msg_pb2 import MessageBytesExtra

# 配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DECRYPTED_DB_DIR = os.path.join(BASE_DIR, 'output', 'decrypted_db')
TARGET_GROUP_ID = '50203296293@chatroom'
TARGET_GROUP_NAME = '数据分析派单群'
MY_WXID = 'wxid_ucag2pjrmhm822'
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')


def get_contact_info(micromsg_db_path):
    """从 MicroMsg.db 获取所有联系人信息"""
    print("正在加载联系人信息...")

    conn = sqlite3.connect(micromsg_db_path)
    cursor = conn.cursor()

    # 查询 Contact 表
    cursor.execute("""
        SELECT UserName, Remark, NickName
        FROM Contact
    """)

    contacts = {}
    for username, remark, nickname in cursor.fetchall():
        display_name = remark if remark else nickname
        contacts[username] = display_name if display_name else username

    conn.close()
    print(f"已加载 {len(contacts)} 个联系人")
    return contacts


def parse_sender_from_bytesextra(bytes_extra):
    """从 BytesExtra 解析发送者 wxid"""
    if not bytes_extra:
        return None

    try:
        msgbytes = MessageBytesExtra()
        msgbytes.ParseFromString(bytes_extra)

        for tmp in msgbytes.message2:
            if tmp.field1 == 1:
                wxid = tmp.field2
                # 处理带冒号的情况
                if ':' in wxid:
                    wxid = wxid.split(':')[0]
                return wxid
    except Exception as e:
        pass

    return None


def extract_messages_from_db(db_path, group_id, contacts):
    """从单个 MSG*.db 文件提取消息"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 查询该群的所有消息
    cursor.execute("""
        SELECT localId, TalkerId, Type, SubType, IsSender, CreateTime,
               Status, StrContent, MsgSvrID, BytesExtra, CompressContent
        FROM MSG
        WHERE StrTalker = ?
        ORDER BY CreateTime
    """, (group_id,))

    messages = []
    for row in cursor.fetchall():
        local_id, talker_id, msg_type, sub_type, is_sender, create_time, \
            status, str_content, msg_svr_id, bytes_extra, compress_content = row

        # 确定发送者
        if is_sender:
            sender_wxid = MY_WXID
        else:
            sender_wxid = parse_sender_from_bytesextra(bytes_extra)
            if not sender_wxid:
                sender_wxid = group_id

        # 获取发送者昵称
        sender_name = contacts.get(sender_wxid, sender_wxid)

        # 格式化时间
        if create_time and create_time > 0:
            time_str = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')
        else:
            time_str = 'unknown'

        messages.append({
            'time': create_time,
            'time_str': time_str,
            'sender_wxid': sender_wxid,
            'sender_name': sender_name,
            'is_sender': is_sender,
            'type': msg_type,
            'subtype': sub_type,
            'content': str_content if str_content else '',
            'msg_svr_id': msg_svr_id
        })

    conn.close()
    return messages


def extract_all_messages(group_id, contacts):
    """遍历所有 MSG*.db 文件提取消息"""
    print(f"\n正在遍历所有 MSG*.db 文件...")

    multi_dir = os.path.join(DECRYPTED_DB_DIR, 'Multi')
    if not os.path.exists(multi_dir):
        print(f"错误: 找不到目录 {multi_dir}")
        return []

    all_messages = []
    msg_files = []

    # 查找所有 MSG*.db 文件
    for filename in os.listdir(multi_dir):
        if filename.startswith('MSG') and filename.endswith('.db') and not filename.startswith('FTSMSG') and not filename.startswith('MediaMSG'):
            msg_files.append(filename)

    msg_files.sort()
    print(f"找到 {len(msg_files)} 个消息数据库文件: {', '.join(msg_files)}")

    for filename in msg_files:
        db_path = os.path.join(multi_dir, filename)
        print(f"  正在处理 {filename}...")

        try:
            messages = extract_messages_from_db(db_path, group_id, contacts)
            all_messages.extend(messages)
            print(f"    提取到 {len(messages)} 条消息")
        except Exception as e:
            print(f"    错误: {e}")

    # 按时间排序
    all_messages.sort(key=lambda x: x['time'])

    print(f"\n总共提取到 {len(all_messages)} 条消息")
    return all_messages


def export_messages(messages, group_name):
    """导出消息到文件"""
    print(f"\n正在导出消息...")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 导出为 JSON
    json_path = os.path.join(OUTPUT_DIR, f'group_{group_name}_messages.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
    print(f"JSON 已导出: {json_path}")

    # 导出为 TXT（可读格式）
    txt_path = os.path.join(OUTPUT_DIR, f'group_{group_name}_messages.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(f"群名: {group_name}\n")
        f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"消息总数: {len(messages)}\n")
        f.write("=" * 80 + "\n\n")

        for msg in messages:
            f.write(f"[{msg['time_str']}] {msg['sender_name']}\n")
            if msg['content']:
                f.write(f"{msg['content']}\n")
            f.write("-" * 80 + "\n\n")

    print(f"TXT 已导出: {txt_path}")

    return txt_path, json_path


def analyze_requirements(messages):
    """分析需求信息"""
    print(f"\n正在分析需求信息...")

    # 筛选包含关键词的消息
    keywords = ['700', '3天', 'flutter', '需求', '功能', '开发', '项目', '做', '实现', '要', '帮', '价格', '报价', '多少钱']
    relevant_messages = []

    for msg in messages:
        content = msg['content'].lower()
        if any(keyword in content for keyword in keywords):
            relevant_messages.append(msg)

    # 导出需求分析
    analysis_path = os.path.join(OUTPUT_DIR, f'group_{TARGET_GROUP_NAME}_requirements.txt')
    with open(analysis_path, 'w', encoding='utf-8') as f:
        f.write(f"=== 需求分析 ===\n\n")
        f.write(f"总消息数: {len(messages)}\n")
        f.write(f"相关消息数: {len(relevant_messages)}\n\n")

        f.write("=" * 80 + "\n")
        f.write("包含关键词的消息:\n")
        f.write("=" * 80 + "\n\n")

        for msg in relevant_messages:
            f.write(f"[{msg['time_str']}] {msg['sender_name']}\n")
            f.write(f"{msg['content']}\n")
            f.write("-" * 80 + "\n\n")

    print(f"需求分析已导出: {analysis_path}")
    return analysis_path


def main():
    print("=" * 80)
    print(f"提取群 [{TARGET_GROUP_NAME}] 的所有消息记录")
    print(f"群ID: {TARGET_GROUP_ID}")
    print("=" * 80)

    # 1. 加载联系人信息
    micromsg_db = os.path.join(DECRYPTED_DB_DIR, 'MicroMsg.db')
    contacts = get_contact_info(micromsg_db)

    # 2. 提取所有消息
    messages = extract_all_messages(TARGET_GROUP_ID, contacts)

    if not messages:
        print("\n未找到任何消息")
        return

    # 3. 导出消息
    txt_path, json_path = export_messages(messages, TARGET_GROUP_NAME)

    # 4. 分析需求
    analysis_path = analyze_requirements(messages)

    print("\n" + "=" * 80)
    print("完成！")
    print(f"消息记录: {txt_path}")
    print(f"JSON数据: {json_path}")
    print(f"需求分析: {analysis_path}")
    print("=" * 80)


if __name__ == '__main__':
    main()
