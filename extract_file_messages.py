import sqlite3
import re
from datetime import datetime

db_path = 'output/decrypted_db/Multi/MSG1.db'
output_file = 'file_messages_info.txt'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 目标时间戳
target_time1 = int(datetime(2026, 5, 12, 17, 48, 30).timestamp())
target_time2 = int(datetime(2026, 5, 12, 17, 57, 54).timestamp())

# 查询Type=49的文件消息
cursor.execute('''
    SELECT CreateTime, CompressContent
    FROM MSG
    WHERE StrTalker = '49734720477@chatroom'
    AND Type = 49
    AND (CreateTime BETWEEN ? - 60 AND ? + 60
         OR CreateTime BETWEEN ? - 60 AND ? + 60)
    ORDER BY CreateTime
''', (target_time1, target_time1, target_time2, target_time2))

results = cursor.fetchall()
conn.close()

def extract_from_bytes(data):
    """直接从字节流中提取XML标签内容"""
    if not data:
        return None, None

    # 提取<title>标签中的CDATA内容
    # 注意：微信的CompressContent中标签可能不完整，需要灵活匹配
    title = None
    # 匹配 <title><![CDATA[...]]>，不要求完整的</title>
    title_match = re.search(rb'<title><!\[CDATA\[(.*?)\]\]>', data)
    if title_match:
        try:
            title = title_match.group(1).decode('utf-8', errors='replace')
        except:
            pass

    # 提取<des>标签内容
    # 由于压缩格式特殊，des标签可能也不完整
    # 观察数据发现 des/ 后面跟着的是压缩后的内容
    des = None
    # 尝试匹配 <des>...</des> 或 <des><![CDATA[...]]>
    des_match = re.search(rb'<des><!\[CDATA\[(.*?)\]\]>', data)
    if des_match:
        try:
          des = des_match.group(1).decode('utf-8', errors='replace')
        except:
            pass
    else:
        # 尝试匹配普通格式
        des_match = re.search(rb'<des>(.*?)</des>', data)
        if des_match:
            try:
                des = des_match.group(1).decode('utf-8', errors='replace')
            except:
                pass

    return title, des

# 解析并输出
output_lines = []
output_lines.append('从群 49734720477@chatroom 提取的文件消息信息\n')
output_lines.append(f'提取时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
output_lines.append('=' * 80 + '\n\n')

for idx, (create_time, compress_content) in enumerate(results, 1):
    msg_time = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')
    output_lines.append(f'消息 {idx}:\n')
    output_lines.append(f'时间: {msg_time}\n')

    title, des = extract_from_bytes(compress_content)

    output_lines.append(f'文件名: {title if title else "未找到"}\n')
    output_lines.append(f'描述: {des if des else "无描述"}\n')

    output_lines.append('\n' + '-' * 80 + '\n\n')

# 写入文件
with open(output_file, 'w', encoding='utf-8') as f:
    f.writelines(output_lines)

print(f'成功提取 {len(results)} 条文件消息')
print(f'结果已保存到: {output_file}')

# 同时输出到控制台
print('\n提取的内容:')
print(''.join(output_lines))
