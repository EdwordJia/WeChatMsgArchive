#!/usr/bin/env python3
"""分析微信群聊前，先确保导出文件是最新的。"""
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(REPO, 'output')
SYNC_SCRIPT = os.path.join(REPO, '.claude', 'sync_all_groups.py')
FRESHNESS_SECONDS = 300  # 5 分钟内认为仍新鲜

sys.path.insert(0, os.path.join(REPO, '.claude'))
from sync_all_groups import GROUPS


def is_wechat_running():
    """检查微信主进程是否正在运行。"""
    for image in ('WeChat.exe', 'Weixin.exe'):
        try:
            result = subprocess.run(
                ['tasklist', '/FI', f'IMAGENAME eq {image}'],
                capture_output=True, text=True, check=False
            )
            if image in result.stdout:
                return True
        except Exception:
            pass
    return False


def report_export_time(report_path):
    """从报告头部解析导出时间。"""
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= 10:
                    break
                m = re.search(
                    r'导出时间:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',
                    line
                )
                if m:
                    return datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S')
    except Exception:
        pass
    return None


def is_stale(group_id):
    """判断某个群的导出文件是否需要重新同步。"""
    report_path = os.path.join(OUTPUT_DIR, f'group_{group_id}_latest.txt')
    if not os.path.exists(report_path):
        return True
    export_time = report_export_time(report_path)
    if not export_time:
        return True
    return (datetime.now() - export_time).total_seconds() > FRESHNESS_SECONDS


def ensure_sync(groups=None):
    """确保指定群的导出文件为最新；未指定则检查全部活跃群。"""
    if groups is None:
        groups = GROUPS

    stale_groups = [g for g in groups if is_stale(g)]
    if not stale_groups:
        print('群聊导出文件均在 5 分钟内，无需重新同步。')
        return True

    if not is_wechat_running():
        print('警告：微信未运行，无法重新解密同步，将使用现有导出文件。')
        print('如需最新消息，请先启动微信后再执行分析。')
        return False

    print(f'以下群聊导出文件较旧，开始同步: {stale_groups}')
    sys.stdout.flush()
    result = subprocess.run(
        [sys.executable, SYNC_SCRIPT],
        cwd=REPO,
        check=False
    )
    return result.returncode == 0


if __name__ == '__main__':
    ensure_sync(sys.argv[1:] or None)
