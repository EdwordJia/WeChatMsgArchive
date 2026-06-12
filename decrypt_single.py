import json
import os
import sys
import ctypes
from multiprocessing import freeze_support

sys.stdout.reconfigure(encoding='utf-8')
freeze_support()

import psutil
import pythoncom
from wxManager import Me
from wxManager.decrypt.common import WeChatInfo, get_version
from wxManager.decrypt.wx_info_v3 import get_info_wxid, get_wx_dir, get_key, get_exe_bit
from wxManager.decrypt.decrypt_v3 import decrypt_db_file_v3
from datetime import datetime


v3_running = any(p.name() == 'WeChat.exe' for p in psutil.process_iter(['name']))
print(f'WeChat v3: {"运行中" if v3_running else "未检测到"}')

if not v3_running:
    print('错误: 未检测到微信进程')
    sys.exit(1)

wx_info = None
wx_version = None

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
        wx_info = wechat_info
        wx_version = 'v3'
        break

if not wx_info or not wx_info.key:
    print('错误: 未能获取解密密钥')
    sys.exit(1)

print(f'获取成功: {wx_version} ({wx_info.version})')
print(f'wxid: {wx_info.wxid}')

output_dir = 'output/decrypted_db'
os.makedirs(output_dir, exist_ok=True)

if wx_version == 'v3':
    src_dir = os.path.join(wx_info.wx_dir, 'Msg')
    print(f'\n开始单线程解密...')

    decrypted_count = 0
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.db'):
                src_file_path = os.path.join(root, file)
                relative_path = os.path.relpath(root, src_dir)
                dest_sub_dir = os.path.join(output_dir, relative_path)
                dest_file_path = os.path.join(dest_sub_dir, file)

                if not os.path.exists(dest_sub_dir):
                    os.makedirs(dest_sub_dir)

                print(f'  解密: {dest_file_path}')
                success, msg = decrypt_db_file_v3(wx_info.key, src_file_path, dest_file_path)
                if success:
                    decrypted_count += 1
                else:
                    print(f'    失败: {msg}')

    print(f'\n解密完成: {decrypted_count} 个数据库')

me = Me()
me.wx_dir = wx_info.wx_dir
me.wxid = wx_info.wxid
me.name = wx_info.wxid

info_path = os.path.join(output_dir, 'info.json')
with open(info_path, 'w', encoding='utf-8') as f:
    json.dump(me.to_json(), f, ensure_ascii=False, indent=2)

print(f'info.json 已生成')
