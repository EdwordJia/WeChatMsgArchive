#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
微信群聊天记录提取脚本
目标群名: 软件定制开发、无
微信版本: v3 (3.9.x)
"""

import os
import sys
import json
import csv
import ctypes
import psutil
import pythoncom
from datetime import datetime
from multiprocessing import freeze_support

# 将项目根目录加入路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

TARGET_GROUP_NAME = '软件定制开发、无'
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')


def get_wx_info_bypass_version():
    """
    绕过版本号限制，直接获取 wxid / wx_dir / key。
    nick_name / account_name 留空（不影响解密）。
    """
    from wxManager.decrypt.wx_info_v3 import (
        get_info_wxid, get_wx_dir, get_key, get_exe_bit
    )
    from wxManager.decrypt.common import WeChatInfo, get_version

    results = []
    for process in psutil.process_iter(['name', 'exe', 'pid']):
        if process.name() != 'WeChat.exe':
            continue

        wechat_info = WeChatInfo()
        wechat_info.pid = process.pid

        try:
            pythoncom.CoInitialize()
            wechat_info.version = get_version(process.pid)
        except Exception as e:
            print(f"获取版本失败: {e}")
            wechat_info.version = '3.9.12.57'

        # 找 WeChatWin.dll 基址
        wechat_base_address = 0
        try:
            for module in process.memory_maps(grouped=False):
                if module.path and 'WeChatWin.dll' in module.path:
                    wechat_base_address = int(module.addr, 16)
                    break
        except Exception as e:
            print(f"获取内存模块失败: {e}")

        if wechat_base_address == 0:
            print("找不到 WeChatWin.dll，请确认微信已登录")
            continue

        Handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, process.pid)

        # wxid 和 wx_dir 不需要 bias_list
        wechat_info.wxid = get_info_wxid(Handle)
        wechat_info.wx_dir = get_wx_dir(wechat_info.wxid) if wechat_info.wxid != 'None' else ''

        if not wechat_info.wx_dir:
            print(f"获取微信数据目录失败，wxid={wechat_info.wxid}")
            continue

        # key 同样不需要 bias_list
        addrLen = get_exe_bit(process.exe()) // 8
        wechat_info.key = get_key(wechat_info.wx_dir, addrLen)

        if not wechat_info.key or wechat_info.key == 'None':
            wechat_info.errcode = 404
            wechat_info.errmsg = '获取 key 失败，请重启微信后重试。'
        else:
            wechat_info.errcode = 200
            wechat_info.errmsg = 'ok'

        results.append(wechat_info)

    return results


def step1_get_wx_info():
    """第一步：从内存获取微信账号信息和数据库密钥"""
    print("=" * 60)
    print("第一步：获取微信账号信息和数据库密钥")
    print("=" * 60)
    print("请确保微信已登录并运行中（WeChat.exe）...")
    print()

    results = get_wx_info_bypass_version()

    ok_list = [r for r in results if r.errcode == 200]
    if not ok_list:
        for r in results:
            print(f"错误: {r.errmsg} (版本: {r.version})")
        if not results:
            print("未找到 WeChat.exe 进程，请先登录微信")
        return None

    wx_info = ok_list[0]
    print(f"获取成功!")
    print(f"   wxid    : {wx_info.wxid}")
    print(f"   版本    : {wx_info.version}")
    print(f"   数据目录: {wx_info.wx_dir}")
    print(f"   密钥    : {wx_info.key[:16] if wx_info.key else ''}...")
    return wx_info


def step2_decrypt_db(wx_info):
    """第二步：批量解密数据库文件"""
    print()
    print("=" * 60)
    print("第二步：解密微信数据库")
    print("=" * 60)

    from wxManager.decrypt.decrypt_v3 import decrypt_db_files

    wx_dir = wx_info.wx_dir
    key = wx_info.key
    src_dir = os.path.join(wx_dir, 'Msg')
    dst_dir = os.path.join(OUTPUT_DIR, 'decrypted_db')

    if not os.path.exists(src_dir):
        print(f"找不到消息目录: {src_dir}")
        return None

    db_files = []
    for root, dirs, files in os.walk(src_dir):
        for f in files:
            if f.endswith('.db'):
                db_files.append(os.path.join(root, f))
    print(f"共找到 {len(db_files)} 个数据库文件")

    os.makedirs(dst_dir, exist_ok=True)
    print(f"开始解密，输出到: {dst_dir}")
    print("使用多进程，请稍候...")

    decrypt_db_files(key, src_dir, dst_dir)

    decrypted = []
    for root, dirs, files in os.walk(dst_dir):
        for f in files:
            if f.endswith('.db'):
                decrypted.append(f)
    print(f"解密完成，共 {len(decrypted)} 个文件")

    # 保存 info.json 供 DataBaseV3.init_database 读取
    info_path = os.path.join(dst_dir, 'info.json')
    if not os.path.exists(info_path):
        info = {
            'wxid': wx_info.wxid,
            'name': wx_info.nick_name or wx_info.wxid,
            'account': wx_info.account_name or '',
            'mobile': wx_info.phone or '',
        }
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        print(f"已生成 info.json")

    return dst_dir


def step3_find_group_and_export(wx_info, decrypted_dir):
    """第三步：定位目标群并导出聊天记录"""
    print()
    print("=" * 60)
    print(f"第三步：查找群 [{TARGET_GROUP_NAME}] 并导出")
    print("=" * 60)

    from wxManager.manager_v3 import DataBaseV3

    db = DataBaseV3()
    print("正在初始化数据库连接...")
    db.init_database(decrypted_dir)

    print("正在获取会话列表...")
    sessions = db.get_session()
    print(f"共找到 {len(sessions)} 个会话")

    # 查找目标群
    target_username = None
    for s in sessions:
        try:
            remark = getattr(s, 'remark', '') or ''
            nickname = getattr(s, 'nickname', '') or ''
            username = getattr(s, 'username', '') or ''
            display_name = remark if remark else nickname
            if TARGET_GROUP_NAME in display_name:
                target_username = username
                print(f"\n找到目标群!")
                print(f"   群名  : {display_name}")
                print(f"   群ID  : {username}")
                break
        except Exception:
            continue

    if not target_username:
        print(f"\n未找到群 [{TARGET_GROUP_NAME}]，正在列出所有群聊：")
        print("-" * 50)
        for s in sessions:
            try:
                remark = getattr(s, 'remark', '') or ''
                nickname = getattr(s, 'nickname', '') or ''
                username = getattr(s, 'username', '') or ''
                display_name = remark if remark else nickname
                if '@chatroom' in username:
                    print(f"  {display_name} | {username}")
            except Exception:
                pass
        print("-" * 50)
        print("\n请修改脚本中 TARGET_GROUP_NAME 变量后重试。")
        db.close()
        return

    # 提取消息
    print(f"\n正在提取聊天记录（可能需要数分钟）...")
    try:
        messages = db.get_messages(target_username)
        print(f"共提取到 {len(messages)} 条消息")
    except Exception as e:
        print(f"提取消息失败: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return

    db.close()

    if not messages:
        print("未找到任何消息")
        return

    # 导出
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_name = TARGET_GROUP_NAME.replace('、', '_').replace(' ', '_')
    csv_path = os.path.join(OUTPUT_DIR, f'group_{safe_name}.csv')
    txt_path = os.path.join(OUTPUT_DIR, f'group_{safe_name}.txt')

    print(f"\n正在导出...")

    sender_count = {}
    date_count = {}

    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as fc:
        writer = csv.writer(fc)
        writer.writerow(['时间', '发送者wxid', '发送者昵称', '消息类型', '内容'])

        with open(txt_path, 'w', encoding='utf-8') as ft:
            ft.write(f"群名: {TARGET_GROUP_NAME}\n")
            ft.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            ft.write(f"消息总数: {len(messages)}\n")
            ft.write("=" * 60 + "\n\n")

            for msg in messages:
                try:
                    ts = getattr(msg, 'create_time', None) or getattr(msg, 'time', None) or 0
                    if isinstance(ts, (int, float)) and ts > 0:
                        ts_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                        date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                    else:
                        ts_str = str(ts)
                        date_str = 'unknown'

                    sender = getattr(msg, 'sender', '') or getattr(msg, 'talker', '') or ''
                    sender_name = getattr(msg, 'sender_name', '') or getattr(msg, 'display_name', '') or sender
                    msg_type = str(getattr(msg, 'type', '') or getattr(msg, 'msg_type', '') or '')
                    content = getattr(msg, 'content', '') or getattr(msg, 'message', '') or ''
                    if not isinstance(content, str):
                        content = str(content)

                    writer.writerow([ts_str, sender, sender_name, msg_type, content])
                    ft.write(f"[{ts_str}] {sender_name}({sender})\n{content}\n\n")

                    k = sender_name or sender
                    sender_count[k] = sender_count.get(k, 0) + 1
                    date_count[date_str] = date_count.get(date_str, 0) + 1
                except Exception:
                    pass

    print(f"CSV 已导出: {csv_path}")
    print(f"TXT 已导出: {txt_path}")

    # 统计报告
    stats_path = os.path.join(OUTPUT_DIR, f'stats_{safe_name}.txt')
    with open(stats_path, 'w', encoding='utf-8') as f:
        f.write(f"=== 群[{TARGET_GROUP_NAME}]聊天记录统计报告 ===\n\n")
        f.write(f"总消息数: {len(messages)}\n")
        f.write(f"参与人数: {len(sender_count)}\n\n")
        f.write("【按日期统计】\n")
        for d in sorted(date_count.keys()):
            f.write(f"  {d}: {date_count[d]} 条\n")
        f.write("\n【发言排行 Top 20】\n")
        for i, (name, count) in enumerate(sorted(sender_count.items(), key=lambda x: -x[1])[:20], 1):
            f.write(f"  {i:2d}. {name}: {count} 条\n")

    print(f"统计报告: {stats_path}")

    # 控制台摘要
    print("\n" + "=" * 60)
    print("统计摘要")
    print("=" * 60)
    print(f"  总消息数: {len(messages)}")
    print(f"  参与人数: {len(sender_count)}")
    if date_count:
        dates = sorted(k for k in date_count.keys() if k != 'unknown')
        if dates:
            print(f"  时间跨度: {dates[0]} ~ {dates[-1]}")
    print(f"\n  发言 Top 5:")
    for name, count in sorted(sender_count.items(), key=lambda x: -x[1])[:5]:
        print(f"    {name}: {count} 条")


def main():
    freeze_support()
    print("微信群聊天记录提取工具 (v3)")
    print(f"目标群: {TARGET_GROUP_NAME}")
    print(f"输出目录: {OUTPUT_DIR}")
    print()

    wx_info = step1_get_wx_info()
    if not wx_info:
        print("\n获取微信信息失败，请确保微信已登录后重试。")
        sys.exit(1)

    decrypted_dir = step2_decrypt_db(wx_info)
    if not decrypted_dir:
        print("\n数据库解密失败。")
        sys.exit(1)

    step3_find_group_and_export(wx_info, decrypted_dir)

    print(f"\n全部完成！输出目录: {OUTPUT_DIR}")


if __name__ == '__main__':
    main()
