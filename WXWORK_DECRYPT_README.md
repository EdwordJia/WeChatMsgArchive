# 企业微信数据库解密功能实现

## 项目概述

本项目实现了企业微信(WXWork)数据库的本地解密功能,通过读取企业微信进程内存提取数据库加密密钥,无需依赖官方API。

## 技术原理

### 1. 核心技术
- **进程内存读取**: 使用Windows API `ReadProcessMemory` 读取企业微信进程内存
- **模式扫描**: 在 `WXWorkWin.dll` 模块中扫描特定字节模式(如 "iphone\x00", "android\x00")
- **密钥提取**: 从模式附近的内存地址提取32字节加密密钥
- **密钥验证**: 使用 PBKDF2-HMAC-SHA1 算法验证密钥正确性

### 2. 加密算法
企业微信数据库使用 SQLCipher 加密,参数如下:
- **算法**: PBKDF2-HMAC-SHA1
- **密钥长度**: 32字节
- **迭代次数**: 64000
- **页大小**: 4096字节

## 实现文件

### 1. 核心模块
**文件**: `wxManager/decrypt/wx_info_wxwork.py`

主要函数:
- `get_wxwork_info()`: 主入口,返回企业微信信息和密钥
- `get_wxwork_key()`: 从内存中提取数据库加密密钥
- `get_wxwork_dir()`: 获取企业微信数据目录
- `get_info_wxid()`: 从内存中提取企业微信ID
- `verify_key()`: 验证提取的密钥是否正确

### 2. 测试脚本
**文件**: `test_wxwork_decrypt.py`

功能:
- 检测企业微信进程
- 提取并显示密钥信息
- 列出数据目录中的数据库文件
- 提供详细的诊断信息

## 与个人微信的差异

| 项目 | 个人微信 | 企业微信 |
|------|---------|---------|
| 进程名 | WeChat.exe / Weixin.exe | WXWork.exe |
| DLL模块 | WeChatWin.dll / Weixin.dll | WXWorkWin.dll |
| 数据目录 | `%USERPROFILE%\Documents\WeChat Files\` | `%APPDATA%\Tencent\WXWork\` |
| 注册表路径 | `HKCU\Software\Tencent\WeChat` | `HKCU\Software\Tencent\WXWork` |
| 用户ID字段 | wxid | wxid (可能不同格式) |

## 使用方法

### 前置条件
1. 安装依赖:
```bash
pip install pymem psutil pywin32
```

2. 确保企业微信正在运行并已登录

3. 以管理员权限运行脚本

### 运行测试
```bash
python test_wxwork_decrypt.py
```

### 集成到代码
```python
from wxManager.decrypt.wx_info_wxwork import get_wxwork_info

# 获取企业微信信息
wxwork_info = get_wxwork_info()

for info in wxwork_info:
    if info['errcode'] == 200:
        print(f"企业微信ID: {info['wxid']}")
        print(f"数据目录: {info['wx_dir']}")
        print(f"密钥: {info['key']}")
```

## 数据库解密

获取密钥后,可以使用 SQLCipher 解密数据库:

```python
import sqlite3
from pysqlcipher3 import dbapi2 as sqlcipher

def decrypt_wxwork_db(db_path, key):
    conn = sqlcipher.connect(db_path)
    conn.execute(f"PRAGMA key = \"x'{key}'\"")
    conn.execute("PRAGMA cipher_page_size = 4096")
    conn.execute("PRAGMA kdf_iter = 64000")
    conn.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA1")
    conn.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA1")

    # 测试解密是否成功
    cursor = conn.execute("SELECT count(*) FROM sqlite_master")
    result = cursor.fetchone()

    return conn
```

## 已知限制

1. **版本依赖**: 内存偏移地址可能随企业微信版本变化而变化
2. **权限要求**: 需要管理员权限才能读取进程内存
3. **进程检测**: 必须在企业微信运行时才能提取密钥
4. **数据目录**: 企业微信的数据目录结构可能与个人微信不同,需要实际测试验证

## 测试状态

### 当前状态
- ✅ 代码实现完成
- ✅ 测试脚本创建
- ⏳ 等待实际企业微信环境测试
- ⏳ 数据库结构分析
- ⏳ MCP服务器集成

### 待验证项
1. 企业微信进程和DLL名称是否正确
2. 内存模式扫描是否能找到密钥
3. 数据目录路径是否正确
4. 数据库文件结构是否与个人微信一致
5. 密钥验证算法是否适用

## 下一步计划

1. **实际测试**: 在安装了企业微信的环境中运行测试
2. **数据库分析**: 分析企业微信数据库结构(MSG*.db, MicroMsg.db等)
3. **功能扩展**:
   - 创建企业微信专用的数据库操作类
   - 实现消息搜索和导出功能
   - 集成到MCP服务器
4. **文档完善**: 根据测试结果更新文档

## 参考资料

- [PyWxDump](https://github.com/xaoyaoo/PyWxDump) - 个人微信解密参考
- [SQLCipher文档](https://www.zetetic.net/sqlcipher/sqlcipher-api/)
- 企业微信官方文档

## 许可声明

本项目仅用于个人学习和研究目的,请勿用于非法用途。使用本工具解密数据库前,请确保:
1. 你是数据的合法所有者
2. 遵守相关法律法规
3. 尊重他人隐私

## 贡献

欢迎提交Issue和Pull Request,特别是:
- 不同企业微信版本的测试结果
- 内存偏移地址的版本适配
- 数据库结构的分析
- 功能改进建议
