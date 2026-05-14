# 微信消息同步问题修复指南

## 快速修复（推荐）

### 方法1：使用修复脚本（最简单）

1. **编辑修复脚本，设置密钥**

```bash
# 编辑 fix_wechat_sync.py
# 将 KEY = 'YOUR_KEY_HERE' 替换为实际的解密密钥
```

2. **运行修复脚本**

```bash
./venv/Scripts/python fix_wechat_sync.py
```

脚本会自动：
- 检查微信是否运行
- 检查WAL文件状态
- 询问是否关闭微信
- 解密数据库（包括WAL文件）
- 同步到索引数据库
- 验证结果
- 询问是否重启微信

### 方法2：手动操作

1. **关闭微信**

```bash
taskkill /F /IM WeChat.exe /T
```

2. **等待5秒**（让SQLite执行checkpoint）

3. **重新解密**

```bash
./venv/Scripts/python -c "
from wxManager.decrypt import decrypt_v3
key = 'YOUR_KEY_HERE'
src_dir = 'E:/腾讯电脑管家文件搬家/微信聊天文件搬家/Users/WeChat Files/wxid_ucag2pjrmhm822/Msg'
output_dir = 'output/decrypted_db'
decrypt_v3.decrypt_db_files(key, src_dir=src_dir, dest_dir=output_dir)
"
```

4. **重新同步**

使用MCP：
```python
mcp__wechat-data__sync_messages(incremental=false)
```

或直接运行：
```bash
./venv/Scripts/python wechat_index_db.py full
```

5. **验证结果**

```bash
./venv/Scripts/python -c "
import sqlite3
from datetime import datetime

# 检查索引数据库
conn = sqlite3.connect('output/wechat_index.db')
cur = conn.cursor()

cur.execute('SELECT MAX(create_time) FROM messages')
latest = cur.fetchone()[0]
print(f'最新消息时间: {datetime.fromtimestamp(latest).strftime(\"%Y-%m-%d %H:%M:%S\")}')

cur.execute('SELECT COUNT(*) FROM messages WHERE content LIKE \"%滚动条%\"')
count = cur.fetchone()[0]
print(f'包含\"滚动条\"的消息数: {count}')

conn.close()
"
```

## 高级用法

### 使用增强版解密（支持WAL文件）

```python
from wxManager.decrypt.decrypt_v3_enhanced import decrypt_db_files_enhanced

key = 'YOUR_KEY_HERE'
src_dir = 'E:/腾讯电脑管家文件搬家/微信聊天文件搬家/Users/WeChat Files/wxid_ucag2pjrmhm822/Msg'
dest_dir = 'output/decrypted_db'

# 解密时包含WAL文件
result = decrypt_db_files_enhanced(key, src_dir, dest_dir, include_wal=True)

print(f'解密完成:')
print(f'  总文件数: {result["total_files"]}')
print(f'  成功: {result["success_count"]}')
print(f'  WAL文件: {result["wal_files"]}')
```

### 检查WAL文件状态

```bash
./venv/Scripts/python -c "
import os
from pathlib import Path

msg_dir = Path('E:/腾讯电脑管家文件搬家/微信聊天文件搬家/Users/WeChat Files/wxid_ucag2pjrmhm822/Msg/Multi')
wal_files = list(msg_dir.glob('*.db-wal'))

print(f'找到 {len(wal_files)} 个WAL文件:')
for wal_file in wal_files:
    size = wal_file.stat().st_size
    if size > 0:
        print(f'  {wal_file.name}: {size/1024/1024:.2f} MB')
"
```

## 自动化方案

### 定时任务（Windows任务计划程序）

1. **创建批处理文件** `auto_sync_wechat.bat`

```batch
@echo off
cd /d D:\develoment_home\project_home\WeChatMsgArchive
.\venv\Scripts\python.exe fix_wechat_sync.py
```

2. **配置任务计划程序**

- 打开"任务计划程序"
- 创建基本任务
- 触发器：每天凌晨3点
- 操作：启动程序 `auto_sync_wechat.bat`

### 使用Python定时任务

```python
import schedule
import time
from fix_wechat_sync import main

# 每天凌晨3点执行
schedule.every().day.at("03:00").do(main)

# 或每隔6小时执行
schedule.every(6).hours.do(main)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## 常见问题

### Q1: 为什么搜索不到最新消息？

**A**: 微信使用SQLite的WAL模式，最新消息可能还在WAL文件中，没有写入主数据库。需要关闭微信后重新解密。

### Q2: 解密时提示"file is not a database"？

**A**: 这是正常的，说明源数据库是加密的。解密后的数据库可以正常读取。

### Q3: 同步显示成功，但搜索不到？

**A**: 检查以下几点：
1. 索引数据库的最新消息时间是否正确
2. 是否在正确的数据库中搜索
3. 关键词是否正确（注意大小写、空格）

### Q4: 如何获取解密密钥？

**A**: 使用 `wechat-decrypt-db` 技能从运行中的微信进程提取密钥：

```bash
# 在Claude Code中运行
/wechat-decrypt-db
```

### Q5: 可以在微信运行时解密吗？

**A**: 可以，但只能获取到已写入主数据库的消息，无法获取WAL文件中的最新消息。建议关闭微信后解密。

### Q6: WAL文件是什么？

**A**: WAL（Write-Ahead Logging）是SQLite的一种日志模式：
- 新的写入操作先写入WAL文件
- 定期执行checkpoint，将WAL内容合并到主数据库
- 关闭数据库时会自动执行checkpoint

### Q7: 如何强制执行checkpoint？

**A**: 关闭微信即可，SQLite会自动执行checkpoint。或使用SQLite命令：

```python
import sqlite3
conn = sqlite3.connect('path/to/database.db')
conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
conn.close()
```

## 技术细节

### SQLite WAL模式

```
数据库文件结构：
├── MSG1.db          # 主数据库文件
├── MSG1.db-wal      # WAL文件（Write-Ahead Log）
└── MSG1.db-shm      # 共享内存文件（Shared Memory）

写入流程：
1. 新消息 → 写入WAL文件
2. 定期checkpoint → WAL内容合并到主数据库
3. 关闭数据库 → 自动执行checkpoint
```

### 解密流程

```
原始流程（只解密主数据库）：
源数据库（加密）→ 解密 → 目标数据库（明文）
MSG1.db → decrypt → output/decrypted_db/Multi/MSG1.db

增强流程（同时解密WAL）：
MSG1.db → decrypt → output/decrypted_db/Multi/MSG1.db
MSG1.db-wal → decrypt → output/decrypted_db/Multi/MSG1.db-wal
MSG1.db-shm → copy → output/decrypted_db/Multi/MSG1.db-shm
```

### 同步流程

```
1. 遍历所有MSG*.db文件
2. 查询 CreateTime > last_sync_time 的消息
3. 插入到索引数据库
4. 更新 last_sync_time
```

## 相关文件

- **诊断报告**: `WECHAT_MESSAGE_SYNC_DIAGNOSIS.md`
- **修复脚本**: `fix_wechat_sync.py`
- **增强解密**: `wxManager/decrypt/decrypt_v3_enhanced.py`
- **原始解密**: `wxManager/decrypt/decrypt_v3.py`
- **同步代码**: `wechat_index_db.py`
- **MCP数据库层**: `mcp_servers/wechat_data/database.py`

## 联系支持

如果问题仍未解决，请提供以下信息：

1. 微信版本
2. 最新消息时间（从微信客户端查看）
3. 解密数据库的最新消息时间
4. 索引数据库的最新消息时间
5. WAL文件大小
6. 错误日志（如有）
