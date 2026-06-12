#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""搜索今天的客户反馈信息"""

import sys
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
import os

sys.stdout.reconfigure(encoding='utf-8')

FEEDBACK_KEYWORDS = [
    'bug', 'BUG', '问题', '错误', '异常', '崩溃', '闪退',
    '需要', '希望', '能不能', '可以', '建议', '增加', '添加',
    '改成', '改为', '调整', '优化', '支持', '实现', '功能',
    '不行', '失败', '无法', '不能', '报错', '修复'
]
def get_today_timestamp_range():
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    today_ts = int(today.timestamp() * 1000)
    tomorrow_ts = int(tomorrow.timestamp() * 1000)
    return today_ts, tomorrow_ts

def get_group_names(micromsg_db_path):
    group_names = {}
    if not os.path.exists(micromsg_db_path):
        print(f"警告: MicroMsg.db 不存在: {micromsg_db_path}")
        return group_names
    try:
        conn = sqlite3.connect(micromsg_db_path)
      cursor = conn.cursor()
        cursor.execute("""
          SELECT UserName, NickName, Remark
            FROM Contact
            WHERE UserName LIKE '%@chatroom'
        """)
        for row in cursor.fetchall():
            username, nickname, remark = row
            display_name = remark if remark else nickname
            if display_name:
                group_names[username] = display_name
       else:
              group_names[username] = username
        conn.close()
        print(f"成功加载 {len(group_names)} 个群聊名称")
    except Exception as e:
        print(f"读取群名称失败: {e}")
    return group_names

def search_today_feedback(index_db_path, micromsg_db_path):
    if not os.path.exists(index_db_path):
        print(f"错误: 索引数据库不存在: {index_db_path}")
        return
    today_start, today_end = get_today_timestamp_range()
    print(f"搜索时间范围: {datetime.fromtimestamp(today_start/1000)} 到 {datetime.fromtimestamp(today_end/1000)}")
    group_names = get_group_names(micromsg_db_path)
    conn = sqlite3.connect(index_db_path)
    cursor = conn.cursor()
    keyword_conditions = " OR ".join([f"content LIKE '%{kw}%'" for kw in FEEDBACK_KEYWORDS])
    query = f"""
        SELECT talker, content, sender_wxid, create_time, msg_type
        FROM messages
        WHERE create_time >= ? AND create_time < ?
        AND talker LIKE '%@chatroom'
        AND ({keyword_conditions})
        ORDER BY talker, create_time DESC
    """
    cursor.execute(query, (today_start, today_end))
    results = cursor.fetchall()
    conn.close()
    if not results:
        print("
今天没有找到包含反馈关键词的群聊消息")
        return
    group_feedbacks = defaultdict(list)
    for talker, content, sender_wxid, create_time, msg_type in results:
        group_feedbacks[talker].append({
          'content': content,
            'sender': sender_wxid,
         'time': datetime.fromtimestamp(create_time / 1000).strftime('%H:%M:%S'),
            'msg_type': msg_type
        })
    print(f"
{'='*80}")
    print(f"今天的客户反馈汇总 ({len(results)} 条消息，{len(group_feedbacks)} 个群)")
    print(f"{'='*80}
")
    sorted_groups = sorted(group_feedbacks.items(), key=lambda x: len(x[1]), reverse=True)
    for talker, feedbacks in sorted_groups:
        group_name = group_names.get(talker, talker)
        print(f"
【{group_name}】")
        print(f"反馈数量: {len(feedbacks)} 条")
        print(f"群ID: {talker}")
        print("-" * 80)
     for i, feedback in enumerate(feedbacks[:5], 1):
            print(f"
{i}. [{feedback['time']}] {feedback['sender']}")
          content = feedback['content'][:200]
            if len(feedback['content']) > 200:
             content += "..."
            print(f"   {content}")
        if len(feedbacks) > 5:
            print(f"
   ... 还有 {len(feedbacks) - 5} 条反馈未显示")
        print()

def main():
    index_db_path = "output/wechat_index.db"
    micromsg_db_path = "output/decrypted_db/Multi/MicroMsg.db"
    print("开始搜索今天的客户反馈...")
    search_today_feedback(index_db_path, micromsg_db_path)
    print("
搜索完成！")

if __name__ == "__main__":
    main()
