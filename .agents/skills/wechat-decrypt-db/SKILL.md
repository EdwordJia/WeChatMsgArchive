---
name: wechat-decrypt-db
description: Decrypt WeChat database files from a running WeChat process. Extracts encryption key from memory, decrypts all .db files, and saves them to output/decrypted_db/ for use by other search/analysis skills. Supports both WeChat v3 (WeChat.exe) and v4 (Weixin.exe). Use when the user wants to refresh the database, update chat data, decrypt WeChat DB, or before running any search skill on stale data. Triggers on keywords like "解密数据库", "刷新数据库", "更新聊天数据", "重新解密", "decrypt", "refresh db".
---

# 微信数据库解密技能

从运行中的微信进程提取密钥，批量解密数据库文件，输出到 `output/decrypted_db/` 供其他技能使用。

## 前置条件

- 微信必须已登录并正在运行
- v3 版本进程名为 `WeChat.exe`，v4 版本为 `Weixin.exe`
- 需要管理员权限读取进程内存

## Instructions

### Step 1: 检测微信版本

```python
import json, os, sys, ctypes
from multiprocessing import freeze_support
sys.stdout.reconfigure(encoding='utf-8')

freeze_support()

import psutil, pythoncom

# 检测运行中的微信版本
v3_running = any(p.name() == 'WeChat.exe' for p in psutil.process_iter(['name']))
v4_running = any(p.name() == 'Weixin.exe' for p in psutil.process_iter(['name']))

print(f'WeChat v3 (WeChat.exe): {"运行中" if v3_running else "未检测到"}')
print(f'WeChat v4 (Weixin.exe): {"运行中" if v4_running else "未检测到"}')

if not v3_running and not v4_running:
    print('错误: 未检测到微信进程，请先登录微信')
    sys.exit(1)
```

### Step 2: 获取微信信息

v3 使用绕过版本号的方式直接从内存提取 wxid 和 key（标准 `get_info_v3` 在部分版本下会因版本号不匹配而获取不到密钥）：

```python
from wxManager import Me
from wxManager.decrypt.common import WeChatInfo, get_version

wx_info = None
wx_version = None

if v3_running:
    from wxManager.decrypt.wx_info_v3 import get_info_wxid, get_wx_dir, get_key, get_exe_bit
    from wxManager.decrypt import decrypt_v3

    for process in psutil.process_iter(['name', 'exe', 'pid']):
        if process.name() != 'WeChat.exe':
            continue

        wechat_info = WeChatInfo()
        wechat_info.pid = process.pid
        try:
            pythoncom.CoInitialize()
            wechat_info.version = get_version(process.pid)
        except:
            wechat_info.version = '3.9.12.57'

        # 查找 WeChatWin.dll 基址
        wechat_base_address = 0
        for module in process.memory_maps(grouped=False):
            if module.path and 'WeChatWin.dll' in module.path:
                wechat_base_address = int(module.addr, 16)
                break
        if wechat_base_address == 0:
            print('找不到 WeChatWin.dll，跳过此进程')
            continue

        Handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, process.pid)
        wechat_info.wxid = get_info_wxid(Handle)
        wechat_info.wx_dir = get_wx_dir(wechat_info.wxid) if wechat_info.wxid != 'None' else ''

        if not wechat_info.wx_dir:
            print(f'获取数据目录失败, wxid={wechat_info.wxid}')
            continue

        addrLen = get_exe_bit(process.exe()) // 8
        wechat_info.key = get_key(wechat_info.wx_dir, addrLen)

        if wechat_info.key and wechat_info.key != 'None':
            wx_info = wechat_info
            wx_version = 'v3'
            break

if v4_running:
    from wxManager.decrypt import get_info_v4
    from wxManager.decrypt.decrypt_dat import get_decode_code_v4
    from wxManager.decrypt import decrypt_v4

    r4 = get_info_v4()
    ok = [i for i in r4 if i.key]
    if ok:
        wx_info = ok[0]
        wx_version = 'v4'

if not wx_info or not wx_info.key:
    print('错误: 未能获取解密密钥，请重启微信后重试')
    sys.exit(1)

print(f'\n获取成功:')
print(f'  版本: {wx_version} ({wx_info.version})')
print(f'  wxid: {wx_info.wxid}')
print(f'  数据目录: {wx_info.wx_dir}')
print(f'  密钥: {wx_info.key[:16]}...')
```

