# -*- coding: utf-8 -*-
"""
搜索"是我宗朕啊"（wxid: wxid_ny8553dmpiws22）最近两天（4月22-24日）的所有消息
通过解析 BytesExtra 字段识别发送者
"""
import sqlite3
from datetime import datetime
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 目标用户信息
target_wxid = 'wxid_ny8553dmpiws22'
target_name = '是我宗朕啊'

# 时间范围：2026-04-22 00:00:00 到 2026-04-24 23:59:59
start_time = int(datetime(2026, 4, 22, 0, 0, 0).timestamp())
end_time = int(datetime(2026, 4, 24, 23, 59, 59).timestamp())

print(f"搜索用户: {target_name} ({target_wxid})")
print(f"时间范围: 2026-04-22 00:00:00 到 2026-04-24 23:59:59")
print(f"时间戳范围: {start_time} 到 {end_time}")
print("=" * 80)

# 遍历所有 MSG*.db 文件，提取最近两天的消息
print("\n遍历所有 MSG 数据库，提取最近两天的消息...")
all_messages = []

for db_file in ['output/decrypted_db/Multi/MSG0.db', 'output/decrypted_db/Multi/MSG1.db']:
    print(f"\n正在处理: {db_file}")
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()

    # 查询时间范围内的所有群聊消息
    cur.execute("""
        SELECT CreateTime, StrTalker, StrContent, IsSender, Type, SubType, BytesExtra
        FROM MSG
        WHERE StrTalker LIKE '%chatroom%'
        AND CreateTime >= ?
        AND CreateTime <= ?
        ORDER BY CreateTime ASC
    """, (start_time, end_time))

    messages = cur.fetchall()
    print(f"  找到 {len(messages)} 条群聊消息，正在筛选...")

    for msg in messages:
        bytes_extra = msg[6]

        # 检查是否是目标用户发送的消息
        is_target_user = False

        # 方法1：如果是当前用户发送的消息（IsSender=1），跳过
        if msg[3] == 1:
            continue

        # 方法2：检查 BytesExtra 中是否包含目标 wxid
        if bytes_extra and target_wxid.encode() in bytes_extra:
            is_target_user = True

        if is_target_user:
            all_messages.append({
                'db': db_file,
                'time': msg[0],
                'chatroom': msg[1],
                'content': msg[2],
                'is_sender': msg[3],
                'type': msg[4],
                'subtype': msg[5],
                'bytes_extra': bytes_extra
            })

    print(f"  筛选出 {len([m for m in all_messages if m['db'] == db_file])} 条目标用户消息")
    conn.close()

# 按时间排序
all_messages.sort(key=lambda x: x['time'])

# 输出结果
print("\n" + "=" * 80)
print(f"共找到 {len(all_messages)} 条消息")
print("=" * 80)

output_file = 'output/zongzhen_recent_messages.txt'
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(f"搜索用户: {target_name} ({target_wxid})\n")
    f.write(f"时间范围: 2026-04-22 00:00:00 到 2026-04-24 23:59:59\n")
    f.write(f"共找到 {len(all_messages)} 条消息\n")
    f.write("=" * 80 + "\n\n")

    for i, msg in enumerate(all_messages, 1):
        time_str = datetime.fromtimestamp(msg['time']).strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"[{i}] {time_str}\n")
        f.write(f"数据库: {msg['db']}\n")
        f.write(f"群聊: {msg['chatroom']}\n")
        f.write(f"类型: Type={msg['type']}, SubType={msg['subtype']}\n")
        f.write(f"内容: {msg['content']}\n")
        f.write("-" * 80 + "\n\n")

        # 同时输出到控制台
        print(f"\n[{i}] {time_str}")
        print(f"群聊: {msg['chatroom']}")
        print(f"类型: Type={msg['type']}, SubType={msg['subtype']}")

        # 根据消息类型显示内容
        if msg['type'] == 1:  # 文本消息
            print(f"内容: {msg['content']}")
        elif msg['type'] == 3:  # 图片消息
            print(f"内容: [图片消息]")
        elif msg['type'] == 49:  # 链接/文件等
            print(f"内容: [特殊消息] {msg['content'][:100] if msg['content'] else ''}")
        else:
            print(f"内容: {msg['content'][:200] if msg['content'] else '[无文本内容]'}")

print(f"\n完整结果已保存到: {output_file}")

# 分析爬虫需求
print("\n" + "=" * 80)
print("分析爬虫需求")
print("=" * 80)

# 统计消息类型
type_stats = {}
for msg in all_messages:
    msg_type = f"Type={msg['type']}"
    type_stats[msg_type] = type_stats.get(msg_type, 0) + 1

print("\n消息类型统计:")
for msg_type, count in sorted(type_stats.items(), key=lambda x: x[1], reverse=True):
    type_name = {
        'Type=1': '文本消息',
        'Type=3': '图片消息',
        'Type=34': '语音消息',
        'Type=43': '视频消息',
        'Type=47': '表情消息',
        'Type=49': '链接/文件消息',
    }.get(msg_type, '其他')
    print(f"  {msg_type} ({type_name}): {count} 条")

# 提取所有文本内容用于需求分析
print("\n完整对话内容:")
print("-" * 80)
for i, msg in enumerate(all_messages, 1):
    time_str = datetime.fromtimestamp(msg['time']).strftime('%Y-%m-%d %H:%M:%S')
    if msg['type'] == 1:  # 文本消息
        print(f"[{time_str}] {msg['content']}")
    elif msg['type'] == 3:
        print(f"[{time_str}] [发送了一张图片]")
    else:
        print(f"[{time_str}] [Type={msg['type']}消息]")

print("\n" + "=" * 80)
print("爬虫需求总结")
print("=" * 80)

# 提取关键信息
urls = []
keywords = []
for msg in all_messages:
    content = msg['content'] or ''

    # 提取 URL
    if 'http' in content.lower():
        import re
        found_urls = re.findall(r'https?://[^\s<>"]+', content)
        urls.extend(found_urls)

    # 提取关键词
    if any(kw in content for kw in ['爬', '网站', '数据', '图纸', '轴承', '型号']):
        keywords.append(content)

if urls:
    print("\n目标网站:")
    for url in urls:
        print(f"  - {url}")

if keywords:
    print("\n关键需求描述:")
    for kw in keywords:
        print(f"  - {kw}")

print("\n[OK] 搜索完成！")
