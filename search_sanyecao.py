# -*- coding: utf-8 -*-
"""
搜索"三叶草"的最新消息记录
重点关注源码压缩包和歌词下载需求
"""
import sqlite3
import os
import json
from datetime import datetime
import struct

# 数据库路径
MICROMSG_DB = 'output/decrypted_db/MicroMsg.db'
MSG_DB_DIR = 'output/decrypted_db/Multi/'

def find_sanyecao_users():
    """查找所有"三叶草"用户"""
    conn = sqlite3.connect(MICROMSG_DB)
    cur = conn.cursor()

    # 查找昵称或备注包含"三叶草"的用户
    cur.execute("""
        SELECT UserName, NickName, Remark, Alias
        FROM Contact
        WHERE NickName LIKE '%三叶草%' OR Remark LIKE '%三叶草%'
    """)
    users = cur.fetchall()
    conn.close()

    print(f"找到 {len(users)} 个'三叶草'用户:")
    for user in users:
        print(f"  wxid: {user[0]}")
        print(f"  昵称: {user[1]}")
        print(f"  备注: {user[2]}")
        print(f"  微信号: {user[3]}")
        print()

    return [u[0] for u in users]

def parse_bytes_extra(bytes_data):
    """解析BytesExtra字段获取群聊发送者wxid"""
    if not bytes_data:
        return None

    try:
        # BytesExtra是protobuf格式，简单解析
        # 通常发送者wxid在特定位置
        data_str = bytes_data.decode('utf-8', errors='ignore')

        # 查找wxid模式
        import re
        wxid_pattern = r'wxid_[a-z0-9]+'
        matches = re.findall(wxid_pattern, data_str)
        if matches:
            return matches[0]
    except:
        pass

    return None

def search_messages_in_db(db_path, target_wxids):
    """在指定MSG数据库中搜索目标用户的消息"""
    if not os.path.exists(db_path):
        return []

    messages = []

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # 方法1: 直接查找StrTalker为目标wxid的消息（私聊）
        for wxid in target_wxids:
            try:
                cur.execute("""
                    SELECT CreateTime, Type, StrTalker, StrContent, BytesExtra, CompressContent
                    FROM MSG
                    WHERE StrTalker = ?
                    ORDER BY CreateTime DESC
                    LIMIT 100
                """, (wxid,))
                rows = cur.fetchall()
                for row in rows:
                    messages.append({
                        'time': row[0],
                        'type': row[1],
                        'talker': row[2],
                        'content': row[3],
                        'bytes_extra': row[4],
                        'compress_content': row[5],
                        'sender': wxid,
                        'is_group': False
                    })
            except Exception as e:
                print(f"  查询私聊消息出错: {e}")
                continue

        # 方法2: 查找群聊消息（通过BytesExtra解析发送者）
        try:
            cur.execute("""
                SELECT CreateTime, Type, StrTalker, StrContent, BytesExtra, CompressContent
                FROM MSG
                WHERE StrTalker LIKE '%@chatroom'
                ORDER BY CreateTime DESC
                LIMIT 5000
            """)
            rows = cur.fetchall()

            for row in rows:
                sender = parse_bytes_extra(row[4])
                if sender in target_wxids:
                    messages.append({
                        'time': row[0],
                        'type': row[1],
                        'talker': row[2],
                        'content': row[3],
                        'bytes_extra': row[4],
                        'compress_content': row[5],
                        'sender': sender,
                        'is_group': True
                    })
        except Exception as e:
            print(f"  查询群聊消息出错: {e}")

        conn.close()
    except Exception as e:
        print(f"  数据库连接出错: {e}")

    return messages

def analyze_message(msg):
    """分析消息内容，识别关键信息"""
    content = msg['content'] or ''
    msg_type = msg['type']

    keywords = {
        '压缩包': False,
        '源码': False,
        '歌词': False,
        '下载': False,
        'zip': False,
        'rar': False,
        '7z': False
    }

    content_lower = content.lower()
    for keyword in keywords:
        if keyword in content_lower:
            keywords[keyword] = True

    # 文件消息
    is_file = msg_type == 49 or msg_type == 6

    return keywords, is_file

