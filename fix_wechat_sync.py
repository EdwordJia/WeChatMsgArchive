"""
微信消息同步修复脚本
解决WAL文件导致的最新消息无法同步问题
"""
import subprocess
import time
import os
import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))


def is_wechat_running():
    """检查微信是否正在运行"""
    try:
        result = subprocess.run(['tasklist'], capture_output=True, text=True, encoding='gbk')
        return 'WeChat.exe' in result.stdout
    except Exception as e:
        print(f'检查微信进程失败: {e}')
        return False


def close_wechat():
    """关闭微信"""
    print('正在关闭微信...')
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'WeChat.exe', '/T'],
                      capture_output=True, check=False)
        time.sleep(5)  # 等待SQLite执行checkpoint
        print('微信已关闭')
        return True
    except Exception as e:
        print(f'关闭微信失败: {e}')
        return False


def check_wal_files(msg_dir):
    """检查WAL文件状态"""
    msg_path = Path(msg_dir)
    wal_files = list(msg_path.glob('**/*.db-wal'))

    print(f'\n找到 {len(wal_files)} 个WAL文件:')
    total_size = 0
    for wal_file in wal_files:
        size = wal_file.stat().st_size
        total_size += size
        if size > 0:
            print(f'  {wal_file.name}: {size/1024/1024:.2f} MB')

    print(f'WAL文件总大小: {total_size/1024/1024:.2f} MB')
    return total_size


def decrypt_databases(key, src_dir, dest_dir):
    """解密数据库"""
    print('\n开始解密数据库...')
    try:
        from wxManager.decrypt import decrypt_v3
        decrypt_v3.decrypt_db_files(key, src_dir=src_dir, dest_dir=dest_dir)
        print('解密完成')
        return True
    except Exception as e:
        print(f'解密失败: {e}')
        import traceback
        traceback.print_exc()
        return False


def sync_to_index():
    """同步到索引数据库"""
    print('\n开始同步到索引数据库...')
    try:
        from wechat_index_db import WeChatIndexDB
        from datetime import datetime

        db = WeChatIndexDB()

        # 同步联系人
        print('1. 同步联系人...')
        db.sync_contacts()

        # 全量同步消息
        print('2. 同步消息...')
        total = db.sync_messages_incremental(since_timestamp=0)
        print(f'   同步了 {total} 条新消息')

        # 更新同步时间
        now = int(datetime.now().timestamp())
        db.set_last_sync_time(now)
        db.close()

        print('同步完成')
        return True
    except Exception as e:
        print(f'同步失败: {e}')
        import traceback
        traceback.print_exc()
        return False


def verify_sync():
    """验证同步结果"""
    print('\n验证同步结果...')
    try:
        import sqlite3

        # 检查解密数据库
        decrypted_db = PROJECT_DIR / 'output' / 'decrypted_db' / 'Multi' / 'MSG1.db'
        if decrypted_db.exists():
            conn = sqlite3.connect(decrypted_db)
            cur = conn.cursor()
            cur.execute('SELECT MAX(CreateTime) FROM MSG')
            latest = cur.fetchone()[0]
            print(f'解密数据库最新消息: {datetime.fromtimestamp(latest).strftime("%Y-%m-%d %H:%M:%S")}')
            conn.close()

        # 检查索引数据库
        index_db = PROJECT_DIR / 'output' / 'wechat_index.db'
        if index_db.exists():
            conn = sqlite3.connect(index_db)
            cur = conn.cursor()

            cur.execute('SELECT MAX(create_time) FROM messages')
            latest = cur.fetchone()[0]
            print(f'索引数据库最新消息: {datetime.fromtimestamp(latest).strftime("%Y-%m-%d %H:%M:%S")}')

            cur.execute('SELECT COUNT(*) FROM messages')
            total = cur.fetchone()[0]
            print(f'索引数据库总消息数: {total}')

            conn.close()

        return True
    except Exception as e:
        print(f'验证失败: {e}')
        return False


def start_wechat():
    """启动微信"""
    print('\n是否启动微信？(y/n): ', end='')
    response = input().strip().lower()
    if response == 'y':
        wechat_path = r'C:\Program Files\Tencent\WeChat\WeChat.exe'
        if os.path.exists(wechat_path):
            subprocess.Popen([wechat_path])
            print('微信已启动')
        else:
            print(f'未找到微信程序: {wechat_path}')


def main():
    """主流程"""
    print('='*80)
    print('微信消息同步修复脚本')
    print('='*80)

    # 配置
    KEY = 'YOUR_KEY_HERE'  # 需要替换为实际的密钥
    SRC_DIR = r'E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822\Msg'
    DEST_DIR = str(PROJECT_DIR / 'output' / 'decrypted_db')

    # 检查密钥
    if KEY == 'YOUR_KEY_HERE':
        print('\n错误：请先在脚本中设置正确的解密密钥（KEY变量）')
        print('提示：可以从之前的解密脚本中获取密钥')
        return

    # 1. 检查微信是否运行
    if is_wechat_running():
        print('\n检测到微信正在运行')

        # 检查WAL文件
        wal_size = check_wal_files(SRC_DIR)
        if wal_size > 1024 * 1024:  # 大于1MB
            print(f'\n警告：WAL文件较大，可能有大量未同步的消息')

        print('\n需要关闭微信以获取最新消息')
        print('是否关闭微信？(y/n): ', end='')
        response = input().strip().lower()

        if response != 'y':
            print('已取消操作')
            return

        if not close_wechat():
            print('关闭微信失败，请手动关闭后重试')
            return
    else:
        print('\n微信未运行')

    # 2. 再次检查WAL文件（应该已经合并到主数据库）
    print('\n检查WAL文件状态...')
    wal_size_after = check_wal_files(SRC_DIR)
    if wal_size_after < wal_size:
        print(f'WAL文件已合并到主数据库（减少了 {(wal_size - wal_size_after)/1024/1024:.2f} MB）')

    # 3. 解密数据库
    if not decrypt_databases(KEY, SRC_DIR, DEST_DIR):
        print('解密失败，请检查错误信息')
        return

    # 4. 同步到索引数据库
    if not sync_to_index():
        print('同步失败，请检查错误信息')
        return

    # 5. 验证结果
    verify_sync()

    # 6. 询问是否启动微信
    start_wechat()

    print('\n='*80)
    print('修复完成！')
    print('='*80)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n操作已取消')
    except Exception as e:
        print(f'\n发生错误: {e}')
        import traceback
        traceback.print_exc()
