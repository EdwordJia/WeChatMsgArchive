"""
强制同步微信最新消息
通过SQLite checkpoint强制合并WAL文件
"""
import sqlite3
import os
import sys
from pathlib import Path
from datetime import datetime

# 微信数据目录
WX_DIR = r'E:\腾讯电脑管家文件搬家\微信聊天文件搬家\Users\WeChat Files\wxid_ucag2pjrmhm822\Msg'
OUTPUT_DIR = Path('output/decrypted_db')

def force_wal_checkpoint():
    """强制执行WAL checkpoint""
    print('正在强制合并WAL文件到主数据库...')
    
    msg_dir = Path(WX_DIR)
    if not msg_dir.exists():
        print(f'错误: 目录不存在 {msg_dir}')
        return False
    
    # 查找所有.db文件
    db_files = list(msg_dir.glob('**/*.db'))
    print(f'找到 {len(db_files)} 个数据库文件')
    
    checkpoint_count = 0
    for db_file in db_files:
        wal_file = db_file.with_suffix('.db-wal')
        if wal_file.exists():
            wal_size = wal_file.stat().st_size
         if wal_size > 0:
                print(f'\n处理: {db_file.name}')
                print(f'  WAL文件大小: {wal_size / 1024:.2f} KB')
                
                try:
         # 连接数据库并执行checkpoint
              conn = sqlite3.connect(str(db_file))
                  conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                  conn.close()
                    
                    # 检查WAL文件是否被清空
                  new_wal_size = wal_file.stat().st_size if wal_file.exists() else 0
              print(f'  Checkpoint后WAL大小: {new_wal_size / 1024:.2f} KB')
              checkpoint_count += 1
           except Exception as e:
            print(f'  错误: {e}')
    
    print(f'\n成功处理 {checkpoint_count} 个WAL文件')
    return checkpoint_count > 0

def decrypt_and_sync():
    """解密并同步""
    print('\n开始解密数据库...')
    
    # 使用现有的解密代码
    sys.path.insert(0, str(Path(__file__).parent))
    from wxManager.decrypt import decrypt_v3
    
    key = '915c197a38d74dae8e4f1fcb6c1b173b9f127075f7e8c6d3a2b4e5f6a7b8c9d0'
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    decrypt_v3.decrypt_db_files(key, src_dir=WX_DIR, dest_dir=str(OUTPUT_DIR))
  
    print('\n解密完成！')
    
    # 统计数据库
    db_count = sum(1 for f in OUTPUT_DIR.rglob('*.db'))
    print(f'解密了 {db_count} 个数据库文件')
    
    return True

def search_latest_messages():
    """搜索最新消息"""
    print('\n搜索最新消息...')
  
    msg_db = OUTPUT_DIR / 'Multi' / 'MSG1.db'
    if not msg_db.exists():
        print(f'错误: 数据库不存在 {msg_db}')
        return
    
    conn = sqlite3.connect(str(msg_db))
    cur = conn.cursor()
    
    # 查询最新消息时间
  cur.execute('SELECT datetime(MAX(CreateTime), "unixepoch", "localtime") FROM MSG')
    latest_time = cur.fetchone()[0]
    print(f'数据库最新消息时间: {latest_time}')
    
    # 查询目标群的最新消息
    target_group = '50241909905@chatroom'
    cur.execute('''
        SELECT datetime(CreateTime, "unixepoch", "localtime"),
               substr(StrContent, 1, 100),
     IsSender
        FROM MSG
        WHERE StrTalker=?
        ORDER BY CreateTime DESC
        LIMIT 10
    ''', (target_group,))
    
    print(f'\n群聊 {target_group} 最新10条消息:')
    for row in cur.fetchall():
        print(f'  [{row[0]}] {"我" if row[2] else "对方"}: {row[1]}')
    
    # 搜索关键词
    keywords = ['滚动条', '图框', '太小', '解密']
    for keyword in keywords:
        cur.execute('''
            SELECT COUNT(*) FROM MSG
            WHERE StrContent LIKE ?
            AND CreateTime > strftime('%s', 'now', '-7 days')
        ''', (f'%{keyword}%',))
        count = cur.fetchone()[0]
        if count > 0:
            print(f'\n找到包含"{keyword}"的消息: {count}条')
            cur.execute('''
              SELECT datetime(CreateTime, "unixepoch", "localtime"),
                  substr(StrContent, 1, 150),
                 StrTalker
                FROM MSG
             WHERE StrContent LIKE ?
           AND CreateTime > strftime('%s', 'now', '-7 days')
                ORDER BY CreateTime DESC
              LIMIT 5
            ''', (f'%{keyword}%',))
       for row in cur.fetchall():
                print(f'  [{row[0]}] {row[2]}: {row[1]}')
    
    conn.close()

if __name__ == '__main__':
    print('='*60)
    print('强制同步微信最新消息')
    print('='*60)
    print(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print()
    
    # 步骤1: 强制checkpoint
    if force_wal_checkpoint():
        print('\nWAL文件已合并到主数据库')
    else:
        print('\n没有需要合并的WAL文件')
    
    # 步骤2: 解密
    if decrypt_and_sync():
        # 步骤3: 搜索
        search_latest_messages()
    
    print('\n'+'='*60)
  print('完成！')
    print('='*60)
