import json
import sys
from datetime import datetime

# 设置输出编码为UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# 读取JSON文件
with open(r'C:\Users\Administrator\.claude\projects\D--develoment-home-project-home-WeChatMsgArchive\c1bde299-8062-40a5-bccd-915273a18938\tool-results\tooluse_uX0HN8BzpWUEWjWHO5DuZM.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 解析嵌套的JSON字符串
result = json.loads(data[0]['text'])
messages = result['messages']

# 按时间倒序排列（最新的在前）
messages_sorted = sorted(messages, key=lambda x: x.get('create_time', 0), reverse=True)

# 输出最近100条消息
print(f"群聊ID: {result['group_id']}")
print(f"消息总数: {result['count']}")
print("\n" + "="*80)
print("最近的消息（按时间倒序）：")
print("="*80 + "\n")

for i, msg in enumerate(messages_sorted[:100], 1):
    timestamp = msg.get('create_time', 0)
    if timestamp:
        time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    else:
        time_str = 'N/A'

    content = msg.get('content', '')
    is_sender = "我" if msg.get('is_sender') == 1 else "对方"
    msg_type = msg.get('msg_type', 0)

    # 只显示文本消息和系统消息
    if msg_type in [1, 10000]:
        print(f"{i}. [{time_str}] {is_sender}: {content[:200]}")
        if len(content) > 200:
            print(f"   ... (消息过长，已截断)")
        print()
