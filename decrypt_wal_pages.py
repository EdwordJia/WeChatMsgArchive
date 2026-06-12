import os, sys, hashlib, hmac, json
sys.stdout.reconfigure(encoding='utf-8')
from multiprocessing import freeze_support
freeze_support()

import psutil, pythoncom, ctypes
from wxManager import Me
from wxManager.decrypt.common import WeChatInfo, get_version
from wxManager.decrypt.wx_info_v3 import get_info_wxid, get_wx_dir, get_key, get_exe_bit
from wxManager.decrypt.decrypt_v3 import DEFAULT_PAGESIZE, KEY_SIZE, DEFAULT_ITER, SQLITE_FILE_HEADER
from Crypto.Cipher import AES

# 获取微信密钥
for process in psutil.process_iter(['name', 'exe', 'pid']):
    if process.name() != 'WeChat.exe':
        continue
    wechat_info = WeChatInfo()
    wechat_info.pid = process.pid
    try:
        pythoncom.CoInitialize()
        wechat_info.version = get_version(process.pid)
    except Exception:
        wechat_info.version = '3.9.12.57'
    wechat_base_address = 0
    for module in process.memory_maps(grouped=False):
        if module.path and 'WeChatWin.dll' in module.path:
            wechat_base_address = int(module.addr, 16)
            break
    if wechat_base_address == 0:
        continue
    Handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, process.pid)
    wechat_info.wxid = get_info_wxid(Handle)
    wechat_info.wx_dir = get_wx_dir(wechat_info.wxid) if wechat_info.wxid != 'None' else ''
    if not wechat_info.wx_dir:
        continue
    addrLen = get_exe_bit(process.exe()) // 8
    wechat_info.key = get_key(wechat_info.wx_dir, addrLen)
    if wechat_info.key and wechat_info.key != 'None':
        key = wechat_info.key
        break

print(f'密钥: {key[:16]}...')

password = bytes.fromhex(key.strip())
src_db = r'E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822\Msg\Multi\MSG1.db'
src_wal = src_db + '-wal'

# 读取加密DB的salt
with open(src_db, 'rb') as f:
    db_header = f.read(16)
salt = db_header[:16]
byteKey = hashlib.pbkdf2_hmac("sha1", password, salt, DEFAULT_ITER, KEY_SIZE)
print(f'密钥派生完成, page_size={DEFAULT_PAGESIZE}')

# 读取WAL文件
wal_size = os.path.getsize(src_wal)
print(f'WAL文件大小: {wal_size} bytes')

with open(src_wal, 'rb') as f:
    wal_data = f.read()

# 解析WAL header
page_size = int.from_bytes(wal_data[8:12], 'big')
print(f'WAL page_size: {page_size}')

# 解析frames
offset = 32  # WAL header
decrypted_pages = {}
frame_count = 0

while offset + 24 <= len(wal_data):
    page_number = int.from_bytes(wal_data[offset:offset+4], 'big')
    commit_mark = int.from_bytes(wal_data[offset+4:offset+8], 'big')

    frame_data_start = offset + 24
    frame_data_end = frame_data_start + page_size

    if frame_data_end > len(wal_data):
        print(f'Frame {frame_count}: 不完整, 跳过 (page {page_number})')
        break

    page_data = wal_data[frame_data_start:frame_data_end]

    # 解密页面
    try:
        iv = page_data[-48:-32]
        encrypted = page_data[:-48]
        t = AES.new(byteKey, AES.MODE_CBC, iv)
        decrypted = t.decrypt(encrypted)
        full_page = decrypted + page_data[-48:]
        decrypted_pages[page_number] = full_page
        frame_count += 1
    except Exception as e:
        print(f'Frame {frame_count}: 解密失败 page {page_number}: {e}')

    offset = frame_data_end

print(f'解析了 {frame_count} 个WAL帧, {len(decrypted_pages)} 个唯一页面')

# 合并到解密数据库
decrypted_db = 'output/decrypted_db/Multi/MSG1.db'
output_db = 'output/MSG1_merged.db'

existing_size = os.path.getsize(decrypted_db)
header_size = len(SQLITE_FILE_HEADER)
num_existing_pages = (existing_size - header_size) // DEFAULT_PAGESIZE

max_page = max(max(decrypted_pages.keys()) if decrypted_pages else 0, num_existing_pages)

print(f'现有DB页数: {num_existing_pages}, WAL最大页号: {max(decrypted_pages.keys()) if decrypted_pages else 0}')

with open(output_db, 'wb') as out:
    out.write(SQLITE_FILE_HEADER.encode())

    with open(decrypted_db, 'rb') as existing:
        existing.seek(header_size)

        for page_num in range(1, max_page + 1):
            if page_num in decrypted_pages:
                out.write(decrypted_pages[page_num])
            elif page_num <= num_existing_pages:
                page_data = existing.read(DEFAULT_PAGESIZE)
                out.write(page_data)
            else:
                # 新页面（WAL独有的），写零页
                out.write(b'\x00' * DEFAULT_PAGESIZE)

print(f'合并完成: {output_db}')
print(f'输出文件大小: {os.path.getsize(output_db)} bytes')
