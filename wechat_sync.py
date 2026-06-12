#!/usr/bin/env python3
"""
微信消息同步工作流
一键完成：解密数据库 -> 遍历所有 MSG*.db -> 导出指定群聊 -> 生成报告

用法:
    ./venv/Scripts/python wechat_sync.py [群ID]

示例:
    ./venv/Scripts/python wechat_sync.py
    ./venv/Scripts/python wechat_sync.py 44637051187@chatroom
"""
import hashlib
import json
import os
import sys
import sqlite3
import shutil
import ctypes
import glob
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from multiprocessing import freeze_support

# Windows 多进程兼容 + UTF-8 输出
sys.stdout.reconfigure(encoding='utf-8')
freeze_support()

import psutil
import pythoncom

from wxManager.decrypt.decrypt_v3 import DEFAULT_ITER, DEFAULT_PAGESIZE, KEY_SIZE, SQLITE_FILE_HEADER
from Crypto.Cipher import AES
import lz4.block
from wxManager.decrypt.decrypt_dat import decode_dat, get_decode_code_v4


# =============================================================================
# 配置
# =============================================================================
OUTPUT_DIR = 'output/decrypted_db'
REPORT_DIR = 'output'
DEFAULT_GROUP = '44637051187@chatroom'


# =============================================================================
# Step 1: 解密数据库（单线程，避免 Windows 多进程 Bug）
# =============================================================================
def get_sqlite_page_size(db_path):
    try:
        conn = sqlite3.connect(db_path)
        page_size = conn.execute('PRAGMA page_size').fetchone()[0]
        conn.close()
        return page_size
    except sqlite3.DatabaseError:
        return None


def validate_msg_db(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='MSG'")
        if not cur.fetchone():
            conn.close()
            return False
        integrity = conn.execute('PRAGMA integrity_check').fetchone()
        if not integrity or integrity[0] != 'ok':
            conn.close()
            return False
        conn.execute('SELECT MAX(CreateTime) FROM MSG').fetchone()
        conn.close()
        return True
    except sqlite3.DatabaseError:
        return False


def write_wal_pages(dest_db_path, decrypted_pages, page_size, db_size_pages):
    with open(dest_db_path, 'r+b') as f:
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        for page_number, page_data in sorted(decrypted_pages.items()):
            required_size = page_number * page_size
            if file_size < required_size:
                f.seek(0, os.SEEK_END)
                f.write(b'\x00' * (required_size - file_size))
                file_size = required_size
            f.seek((page_number - 1) * page_size)
            f.write(page_data[:page_size])
        if db_size_pages:
            final_size = db_size_pages * page_size
            f.truncate(final_size)
            if 1 not in decrypted_pages:
                f.seek(28)
                f.write(db_size_pages.to_bytes(4, 'big'))


def merge_wal_into_decrypted_db(key, src_db_path, dest_db_path):
    wal_path = src_db_path + '-wal'
    if not os.path.exists(wal_path) or os.path.getsize(wal_path) <= 32:
        return 0

    password = bytes.fromhex(key.strip())
    with open(src_db_path, 'rb') as f:
        salt = f.read(16)
    if len(salt) != 16:
        return 0

    byte_key = hashlib.pbkdf2_hmac('sha1', password, salt, DEFAULT_ITER, KEY_SIZE)
    with open(wal_path, 'rb') as f:
        wal_data = f.read()

    page_size = int.from_bytes(wal_data[8:12], 'big') or DEFAULT_PAGESIZE
    if page_size == 1:
        page_size = 65536
    dest_page_size = get_sqlite_page_size(dest_db_path)
    if dest_page_size and dest_page_size != page_size:
        raise sqlite3.DatabaseError(f'WAL页大小({page_size})与解密库页大小({dest_page_size})不一致')
    wal_salt = (wal_data[16:20], wal_data[20:24])
    offset = 32
    frames = []

    while offset + 24 + page_size <= len(wal_data):
        page_number = int.from_bytes(wal_data[offset:offset + 4], 'big')
        commit_size = int.from_bytes(wal_data[offset + 4:offset + 8], 'big')
        frame_salt = (wal_data[offset + 8:offset + 12], wal_data[offset + 12:offset + 16])
        if frame_salt != wal_salt:
            break
        page_start = offset + 24
        page_end = page_start + page_size
        page_data = wal_data[page_start:page_end]
        if page_number > 0 and len(page_data) >= 48:
            iv = page_data[-48:-32]
            if page_number == 1:
                encrypted = page_data[len(SQLITE_FILE_HEADER):-48]
                decrypted = SQLITE_FILE_HEADER.encode() + AES.new(byte_key, AES.MODE_CBC, iv).decrypt(encrypted) + page_data[-48:]
            else:
                encrypted = page_data[:-48]
                decrypted = AES.new(byte_key, AES.MODE_CBC, iv).decrypt(encrypted) + page_data[-48:]
            frames.append((page_number, commit_size, decrypted))
        offset = page_end

    committed_frame_index = None
    db_size_pages = None
    for index, (_, commit_size, _) in enumerate(frames):
        if commit_size:
            committed_frame_index = index
            db_size_pages = commit_size
    if committed_frame_index is None:
        return 0

    decrypted_pages = {}
    for page_number, _, page_data in frames[:committed_frame_index + 1]:
        decrypted_pages[page_number] = page_data

    if not decrypted_pages:
        return 0

    backup_path = dest_db_path + '.prewal'
    shutil.copy2(dest_db_path, backup_path)
    try:
        write_wal_pages(dest_db_path, decrypted_pages, page_size, db_size_pages)
        if validate_msg_db(dest_db_path):
            os.remove(backup_path)
            return len(decrypted_pages)
        shutil.copy2(backup_path, dest_db_path)
        os.truncate(dest_db_path, os.path.getsize(backup_path))
        raise sqlite3.DatabaseError('WAL合并后数据库校验失败')
    except Exception:
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, dest_db_path)
            os.truncate(dest_db_path, os.path.getsize(backup_path))
        raise
    finally:
        if os.path.exists(backup_path):
            os.remove(backup_path)


