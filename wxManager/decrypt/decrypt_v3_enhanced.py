"""
改进的微信数据库解密模块
支持同时解密WAL文件，以获取最新消息
"""
import os
import shutil
from pathlib import Path
from typing import Tuple, List
from concurrent.futures import ProcessPoolExecutor

from wxManager.decrypt.decrypt_v3 import decrypt_db_file_v3


def decrypt_db_with_wal(key: str, db_path: str, out_path: str) -> Tuple[bool, str]:
    """
    解密数据库文件及其WAL文件

    Args:
        key: 64位16进制密钥
        db_path: 源数据库文件路径（.db）
        out_path: 输出数据库文件路径（.db）

    Returns:
        (成功标志, 消息)
    """
    # 1. 解密主数据库文件
    success, msg = decrypt_db_file_v3(key, db_path, out_path)
    if not success:
        return False, msg

    # 2. 处理WAL文件
    wal_src = db_path + '-wal'
    if os.path.exists(wal_src):
        wal_dest = out_path + '-wal'
        try:
            # WAL文件也是加密的，使用相同的解密方法
            wal_success, wal_msg = decrypt_db_file_v3(key, wal_src, wal_dest)
            if not wal_success:
                print(f'警告：WAL文件解密失败 {wal_src}: {wal_msg}')
                # WAL解密失败不影响主数据库
        except Exception as e:
            print(f'警告：处理WAL文件失败 {wal_src}: {e}')

    # 3. 复制SHM文件（共享内存文件，通常不需要解密）
    shm_src = db_path + '-shm'
    if os.path.exists(shm_src):
        shm_dest = out_path + '-shm'
        try:
            shutil.copy2(shm_src, shm_dest)
        except Exception as e:
            print(f'警告：复制SHM文件失败 {shm_src}: {e}')

    return True, msg


def decrypt_wrapper(args):
    """包装函数，用于多进程"""
    key, src_path, dest_path = args
    return decrypt_db_with_wal(key, src_path, dest_path)


def decrypt_db_files_enhanced(key: str, src_dir: str, dest_dir: str,
                              include_wal: bool = True,
                              max_workers: int = 16) -> dict:
    """
    增强版数据库解密函数

    Args:
        key: 64位16进制密钥
        src_dir: 源目录
        dest_dir: 目标目录
        include_wal: 是否包含WAL文件（默认True）
        max_workers: 最大并行数

    Returns:
        解密结果统计
    """
    if not os.path.exists(src_dir):
        return {
            'success': False,
            'error': f'源文件夹 {src_dir} 不存在'
        }

    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    # 收集需要解密的文件
    decrypt_tasks = []
    db_files = []

    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith(".db"):
                src_file_path = os.path.join(root, file)

                # 计算目标路径，保持子文件夹结构
                relative_path = os.path.relpath(root, src_dir)
                dest_sub_dir = os.path.join(dest_dir, relative_path)
                dest_file_path = os.path.join(dest_sub_dir, file)

                # 确保目标子文件夹存在
                if not os.path.exists(dest_sub_dir):
                    os.makedirs(dest_sub_dir)

                db_files.append(file)
                decrypt_tasks.append((key, src_file_path, dest_file_path))

    print(f'找到 {len(decrypt_tasks)} 个数据库文件')

    # 检查WAL文件
    wal_files = []
    if include_wal:
        for root, dirs, files in os.walk(src_dir):
            for file in files:
                if file.endswith(".db-wal"):
                    wal_path = os.path.join(root, file)
                    wal_size = os.path.getsize(wal_path)
                    if wal_size > 0:
                        wal_files.append((file, wal_size))

        if wal_files:
            print(f'\n检测到 {len(wal_files)} 个WAL文件:')
            for wal_file, size in wal_files:
                print(f'  {wal_file}: {size/1024/1024:.2f} MB')
            print('这些文件将被一起解密以获取最新消息\n')

    # 执行解密
    success_count = 0
    failed_files = []

    if include_wal:
        # 使用增强版解密（包含WAL）
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(decrypt_wrapper, decrypt_tasks))

        for i, (success, msg) in enumerate(results):
            if success:
                success_count += 1
            else:
                failed_files.append((db_files[i], msg))
    else:
        # 使用原版解密（不包含WAL）
        from wxManager.decrypt.decrypt_v3 import decode_wrapper
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(decode_wrapper, decrypt_tasks))

        for i, (success, msg) in enumerate(results):
            if success:
                success_count += 1
            else:
                failed_files.append((db_files[i], msg))

    # 返回结果
    result = {
        'success': success_count > 0,
        'total_files': len(decrypt_tasks),
        'success_count': success_count,
        'failed_count': len(failed_files),
        'wal_files': len(wal_files) if include_wal else 0
    }

    if failed_files:
        result['failed_files'] = failed_files

    return result


def check_wechat_status() -> dict:
    """
    检查微信运行状态和WAL文件

    Returns:
        状态信息
    """
    import subprocess

    # 检查微信进程
    try:
        result = subprocess.run(['tasklist'], capture_output=True, text=True, encoding='gbk')
        is_running = 'WeChat.exe' in result.stdout
    except Exception as e:
        is_running = None

    return {
        'wechat_running': is_running,
        'recommendation': '建议关闭微信后再解密，以获取最新消息' if is_running else '可以开始解密'
    }


if __name__ == '__main__':
    # 示例用法
    print('增强版微信数据库解密工具')
    print('='*80)

    # 检查微信状态
    status = check_wechat_status()
    print(f'\n微信运行状态: {"运行中" if status["wechat_running"] else "未运行"}')
    print(f'建议: {status["recommendation"]}')

    # 配置
    KEY = 'YOUR_KEY_HERE'
    SRC_DIR = r'E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822\Msg'
    DEST_DIR = r'output\decrypted_db'

    if KEY == 'YOUR_KEY_HERE':
        print('\n请先设置正确的解密密钥')
    else:
        print('\n开始解密...')
        result = decrypt_db_files_enhanced(KEY, SRC_DIR, DEST_DIR, include_wal=True)

        print(f'\n解密完成:')
        print(f'  总文件数: {result["total_files"]}')
        print(f'  成功: {result["success_count"]}')
        print(f'  失败: {result["failed_count"]}')
        print(f'  WAL文件: {result["wal_files"]}')

        if result.get('failed_files'):
            print('\n失败的文件:')
            for file, msg in result['failed_files']:
                print(f'  {file}: {msg}')
