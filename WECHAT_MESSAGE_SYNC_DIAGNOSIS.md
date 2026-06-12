# 微信消息搜索问题诊断报告

## 问题描述

用户反馈收到了微信消息（包含"滚动条"关键词），但通过以下流程无法找到：
1. 解密微信数据库
2. 同步到索引数据库（显示同步了163657条新消息）
3. 搜索关键词"滚动条"（返回0条结果）
4. 直接查询SQLite的MSG*.db文件（返回0条结果）

## 根因分析

### 1. SQLite WAL（Write-Ahead Logging）机制

微信使用SQLite的WAL模式存储消息：
- 新的写入操作先写入WAL文件（.db-wal）
- 只有在checkpoint操作时，WAL内容才会合并到主数据库文件（.db）
- 当微信正在运行时，最新消息可能还在WAL文件中

### 2. 实际情况验证

```bash
# 源数据库文件状态
MSG1.db              210M  May  9 23:26  # 主数据库文件
MSG1.db-wal          7.9M  May 10 01:16  # WAL文件（持续更新中）
```

**关键发现**：
- MSG1.db主文件最后更新：2026-05-09 23:26:05
- MSG1.db-wal文件最后更新：2026-05-10 01:16（比主文件晚约2小时）
- 微信进程正在运行（14个WeChat相关进程）

### 3. 解密流程的问题

当前解密代码（`wxManager/decrypt/decrypt_v3.py`）：
```python
def decrypt_db_files(key, src_dir: str, dest_dir: str):
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith(".db"):  # 只处理.db文件
                decrypt_db_file_v3(key, src_file_path, dest_file_path)
```

**问题**：
- ✅ 解密了MSG1.db主文件（截止到5月9日23:26的消息）
- ❌ 没有处理MSG1.db-wal文件（5月9日23:26之后的消息）
- ❌ 没有处理MSG1.db-shm文件（共享内存文件）

### 4. 数据验证

```python
# 解密后的数据库
解密数据库最新消息时间: 2026-05-09 23:26:05

# 索引数据库
索引数据库最新消息时间: 2026-05-09 23:26:05
总消息数: 934539
最近7天消息数: 52836
```

**结论**：解密和同步流程都正常工作，但只能获取到已经写入主数据库文件的消息，无法获取WAL文件中的最新消息。

## 解决方案

### 方案1：关闭微信后解密（推荐）

**原理**：关闭微信后，SQLite会自动执行checkpoint，将WAL文件内容合并到主数据库。

**操作步骤**：
```bash
# 1. 关闭微信
taskkill /F /IM WeChat.exe /T

# 2. 等待几秒让SQLite完成checkpoint

# 3. 重新解密
./venv/Scripts/python -c "
from wxManager.decrypt import decrypt_v3
key = 'YOUR_KEY'
src_dir = 'E:/腾讯电脑管家文件搬家/微信聊天文件搬家/Users/WeChat Files/wxid_ucag2pjrmhm822/Msg'
output_dir = 'output/decrypted_db'
decrypt_v3.decrypt_db_files(key, src_dir=src_dir, dest_dir=output_dir)
"

# 4. 重新同步
# 使用 mcp__wechat-data__sync_messages(incremental=false)
```

**优点**：
- 简单可靠
- 不需要修改代码
- 保证数据完整性

**缺点**：
- 需要关闭微信（影响正常使用）
- 无法实时获取最新消息

### 方案2：同时解密WAL文件（需要开发）

**原理**：WAL文件也是加密的，需要单独解密。

**实现思路**：
```python
def decrypt_db_files_with_wal(key, src_dir: str, dest_dir: str):
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            # 处理.db文件
            if file.endswith(".db"):
                src_file_path = os.path.join(root, file)
                dest_file_path = os.path.join(dest_sub_dir, file)
                decrypt_db_file_v3(key, src_file_path, dest_file_path)

                # 处理对应的.db-wal文件
                wal_src = src_file_path + '-wal'
                if os.path.exists(wal_src):
                    wal_dest = dest_file_path + '-wal'
                    decrypt_db_file_v3(key, wal_src, wal_dest)

                # 复制.db-shm文件（共享内存文件，可能不需要解密）
                shm_src = src_file_path + '-shm'
                if os.path.exists(shm_src):
                    shm_dest = dest_file_path + '-shm'
                    shutil.copy2(shm_src, shm_dest)
```

**优点**：
- 可以在微信运行时获取最新消息
- 实时性更好

**缺点**：
- 需要修改解密代码
- WAL文件格式可能与主数据库不同，需要验证解密方法
- 可能存在文件锁定问题

### 方案3：定期自动关闭微信并同步（自动化）

**原理**：通过定时任务，在特定时间（如凌晨）自动关闭微信、解密、同步。

