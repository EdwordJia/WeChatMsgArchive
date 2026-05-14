# -*- coding: utf-8 -*-
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime
import os
import shutil
import sys
import hashlib

sys.stdout.reconfigure(encoding='utf-8')

# 连接数据库
conn = sqlite3.connect('output/decrypted_db/Multi/MSG1.db')
cur = conn.cursor()

# 查询所有图片消息
cur.execute("""
    SELECT CreateTime, StrContent FROM MSG
    WHERE StrTalker='44601760933@chatroom' AND Type=3
    ORDER BY CreateTime DESC
""")

print('=== 肖战表情包群 图片消息 ===')
image_info = []
for ts, content in cur.fetchall():
    time_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    if content:
        try:
            root = ET.fromstring(content)
            img = root.find('img')
         if img is not None:
              md5 = img.get('md5', '')
            length = int(img.get('length', '0'))
                image_info.append({'time': time_str, 'md5': md5, 'size': length})
              print(f'{time_str} - MD5: {md5}, Size: {length}')
        except:
            pass

conn.close()
print(f'\n找到 {len(image_info)} 条图片消息')

# 计算群聊 ID 的 MD5 hash
chatroom_id = '44601760933@chatroom'
chatroom_hash = hashlib.md5(chatroom_id.encode()).hexdigest()

# 微信数据目录
wechat_data_dir = r'E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822'
image_dir = os.path.join(wechat_data_dir, 'FileStorage', 'MsgAttach', chatroom_hash, 'Image')

print(f'\n=== 查找本地图片文件 ===')
print(f'群聊 hash: {chatroom_hash}')
print(f'图片目录: {image_dir}')

output_dir = 'output/xiaozhan_images'
os.makedirs(output_dir, exist_ok=True)

# 收集所有本地图片文件
local_files = []
if os.path.exists(image_dir):
    for root, dirs, files in os.walk(image_dir):
        for file in files:
            if file.endswith('.dat'):
          file_path = os.path.join(root, file)
              file_size = os.path.getsize(file_path)
             local_files.append({'path': file_path, 'name': file, 'size': file_size})

print(f'找到 {len(local_files)} 个本地图片文件')

# 根据文件大小匹配（允许±200字节的误差，或10倍差异）
found_count = 0
not_found_count = 0
found_files = []

for info in image_info:
    target_size = info['size']
    md5 = info['md5']
    matched = False
    
    for local_file in local_files:
        size_diff = abs(local_file['size'] - target_size)
        # 允许200字节误差，或者10倍差异（压缩前后）
        if size_diff <= 200 or abs(local_file['size'] / target_size - 10) < 0.5:
            src_path = local_file['path']
            dst_path = os.path.join(output_dir, f"{md5}.jpg")
            shutil.copy2(src_path, dst_path)
            print(f'Matched: {local_file["name"]} (size diff: {size_diff}) -> {md5}.jpg')
          found_files.append(dst_path)
     matched = True
            found_count += 1
         break
    
    if not matched:
        print(f'Not found: MD5={md5}, Size={target_size}')
        not_found_count += 1

print(f'\n=== 统计结果 ===')
print(f'总图片消息数: {len(image_info)}')
print(f'成功找到并复制: {found_count}')
print(f'未找到: {not_found_count}')
print(f'图片保存目录: {os.path.abspath(output_dir)}')