# =============================================================================
# Step 1: 解密数据库（单线程，避免 Windows 多进程 Bug）
# =============================================================================
def step1_decrypt():
    """从运行中的微信进程提取密钥，单线程解密所有 .db 文件"""
    print('=' * 50)
    print('Step 1: 解密微信数据库...')

    from wxManager import Me
    from wxManager.decrypt.common import WeChatInfo, get_version
    from wxManager.decrypt.wx_info_v3 import get_info_wxid, get_wx_dir, get_key, get_exe_bit
    from wxManager.decrypt.decrypt_v3 import decrypt_db_file_v3

    # 检测微信进程
    v3_running = any(p.name() == 'WeChat.exe' for p in psutil.process_iter(['name']))
    if not v3_running:
        print('错误: 未检测到微信进程，请先登录微信')
        sys.exit(1)
    print(f'  WeChat v3: 运行中')

    # 提取密钥
    wx_info = None
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
            break

    if not wx_info or not wx_info.key:
        print('错误: 未能获取解密密钥，请重启微信后重试')
        sys.exit(1)

    print(f'  获取成功: wxid={wx_info.wxid}')

    # 清除旧解密文件（避免数据不同步）
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
        print('  已清除旧解密文件')
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 单线程解密
    src_dir = os.path.join(wx_info.wx_dir, 'Msg')
    decrypted_count = 0
    wal_page_count = 0
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.db'):
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(root, src_dir)
                dest_path = os.path.join(OUTPUT_DIR, rel_path, file)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                success, msg = decrypt_db_file_v3(wx_info.key, src_path, dest_path)
                if success:
                    decrypted_count += 1
                    rel_parts = rel_path.replace('\\', '/').split('/')
                    if rel_parts[0] == 'Multi' and file.startswith('MSG'):
                        try:
                            merged_pages = merge_wal_into_decrypted_db(wx_info.key, src_path, dest_path)
                            if merged_pages:
                                wal_page_count += merged_pages
                                print(f'    WAL合并: {os.path.join(rel_path, file)} ({merged_pages} pages)')
                        except Exception as exc:
                            print(f'    WAL合并失败: {os.path.join(rel_path, file)} - {exc}')
                else:
                    print(f'    失败: {file} - {msg}')

    print(f'  解密完成: {decrypted_count} 个数据库')
    if wal_page_count:
        print(f'  实时WAL页面已合并: {wal_page_count} 页')

    # 生成 info.json
    me = Me()
    me.wx_dir = wx_info.wx_dir
    me.wxid = wx_info.wxid
    me.name = wx_info.wxid
    info_path = os.path.join(OUTPUT_DIR, 'info.json')
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(me.to_json(), f, ensure_ascii=False, indent=2)
    print(f'  info.json 已生成')

    return wx_info.wxid, wx_info.wx_dir


