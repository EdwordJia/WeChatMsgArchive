#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
提取"肖战表情包"群（44601760933@chatroom）的完整聊天记录
"""

import sqlite3
import json
import csv
import os
from datetime import datetime
from collections import Counter


def parse_bytes_extra(data):
    """从 BytesExtra 中提取发送者 wxid"""
    if not data:
        return None
    try:
     i = 0
        while i < len(data):
            if data[i] == 0x1a:
           i += 1
                if i >= len(data):
                break
                length = data[i]
                i += 1
            sub = data[i:i+length]
                j = 0
                while j < len(sub):
                  if sub[j] == 0x08 and j+1 < len(sub) and sub[j+1] == 0x01 and j+2 < len(sub) and sub[j+2] == 0x12:
                        j += 3
                        wxid_len = sub[j]
              j += 1
                    return sub[j:j+wxid_len].decode('utf-8', errors='ignore')
                j += 1
              i += length
            else:
          i += 1
    except:
        pass
    return None


def main():
    # 配置
    group_id = '44601760933@chatroom'
    micro_db = 'output/decrypted_db/MicroMsg.db'
    msg_db = 'output/decrypted_db/Multi/MSG0.db'
    info_json = 'output/decrypted_db/info.json'
    out_dir = 'output'

    # 确保输出目录存在
    os.makedirs(out_dir, exist_ok=True)

    print(f"=== 开始提取群聊记录 ===")
    print(f"群ID: {group_id}")
    print()

    # Step 1: 读取自己的 wxid
    print("[1/5] 读取用户信息...")
    with open(info_json, 'r', encoding='utf-8') as f:
        my_wxid = json.load(f).get('wxid', '')
    print(f"  我的 wxid: {my_wxid}")

    # Step 2: 加载群成员映射
    print("\n[2/5] 加载群成员映射...")
  conn_micro = sqlite3.connect(micro_db)
    cur_micro = conn_micro.cursor()

    # 获取群成员列表
    cur_micro.execute('SELECT UserNameList FROM ChatRoom WHERE ChatRoomName=?', (group_id,))
    row = cur_micro.fetchone()

  member_map = {my_wxid: '我'}
    member_count = 1

    if row and row[0]:
        member_list = [wxid for wxid in row[0].split('^G') if wxid]
        member_count = len(member_list)
        print(f"  群成员数: {member_count}")

        for wxid in member_list:
        if wxid == my_wxid:
            continue
            cur_micro.execute('SELECT NickName, Remark FROM Contact WHERE UserName=?', (wxid,))
            c = cur_micro.fetchone()
            if c:
                member_map[wxid] = c[1] if c[1] else c[0]
        else:
         member_map[wxid] = wxid
    else:
        print("  警告: 未找到群成员列表")

    conn_micro.close()

    # Step 3: 提取群消息
    print("\n[3/5] 提取群消息...")
    conn_msg = sqlite3.connect(msg_db)
    cur_msg = conn_msg.cursor()

    cur_msg.execute(""
        SELECT Type, IsSender, CreateTime, StrContent, BytesExtra
        FROM MSG WHERE StrTalker=? ORDER BY CreateTime
    """, (group_id,))

    messages = []
    for msg_type, is_sender, ts, content, bytes_extra in cur_msg.fetchall():
     # 确定发送者
        if is_sender:
            sender_wxid = my_wxid
        else:
        sender_wxid = parse_bytes_extra(bytes_extra) or ''

        sender_name = member_map.get(sender_wxid, sender_wxid or '未知')

        # 格式化时间
        ts_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else '未知'

        # 消息类型映射
        type_map = {
            1: '文本',
        3: '图片',
       34: '语音',
            43: '视频',
            47: '表情包',
            10000: '系统消息',
            49: '链接/文件'
        }
        type_name = type_map.get(msg_type, f'类型{msg_type}')

        # 消息内容
      text_map = {
       3: '[图片]',
            34: '[语音]',
            43: '[视频]',
            47: '[表情包]',
            49: '[链接/文件]'
        }

        if msg_type == 1:
            text = content or ''
        else:
        text = text_map.get(msg_type, content or f'[{type_name}]')

        messages.append((ts_str, sender_name, type_name, text, msg_type))

    conn_msg.close()
    print(f"  提取消息数: {len(messages)}")

    # Step 4: 生成统计数据
    print("\n[4/5] 生成统计数据...")
    real_msgs = [m for m in messages if m[4] != 10000]
    sender_cnt = Counter(m[1] for m in real_msgs)
    date_cnt = Counter(m[0][:10] for m in real_msgs)
    type_cnt = Counter(m[2] for m in messages)

    # 时间跨度
    if messages:
        time_start = messages[0][0][:10]
        time_end = messages[-1][0][:10]
    else:
        time_start = time_end = '未知'

    # Step 5: 导出文件
    print("\n[5/5] 导出文件...")
    safe_name = group_id.replace('@chatroom', '')

    # TXT 格式
    txt_file = f'{out_dir}/group_{safe_name}_full.txt'
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write(f'群ID: {group_id}\n')
        f.write(f'总消息数: {len(messages)}\n')
        f.write(f'时间跨度: {time_start} ~ {time_end}\n\n')
        f.write('=' * 60 + '\n\n')

        for ts, name, type_name, text, _ in messages:
            f.write(f'[{ts}] {name}\n')
            f.write(f'{text}\n\n')
    print(f"  ✓ {txt_file}")

    # CSV 格式
    csv_file = f'{out_dir}/group_{safe_name}_full.csv'
    with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['时间', '发送者', '消息类型', '内容'])
        for m in messages:
         writer.writerow([m[0], m[1], m[2], m[3]])
    print(f"  ✓ {csv_file}")

    # 统计报告
    stats_file = f'{out_dir}/group_{safe_name}_stats.txt'
    with open(stats_file, 'w', encoding='utf-8') as f:
        f.write(f'=== 群聊统计报告 ===\n\n')
        f.write(f'群ID: {group_id}\n')
        f.write(f'成员数: {member_count}\n')
        f.write(f'总消息数: {len(messages)}\n')
        f.write(f'有效消息数: {len(real_msgs)}\n')
        f.write(f'时间跨度: {time_start} ~ {time_end}\n\n')

        f.write('【发言排行】\n')
        for name, cnt in sender_cnt.most_common():
            pct = cnt * 100.0 / len(real_msgs) if real_msgs else 0
          f.write(f'  {name}: {cnt}条 ({pct:.1f}%)\n')

        f.write('\n【按日期】\n')
        for d in sorted(date_cnt):
            f.write(f'  {d}: {date_cnt[d]}条\n')

        f.write('\n【消息类型】\n')
        for t, c in type_cnt.most_common():
            f.write(f'  {t}: {c}条\n')
    print(f"  ✓ {stats_file}")

    # Step 6: 控制台汇总输出
    print("\n" + "=" * 60)
    print(f"=== 群聊分析：肖战表情包 ===")
    print(f"群ID: {group_id}")
    print(f"成员数: {member_count}")
    print(f"总消息数: {len(messages)}")
    print(f"时间跨度: {time_start} ~ {time_end}")
    print()
    print("【发言排行 Top 5】")
  for name, cnt in sender_cnt.most_common(5):
        pct = cnt * 100.0 / len(real_msgs) if real_msgs else 0
        print(f"  {name}: {cnt}条 ({pct:.1f}%)")
    print()
    print("【消息类型】")
    type_list = []
    for t, c in type_cnt.most_common():
        type_list.append(f"{t}: {c}")
    print("  " + " | ".join(type_list))
    print()
    print("已导出:")
    print(f"  {txt_file}")
    print(f"  {csv_file}")
    print(f"  {stats_file}")
    print("=" * 60)


if __name__ == '__main__':
    main()
