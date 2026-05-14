import sqlite3
import xml.etree.ElementTree as ET
import os

conn = sqlite3.connect('output/decrypted_db/Multi/MSG1.db')
cur = conn.cursor()
cur.execute('''
    SELECT StrContent FROM MSG
    WHERE StrTalker='44601760933@chatroom' AND Type=3
    ORDER BY CreateTime DESC
''')
print('数据库中的 md5 和 originsourcemd5:')
for row in cur.fetchall():
    content = row[0]
    if content:
        try:
          root = ET.fromstring(content)
            img = root.find('img')
            if img is not None:
                md5 = img.get('md5', '')
                origin_md5 = img.get('originsourcemd5', '')
                print(f'md5: {md5}, originsourcemd5: {origin_md5}')
        except:
            pass
conn.close()

print('\n本地文件:')
image_dir = r'E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822\FileStorage\MsgAttach\c9f3a0fe419f2c95f9e5b8c1834c44dc\Image\2026-05'
if os.path.exists(image_dir):
    for file in os.listdir(image_dir):
        if file.endswith('.dat'):
            print(file.replace('.dat', ''))