# =============================================================================
# Step 2: 导出消息（遍历所有 MSG*.db，避免漏消息）
# =============================================================================
def clean_xml_text(value):
    if value is None:
        return ''
    if not isinstance(value, str):
        value = str(value)
    value = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', value, flags=re.S)
    value = re.sub(r'<[^>]+>', ' ', value)
    value = html.unescape(value)
    value = value.replace('\r', '\n')
    value = re.sub(r'[ \t]+', ' ', value)
    value = re.sub(r'\n\s*\n+', '\n', value)
    return value.strip()


def child_text(element, path):
    found = element.find(path)
    if found is None:
        return ''
    return clean_xml_text(''.join(found.itertext()))


def decompress_compress_content(data):
    if not data:
        return ''
    if isinstance(data, str):
        return data
    try:
        return lz4.block.decompress(data, uncompressed_size=len(data) << 10).decode('utf-8', errors='replace').replace('\x00', '')
    except Exception:
        return data.decode('utf-8', errors='replace').replace('\x00', '') if isinstance(data, bytes) else ''


def parse_record_xml(record_xml, limit=30):
    if not record_xml:
        return []
    record_xml = html.unescape(record_xml)
    try:
        root = ET.fromstring(record_xml)
    except ET.ParseError:
        record_xml = re.sub(r'&#(\d+);', '', record_xml)
        try:
            root = ET.fromstring(record_xml)
        except ET.ParseError:
            return []

    items = []
    for item in root.findall('.//dataitem')[:limit]:
        source = child_text(item, 'sourcename')
        when = child_text(item, 'sourcetime') or child_text(item, 'srcMsgCreateTime')
        text = child_text(item, 'datadesc') or child_text(item, 'datatitle')
        datatype = item.attrib.get('datatype', '')
        if not text:
            if datatype == '2':
                text = '[图片]'
            elif datatype == '37':
                text = '[表情]'
            elif datatype == '34':
                text = '[语音]'
            elif datatype == '43':
                text = '[视频]'
            elif datatype == '49':
                text = '[链接/小程序]'
            else:
                text = '[非文本消息]'
        prefix = ''
        if when or source:
            prefix = f"{when} {source}".strip() + ': '
        items.append(prefix + text)
    return items


def parse_merged_forward(compress_content):
    xml = decompress_compress_content(compress_content)
    if not xml:
        return '[合并转发聊天记录]'
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        root = None

    if root is None:
        title_match = re.search(r'<title>(.*?)</title>', xml, re.S)
        des_match = re.search(r'<des>(.*?)</des>', xml, re.S)
        lines = ['[合并转发聊天记录]']
        if title_match:
            lines.append('标题: ' + clean_xml_text(title_match.group(1)))
        if des_match:
            lines.append('摘要: ' + clean_xml_text(des_match.group(1)))
        return '\n'.join(lines)

    appmsg = root.find('appmsg')
    title = child_text(appmsg, 'title') if appmsg is not None else ''
    desc = child_text(appmsg, 'des') if appmsg is not None else ''
    record_xml = ''
    record_match = re.search(r'<recorditem><!\[CDATA\[(.*?)\]\]></recorditem>', xml, re.S)
    if record_match:
        record_xml = record_match.group(1)
    elif appmsg is not None:
        record_node = appmsg.find('recorditem')
        if record_node is not None:
            record_xml = ''.join(record_node.itertext())
    items = parse_record_xml(record_xml)

    lines = ['[合并转发聊天记录]']
    if title:
        lines.append('标题: ' + title)
    if desc:
        lines.append('摘要: ' + desc)
    if items:
        lines.append('内容:')
        lines.extend('- ' + item for item in items)
    return '\n'.join(lines)


