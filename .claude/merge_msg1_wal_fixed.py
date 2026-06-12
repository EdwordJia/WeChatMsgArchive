import ctypes
import hashlib
import hmac
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from multiprocessing import freeze_support

sys.stdout.reconfigure(encoding='utf-8')
freeze_support()

import psutil
import pythoncom
from Crypto.Cipher import AES
from wxManager.decrypt.common import WeChatInfo, get_version
from wxManager.decrypt.wx_info_v3 import get_info_wxid, get_wx_dir, get_key, get_exe_bit
from wxManager.decrypt.decrypt_v3 import DEFAULT_ITER, DEFAULT_PAGESIZE, KEY_SIZE, SQLITE_FILE_HEADER


def load_key():
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
        handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, process.pid)
        wechat_info.wxid = get_info_wxid(handle)
        wechat_info.wx_dir = get_wx_dir(wechat_info.wxid) if wechat_info.wxid != 'None' else ''
        if not wechat_info.wx_dir:
            continue
        addr_len = get_exe_bit(process.exe()) // 8
        key = get_key(wechat_info.wx_dir, addr_len)
        if key and key != 'None':
            return key
    raise SystemExit('未获取到微信密钥')


def decrypt_wal_pages(src_db, src_wal, key):
    password = bytes.fromhex(key.strip())
    with open(src_db, 'rb') as f:
        salt = f.read(16)
    byte_key = hashlib.pbkdf2_hmac('sha1', password, salt, DEFAULT_ITER, KEY_SIZE)

    wal_data = Path(src_wal).read_bytes()
    page_size = int.from_bytes(wal_data[8:12], 'big')
    if page_size == 1:
        page_size = 65536
    if page_size != DEFAULT_PAGESIZE:
        raise SystemExit(f'不支持的 WAL page_size: {page_size}')

    pages = {}
    offset = 32
    frames = 0
    while offset + 24 + page_size <= len(wal_data):
        page_number = int.from_bytes(wal_data[offset:offset+4], 'big')
        page_data = wal_data[offset+24:offset+24+page_size]
        iv = page_data[-48:-32]
        if page_number == 1:
            encrypted = page_data[16:-48]
            decrypted = SQLITE_FILE_HEADER.encode() + AES.new(byte_key, AES.MODE_CBC, iv).decrypt(encrypted) + page_data[-48:]
        else:
            encrypted = page_data[:-48]
            decrypted = AES.new(byte_key, AES.MODE_CBC, iv).decrypt(encrypted) + page_data[-48:]
        pages[page_number] = decrypted
        frames += 1
        offset += 24 + page_size
    return pages, frames


def merge_pages(base_db, output_db, pages):
    base = bytearray(Path(base_db).read_bytes())
    for page_number, page_data in pages.items():
        start = (page_number - 1) * DEFAULT_PAGESIZE
        end = start + DEFAULT_PAGESIZE
        if len(base) < end:
            base.extend(b'\x00' * (end - len(base)))
        base[start:end] = page_data
    Path(output_db).write_bytes(base)


def main():
    src_db = r'E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822\Msg\Multi\MSG1.db'
    src_wal = src_db + '-wal'
    base_db = 'output/decrypted_db/Multi/MSG1.db'
    out_db = 'output/MSG1_merged_fixed.db'
    key = load_key()
    pages, frames = decrypt_wal_pages(src_db, src_wal, key)
    print(f'WAL帧数: {frames}, 唯一页: {len(pages)}, 包含第1页: {1 in pages}')
    merge_pages(base_db, out_db, pages)
    conn = sqlite3.connect(out_db)
    ok = conn.execute('PRAGMA integrity_check').fetchone()[0]
    print(f'integrity_check: {ok}')
    chatroom_id = '49584724187@chatroom'
    rows = conn.execute('''
        SELECT IsSender, CreateTime, StrContent, Type, SubType
        FROM MSG
        WHERE StrTalker = ? AND CreateTime >= ?
        ORDER BY CreateTime ASC
    ''', (chatroom_id, int(datetime(2026, 6, 1, 4, 0, 0).timestamp()))).fetchall()
    print(f'知识付费应用 6月1日04:00后: {len(rows)} 条')
    for is_sender, ts, content, msg_type, subtype in rows[-30:]:
        dt = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        sender = '我' if is_sender else '对方'
        print(f'[{dt}] {sender} type={msg_type}/{subtype}: {(content or "[无内容]")[:300]}')
    conn.close()


if __name__ == '__main__':
    main()