**实现**：
```python
# auto_sync_wechat.py
import subprocess
import time
from wxManager.decrypt import decrypt_v3

def auto_sync():
    # 1. 关闭微信
    subprocess.run(['taskkill', '/F', '/IM', 'WeChat.exe', '/T'])
    time.sleep(5)  # 等待checkpoint

    # 2. 解密
    key = 'YOUR_KEY'
    src_dir = 'E:/腾讯电脑管家文件搬家/微信聊天文件搬家/Users/WeChat Files/wxid_ucag2pjrmhm822/Msg'
    output_dir = 'output/decrypted_db'
    decrypt_v3.decrypt_db_files(key, src_dir=src_dir, dest_dir=output_dir)

    # 3. 同步（通过MCP或直接调用）
    from wechat_index_db import incremental_sync
    incremental_sync()

    # 4. 重启微信
    subprocess.Popen(['C:/Program Files/Tencent/WeChat/WeChat.exe'])

if __name__ == '__main__':
    auto_sync()
```

**配置定时任务**（Windows任务计划程序）：
- 每天凌晨3点执行
- 或每隔6小时执行一次

## 验证方法

### 1. 验证WAL文件是否包含最新消息

```bash
# 关闭微信前，检查WAL文件大小
ls -lh "E:/腾讯电脑管家文件搬家/微信聊天文件搬家/Users/WeChat Files/wxid_ucag2pjrmhm822/Msg/Multi/MSG1.db-wal"

# 关闭微信
taskkill /F /IM WeChat.exe /T

# 等待5秒

# 再次检查WAL文件（应该变小或消失）
ls -lh "E:/腾讯电脑管家文件搬家/微信聊天文件搬家/Users/WeChat Files/wxid_ucag2pjrmhm822/Msg/Multi/MSG1.db-wal"

# 检查主数据库文件的修改时间（应该更新）
ls -lh "E:/腾讯电脑管家文件搬家/微信聊天文件搬家/Users/WeChat Files/wxid_ucag2pjrmhm822/Msg/Multi/MSG1.db"
```

### 2. 验证解密后的消息时间

```python
import sqlite3
from datetime import datetime

db_path = 'output/decrypted_db/Multi/MSG1.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute('SELECT MAX(CreateTime) FROM MSG')
latest = cur.fetchone()[0]
print(f'最新消息时间: {datetime.fromtimestamp(latest).strftime("%Y-%m-%d %H:%M:%S")}')

conn.close()
```

### 3. 验证搜索功能

```python
# 使用MCP搜索
mcp__wechat-data__search_messages(keyword="滚动条", days=7)

# 或直接查询
import sqlite3
conn = sqlite3.connect('output/wechat_index.db')
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM messages WHERE content LIKE '%滚动条%'")
print(f'找到消息数: {cur.fetchone()[0]}')
conn.close()
```

## 代码层面的改进建议

### 1. 在解密前检查微信是否运行

```python
def is_wechat_running():
    """检查微信是否正在运行"""
    import subprocess
    result = subprocess.run(['tasklist'], capture_output=True, text=True)
    return 'WeChat.exe' in result.stdout

def decrypt_with_check(key, src_dir, dest_dir):
    if is_wechat_running():
        print('警告：微信正在运行，可能无法获取最新消息')
        print('建议：关闭微信后再执行解密')
        response = input('是否继续？(y/n): ')
        if response.lower() != 'y':
            return

    decrypt_db_files(key, src_dir, dest_dir)
```

### 2. 在同步时记录WAL文件状态

```python
def sync_with_wal_check():
    """同步时检查WAL文件状态"""
    msg_dir = Path('E:/腾讯电脑管家文件搬家/微信聊天文件搬家/Users/WeChat Files/wxid_ucag2pjrmhm822/Msg/Multi')

    for db_file in msg_dir.glob('MSG*.db'):
        wal_file = db_file.with_suffix('.db-wal')
        if wal_file.exists():
            wal_size = wal_file.stat().st_size
            if wal_size > 1024 * 1024:  # 大于1MB
                print(f'警告：{db_file.name} 的WAL文件较大 ({wal_size/1024/1024:.2f}MB)')
                print('可能有大量未同步的消息')
```

### 3. 提供强制checkpoint的功能

```python
def force_checkpoint(db_path):
    """强制执行SQLite checkpoint"""
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    conn.close()
```

## 总结

**问题根因**：微信使用SQLite的WAL模式，最新消息在WAL文件中，而解密流程只处理主数据库文件。

**推荐方案**：关闭微信后解密（方案1），简单可靠。

**长期方案**：实现方案3（定期自动同步），在不影响使用的情况下保持数据更新。

**立即操作**：
1. 关闭微信
2. 重新解密数据库
3. 重新同步到索引数据库
4. 验证搜索功能

## 附录：相关文件路径

- 解密代码：`wxManager/decrypt/decrypt_v3.py`
- 同步代码：`wechat_index_db.py`
- MCP数据库层：`mcp_servers/wechat_data/database.py`
- 源数据库：`E:/腾讯电脑管家文件搬家/微信聊天文件搬家/Users/WeChat Files/wxid_ucag2pjrmhm822/Msg/Multi/`
- 解密输出：`output/decrypted_db/Multi/`
- 索引数据库：`output/wechat_index.db`