def extract_md5_from_img_xml(content):
    """从图片消息的 StrContent XML 中提取 md5 属性"""
    if not content or not content.strip().startswith('<?xml'):
        return None
    try:
        root = ET.fromstring(content)
        img = root.find('.//img')
        if img is not None:
            return img.get('md5')
    except ET.ParseError:
        md5_match = re.search(r'md5="([0-9a-f]{32})"', content)
        if md5_match:
            return md5_match.group(1)
    return None


def download_group_images(group_id, wx_dir, image_messages):
    """解密群聊中的图片 .dat 文件，输出到 output/group_images/{group_id}/"""
    if not wx_dir or not image_messages:
        return {}

    attach_hash = hashlib.md5(group_id.encode()).hexdigest()
    attach_base = os.path.join(wx_dir, 'FileStorage', 'MsgAttach', attach_hash)
    if not os.path.exists(attach_base):
        print(f'  图片目录不存在: {attach_base}')
        return {}

    # v3图片用 xor_key=0 让 decode_dat 自动检测加密类型
    xor_key = 0

    safe_group = group_id.replace('@chatroom', '')
    out_dir = os.path.join(REPORT_DIR, 'group_images', safe_group)
    os.makedirs(out_dir, exist_ok=True)

    # 扫描所有.dat文件，建立 {dat文件名: dat_path} 的查找表
    dat_files = {}  # {md5hash_without_ext: dat_path}
    for subdir_name in ['Image', 'Thumb']:
        subdir = os.path.join(attach_base, subdir_name)
        if not os.path.exists(subdir):
            continue
        for date_dir in os.listdir(subdir):
            date_path = os.path.join(subdir, date_dir)
            if not os.path.isdir(date_path):
                continue
            for dat_name in os.listdir(date_path):
                if dat_name.endswith('.dat'):
                    # 提取hash: "abc123.dat" -> "abc123", "abc123_t.dat" -> "abc123"
                    base_name = dat_name.replace('_t.dat', '.dat').replace('.dat', '')
                    dat_path = os.path.join(date_path, dat_name)
                    dat_files.setdefault(base_name, dat_path)

    print(f'  找到 {len(dat_files)} 个.dat文件')

    # 方法1: 直接用XML md5匹配.dat文件名（两个都是md5但可能不同体系）
    # 方法2: 解密所有.dat文件，用时间戳关联
    # 优先方法2: 解密所有.dat文件到输出目录
    decrypted_files = {}  # {base_name: decrypted_path}
    for base_name, dat_path in dat_files.items():
        dt_prefix = base_name[:8]  # 不太有意义，但用于命名
        result = decode_dat(xor_key, dat_path, out_dir, base_name)
        if result and os.path.exists(result):
            decrypted_files[base_name] = os.path.abspath(result)

    print(f'  解密成功: {len(decrypted_files)}/{len(dat_files)} 个')

    # 将图片消息关联到解密后的文件
    # 策略: 每个Type=3的消息按时间顺序，与解密后的文件按文件名排序后一一对应
    # 但更可靠的是通过XML md5直接查找
    image_map = {}  # {svrid: decrypted_path}
    # 先尝试md5直接匹配
    for svrid, md5_val in image_messages:
        if md5_val and md5_val in decrypted_files:
            image_map[svrid] = decrypted_files[md5_val]

    # md5匹配不上的，按时间顺序匹配
    if len(image_map) < len(image_messages):
        # 按消息时间排序
        sorted_msgs = sorted(image_messages, key=lambda x: x[0] if isinstance(x[0], (int, float)) else 0)
        # 按文件名排序解密文件（文件名可能包含时间信息）
        sorted_files = sorted(decrypted_files.items(), key=lambda x: x[0])
        # 逐个分配未匹配的图片消息到未使用的解密文件
        used_files = set(image_map.values())
        file_idx = 0
        for svrid, md5_val in sorted_msgs:
            if svrid in image_map:
                continue
            # 找一个未使用的解密文件
            while file_idx < len(sorted_files):
                base_name, dec_path = sorted_files[file_idx]
                file_idx += 1
                if dec_path not in used_files:
                    image_map[svrid] = dec_path
                    used_files.add(dec_path)
                    break

    print(f'  图片映射完成: {len(image_map)}/{len(image_messages)} 张')
    return image_map


