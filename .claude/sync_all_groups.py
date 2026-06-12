#!/usr/bin/env python3
"""一次性同步多个客户群消息：先解密一次，再批量导出"""
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

# 导入 wechat_sync 的函数
sys.path.insert(0, os.getcwd())
from wechat_sync import step1_decrypt, step2_export_group

GROUPS = [
    '45460642803@chatroom',   # 婚恋匹配
    '49384016077@chatroom',   # Nova通讯软件
    '49584724187@chatroom',   # 知识付费应用
    '47302225829@chatroom',   # 英语单词小程序
    '47390535442@chatroom',   # 海钓小程序
    '49734720477@chatroom',   # 4.21ai训练管理
]

if __name__ == '__main__':
    print('=' * 60)
    print('批量同步客户群消息')
    print('=' * 60)

    # Step 1: 只解密一次
    wxid, wx_dir = step1_decrypt()

    # Step 2: 循环导出每个群
    results = []
    for group_id in GROUPS:
        try:
            report_path, count = step2_export_group(group_id, wx_dir)
            results.append((group_id, report_path, count))
        except Exception as e:
            print(f'  导出失败 {group_id}: {e}')
            results.append((group_id, None, 0))

    print('\n' + '=' * 60)
    print('批量同步完成')
    print('=' * 60)
    for group_id, report_path, count in results:
        status = f'{count} 条' if report_path else '失败'
        print(f'  {group_id}: {status}')