def main():
    print("=" * 60)
    print("搜索'三叶草'的最新消息记录")
    print("=" * 60)
    print()

    # 1. 查找所有"三叶草"用户
    target_wxids = find_sanyecao_users()
    if not target_wxids:
        print("未找到'三叶草'用户")
        return

    # 2. 遍历所有MSG*.db文件
    msg_dbs = []
    for f in os.listdir(MSG_DB_DIR):
        if f.startswith('MSG') and f.endswith('.db') and not f.startswith('FTSMSG') and not f.startswith('MediaMSG'):
            msg_dbs.append(os.path.join(MSG_DB_DIR, f))

    msg_dbs.sort()
    print(f"找到 {len(msg_dbs)} 个MSG数据库文件:")
    for db in msg_dbs:
        print(f"  {os.path.basename(db)}")
    print()

    # 3. 搜索所有消息
    all_messages = []
    for db_path in msg_dbs:
        print(f"正在搜索 {os.path.basename(db_path)}...")
        messages = search_messages_in_db(db_path, target_wxids)
        all_messages.extend(messages)
        print(f"  找到 {len(messages)} 条消息")

    print()
    print(f"总共找到 {len(all_messages)} 条消息")
    print()

    # 4. 按时间排序
    all_messages.sort(key=lambda x: x['time'], reverse=True)

    # 5. 分析并输出
    output_file = 'output/sanyecao_messages.txt'
    important_messages = []

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("'三叶草'消息记录分析\n")
        f.write(f"搜索时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总消息数: {len(all_messages)}\n")
        f.write("=" * 60 + "\n\n")

        for i, msg in enumerate(all_messages[:200], 1):  # 只输出最近200条
            time_str = datetime.fromtimestamp(msg['time']).strftime('%Y-%m-%d %H:%M:%S')
            keywords, is_file = analyze_message(msg)

            # 判断是否重要
            is_important = (
                keywords['压缩包'] or keywords['源码'] or
                keywords['歌词'] or keywords['下载'] or
                keywords['zip'] or keywords['rar'] or keywords['7z'] or
                is_file
            )

            if is_important:
                important_messages.append(msg)

            marker = "【重要】" if is_important else ""
            group_marker = "[群聊]" if msg['is_group'] else "[私聊]"
            file_marker = "[文件]" if is_file else ""

            f.write(f"{marker}{group_marker}{file_marker} [{time_str}] 消息类型:{msg['type']}\n")
            if msg['is_group']:
                f.write(f"群ID: {msg['talker']}\n")
            f.write(f"发送者: {msg['sender']}\n")

            content = msg['content'] or ''
            if len(content) > 500:
                content = content[:500] + "...(截断)"
            f.write(f"内容: {content}\n")

            if keywords:
                matched = [k for k, v in keywords.items() if v]
                if matched:
                    f.write(f"关键词: {', '.join(matched)}\n")

            f.write("\n" + "-" * 60 + "\n\n")

    print(f"详细记录已保存到: {output_file}")
    print()

    # 6. 输出重要消息摘要
    print("=" * 60)
    print(f"重要消息摘要 (共 {len(important_messages)} 条)")
    print("=" * 60)

    for i, msg in enumerate(important_messages[:20], 1):
        time_str = datetime.fromtimestamp(msg['time']).strftime('%Y-%m-%d %H:%M:%S')
        keywords, is_file = analyze_message(msg)

        print(f"\n{i}. [{time_str}]")
        print(f"   类型: {'群聊' if msg['is_group'] else '私聊'} | 消息类型: {msg['type']}")
        if msg['is_group']:
            print(f"   群ID: {msg['talker']}")

        content = msg['content'] or ''
        # 清理特殊字符避免编码错误
        content = content.encode('gbk', errors='ignore').decode('gbk', errors='ignore')
        if len(content) > 200:
            content = content[:200] + "..."
        print(f"   内容: {content}")

        matched = [k for k, v in keywords.items() if v]
        if matched:
            print(f"   关键词: {', '.join(matched)}")

    print()
    print("=" * 60)
    print("搜索完成！")
    print("=" * 60)

if __name__ == '__main__':
    main()