def render_message_text(msg_type, subtype, content, compress_content):
    if msg_type == 49 and subtype == 19:
        return parse_merged_forward(compress_content)
    text = content if content else '[无内容]'
    if text.strip().startswith('<?xml'):
        return '[图片/XML消息]'
    return text


# =============================================================================
# Step 2: 导出消息（遍历所有 MSG*.db，避免漏消息）
# =============================================================================
def step2_export_group(group_id, wx_dir=None):
    """从所有 MSG*.db 中导出指定群聊的消息，生成文本报告（含图片解密）"""
    print('\n' + '=' * 50)
    print('Step 2: 导出群聊消息...')
    print(f'  目标群: {group_id}')

    # 获取群名
    group_name = group_id
    micro_msg_db = os.path.join(OUTPUT_DIR, 'MicroMsg.db')
    if os.path.exists(micro_msg_db):
        conn = sqlite3.connect(micro_msg_db)
        conn.text_factory = lambda x: x.decode('utf-8', 'ignore') if isinstance(x, bytes) else x
        cur = conn.execute('SELECT NickName FROM Contact WHERE UserName=?', (group_id,))
        row = cur.fetchone()
        if row and row[0]:
            group_name = row[0]
        conn.close()

    # 遍历所有 MSG*.db（MSG0.db, MSG1.db, MSG2.db...）
    multi_dir = os.path.join(OUTPUT_DIR, 'Multi')
    db_files = sorted(glob.glob(os.path.join(multi_dir, 'MSG*.db')))

    if not db_files:
        print(f'  错误: 未找到 MSG*.db 文件，目录: {multi_dir}')
        sys.exit(1)

    print(f'  发现 {len(db_files)} 个消息数据库: {[os.path.basename(f) for f in db_files]}')

    # 收集所有消息
    all_messages = []
    for db_path in db_files:
        db_name = os.path.basename(db_path)
        conn = sqlite3.connect(db_path)
        conn.text_factory = lambda x: x.decode('utf-8', 'ignore') if isinstance(x, bytes) else x

        # 检查表结构
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='MSG'")
        if not cur.fetchone():
            print(f'    {db_name}: 无 MSG 表，跳过')
            conn.close()
            continue

        rows = conn.execute(
            'SELECT IsSender, CreateTime, StrContent, Type, SubType, CompressContent, BytesExtra, MsgSvrID FROM MSG WHERE StrTalker=? ORDER BY CreateTime',
            (group_id,)
        ).fetchall()
        conn.close()

        print(f'    {db_name}: {len(rows)} 条消息')
        all_messages.extend(rows)

    # 按时间排序去重
    all_messages.sort(key=lambda x: x[1])

    # 收集图片消息（Type=3），提取md5用于下载
    image_messages = []
    for row in all_messages:
        is_sender, ts, content, msg_type, subtype, compress_content, bytes_extra, svrid = row
        if msg_type == 3 and content:
            md5_val = extract_md5_from_img_xml(content)
            image_messages.append((svrid, md5_val))

    # 解密图片
    image_map = {}
    if wx_dir and image_messages:
        print(f'  发现 {len(image_messages)} 张图片，开始解密...')
        image_map = download_group_images(group_id, wx_dir, image_messages)

    # 生成报告文件
    safe_name = group_id.replace('@chatroom', '')
    report_path = os.path.join(REPORT_DIR, f'group_{safe_name}_latest.txt')
    os.makedirs(REPORT_DIR, exist_ok=True)

    image_index = []  # 图片索引列表

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f'群聊: {group_name}\n')
        f.write(f'群ID: {group_id}\n')
        f.write(f'消息总数: {len(all_messages)}\n')
        f.write(f'导出时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')

        for row in all_messages:
            is_sender, ts, content, msg_type, subtype, compress_content, bytes_extra, svrid = row
            dt = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else ''
            sender = '我' if is_sender else '对方'
            text = render_message_text(msg_type, subtype, content, compress_content)

            # 图片消息：如果解密成功，替换 [图片/XML消息] 为实际路径
            if msg_type == 3 and svrid in image_map:
                img_path = image_map[svrid]
                img_filename = os.path.basename(img_path)
                text = f'[图片: {img_filename}]'
                image_index.append((dt, img_filename, img_path))

            f.write(f'[{dt}] {sender}\n{text}\n\n')

        # 图片索引附录
        if image_index:
            f.write('\n' + '=' * 50 + '\n')
            f.write('图片索引\n')
            f.write('=' * 50 + '\n\n')
            for dt, filename, full_path in image_index:
                f.write(f'[{dt}] {filename}\n  路径: {full_path}\n\n')

    print(f'\n  报告已生成: {report_path}')
    print(f'  消息总数: {len(all_messages)}')
    return report_path, len(all_messages)


