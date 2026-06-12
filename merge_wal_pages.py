import os, sys, hashlib, hmac, shutil
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
key = None
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

if not key:
    print('无法获取密钥')
    sys.exit(1)

print(f'密钥: {key[:16]}...')

password = bytes.fromhex(key.strip())
src_db = r'E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822\Msg\Multi\MSG1.db'
src_wal = src_db + '-wal'

# 读取加密DB的salt
with open(src_db, 'rb') as f:
    db_header = f.read(16)
salt = db_header[:16]
byteKey = hashlib.pbkdf2_hmac("sha1", password, salt, DEFAULT_ITER, KEY_SIZE)

# 解析WAL
with open(src_wal, 'rb') as f:
    wal_data = f.read()

page_size_bytes = int.from_bytes(wal_data[8:12], 'big')
print(f'page_size={page_size_bytes}, wal_size={len(wal_data)}')

# 解析frames，解密页面
offset = 32
decrypted_pages = {}

while offset + 24 + page_size_bytes <= len(wal_data):
    page_number = int.from_bytes(wal_data[offset:offset+4], 'big')

    frame_data_start = offset + 24
    frame_data_end = frame_data_start + page_size_bytes

    page_data = wal_data[frame_data_start:frame_data_end]

    try:
        iv = page_data[-48:-32]
        encrypted = page_data[:-48]
        t = AES.new(byteKey, AES.MODE_CBC, iv)
        decrypted = t.decrypt(encrypted)
        full_page = decrypted + page_data[-48:]
        decrypted_pages[page_number] = full_page
    except:
        pass

    offset = frame_data_end

print(f'解密了 {len(decrypted_pages)} 个WAL页面')

# 复制解密后的MSG1.db，然后patch页面
src_decrypted = 'output/decrypted_db/Multi/MSG1.db'
dst_patched = 'output/MSG1_patched.db'

shutil.copy2(src_decrypted, dst_patched)

header_size = len(SQLITE_FILE_HEADER)

with open(dst_patched, 'r+b') as f:
    f.seek(0, 2)
    file_size = f.tell()
    num_pages = (file_size - header_size) // DEFAULT_PAGESIZE

    patched_count = 0
    for page_num in sorted(decrypted_pages.keys()):
        if page_num < 1:
            continue
        if page_num > num_pages:
            # 页面超出文件范围，需要扩展文件
            extend_pages = page_num - num_pages
            f.write(b'\x00' * (extend_pages * DEFAULT_PAGESIZE))
            num_pages = page_num
            print(f'  扩展文件到 {num_pages} 页')

        offset = header_size + (page_num - 1) * DEFAULT_PAGESIZE
        f.seek(offset)
        f.write(decrypted_pages[page_num])
        patched_count += 1

print(f'Patched {patched_count} pages')
print(f'输出: {dst_patched} ({os.path.getsize(dst_patched)} bytes)')