### Step 3: 解密数据库

```python
output_dir = 'output/decrypted_db'
os.makedirs(output_dir, exist_ok=True)

key = wx_info.key
wx_dir = wx_info.wx_dir

if wx_version == 'v3':
    src_dir = os.path.join(wx_dir, 'Msg')
    print(f'\n开始解密 v3 数据库...')
    print(f'  源目录: {src_dir}')
    print(f'  输出目录: {output_dir}')
    decrypt_v3.decrypt_db_files(key, src_dir=src_dir, dest_dir=output_dir)
else:
    src_dir = wx_dir
    print(f'\n开始解密 v4 数据库...')
    print(f'  源目录: {src_dir}')
    print(f'  输出目录: {output_dir}')
    decrypt_v4.decrypt_db_files(key, src_dir=src_dir, dest_dir=output_dir)
```

### Step 4: 生成 info.json

```python
me = Me()
me.wx_dir = wx_info.wx_dir
me.wxid = wx_info.wxid
me.name = getattr(wx_info, 'nick_name', '') or wx_info.wxid

if wx_version == 'v4':
    me.xor_key = get_decode_code_v4(wx_info.wx_dir)

info_data = me.to_json()
info_path = os.path.join(output_dir, 'info.json')
with open(info_path, 'w', encoding='utf-8') as f:
    json.dump(info_data, f, ensure_ascii=False, indent=2)

print(f'\ninfo.json 已生成: {info_path}')
```

### Step 5: 验证并汇总

```python
db_count = 0
for root, dirs, files in os.walk(output_dir):
    for f in files:
        if f.endswith('.db'):
            db_count += 1

from datetime import datetime
print(f'\n{"="*50}')
print(f'解密完成!')
print(f'  解密时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print(f'  数据库数量: {db_count} 个')
print(f'  输出目录: {os.path.abspath(output_dir)}')
print(f'{"="*50}')
print(f'\n现在可以使用以下技能搜索聊天记录:')
print(f'  - wechat-contact-search (联系人搜索)')
print(f'  - wechat-group-analysis (群聊分析)')
print(f'  - wechat-member-trace (成员消息追踪)')
```

## 注意事项

- 解密过程使用多进程，耗时取决于数据库大小，通常 1-5 分钟
- 解密会覆盖 `output/decrypted_db/` 下的同名文件
- v3 的源数据在 `{wx_dir}/Msg/` 下，v4 直接在 `{wx_dir}/` 下
- v3 标准 `get_info_v3()` 依赖 `version_list.json` 匹配版本号偏移，新版本未收录时会获取不到密钥；绕过方式直接调用 `get_info_wxid` / `get_key` 不依赖版本号
- 如果密钥获取失败，通常重启微信可以解决
- 必须以管理员权限运行，否则无法读取微信进程内存
- 必须使用项目 venv 环境运行（`./venv/Scripts/python`），系统 Python 可能缺少 `yara` 等依赖

## 输出格式

```
WeChat v3 (WeChat.exe): 运行中
WeChat v4 (Weixin.exe): 未检测到

获取成功:
  版本: v3 (3.9.12.57)
  wxid: wxid_ucag2pjrmhm822
  数据目录: C:\Users\xxx\Documents\WeChat Files\wxid_xxx
  密钥: a1b2c3d4e5f6g7h8...

开始解密 v3 数据库...
  源目录: C:\Users\xxx\Documents\WeChat Files\wxid_xxx\Msg
  输出目录: output/decrypted_db

==================================================
解密完成!
  解密时间: 2026-04-13 14:30:00
  数据库数量: 38 个
  输出目录: D:\project\WeChatMsgArchive\output\decrypted_db
==================================================
```