# =============================================================================
# Step 3: 打印最新消息摘要
# =============================================================================
def get_latest_message_time():
    latest = None
    multi_dir = os.path.join(OUTPUT_DIR, 'Multi')
    for db_path in sorted(glob.glob(os.path.join(multi_dir, 'MSG*.db'))):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='MSG'")
            if cur.fetchone():
                row = conn.execute('SELECT MAX(CreateTime) FROM MSG').fetchone()
                if row and row[0] and (latest is None or row[0] > latest):
                    latest = row[0]
            conn.close()
        except Exception:
            continue
    return latest


def step3_print_summary(report_path, count, n=10):
    """打印最近 N 条消息摘要"""
    if count == 0:
        print('\n  该群暂无消息')
        return

    print('\n' + '=' * 50)
    print(f'最新 {min(n, count)} 条消息摘要:')
    print('-' * 50)

    with open(report_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 找到消息正文行（跳过头部的群信息）
    msg_lines = []
    in_header = True
    for line in lines:
        if in_header and line.startswith('[') and ']' in line:
            in_header = False
        if not in_header:
            msg_lines.append(line)

    # 提取最后 N 条完整消息
    messages = []
    current = []
    for line in msg_lines:
        if line.startswith('[') and ']' in line and ('我' in line or '对方' in line):
            if current:
                messages.append(''.join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        messages.append(''.join(current))

    for msg in messages[-n:]:
        # 只打印前两行（时间和内容）
        lines = msg.strip().split('\n')
        if len(lines) >= 2:
            print(f'  {lines[0]}')
            content = lines[1][:80] + '...' if len(lines[1]) > 80 else lines[1]
            print(f'    {content}')
        print()


# =============================================================================
# 主入口
# =============================================================================
def main():
    group_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_GROUP

    print(f'微信消息同步工作流')
    print(f'目标群: {group_id}')
    print(f'开始时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print()

    # Step 1: 解密
    wxid, wx_dir = step1_decrypt()

    # Step 2: 导出（含图片解密）
    report_path, count = step2_export_group(group_id, wx_dir)

    # Step 3: 摘要
    step3_print_summary(report_path, count, n=10)

    latest_ts = get_latest_message_time()
    if latest_ts:
        latest_text = datetime.fromtimestamp(latest_ts).strftime('%Y-%m-%d %H:%M:%S')
        print(f'数据库最新消息时间: {latest_text}')
        if datetime.fromtimestamp(latest_ts).date() < datetime.now().date():
            print('警告: 解密库最新消息不是今天，微信可能尚未写入或WAL未能完整合并')

    print('=' * 50)
    print('全部完成!')
    print(f'报告文件: {os.path.abspath(report_path)}')
    print(f'导出消息: {count} 条')
    print('=' * 50)


if __name__ == '__main__':
    main()
