"""
数据安全层 - 保护解密后的敏感数据

功能：
1. AES-256 加密存储解密后的数据库
2. 基于密码的访问控制
3. 审计日志记录所有访问操作
4. 自动清理过期数据

使用场景：
- 防止解密数据库被未授权访问
- 满足数据安全合规要求
- 审计追踪数据访问行为
"""

import os
import hashlib
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

logger = logging.getLogger(__name__)


class DataSecurityManager:
    """数据安全管理器"""

    def __init__(self, master_password: str, salt: Optional[bytes] = None):
        """
        初始化安全管理器

        Args:
            master_password: 主密码
            salt: 盐值（用于密钥派生）
        """
        self.salt = salt or os.urandom(16)
        self.cipher = self._derive_cipher(master_password)
        self.audit_log_path = "output/security_audit.log"

    def _derive_cipher(self, password: str) -> Fernet:
        """从密码派生加密密钥"""
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.salt,
            iterations=100000,
      )
        key = kdf.derive(password.encode())
        return Fernet(key)

    def encrypt_database(self, db_path: str, output_path: str):
        """加密数据库文件"""
        self._log_audit("encrypt", db_path)

        with open(db_path, 'rb') as f:
            plaintext = f.read()

        encrypted = self.cipher.encrypt(plaintext)

        with open(output_path, 'wb') as f:
            f.write(self.salt + encrypted)

        logger.info(f"✓ 数据库已加密: {output_path}")

    def decrypt_database(self, encrypted_path: str, output_path: str):
        """解密数据库文件"""
        self._log_audit("decrypt", encrypted_path)

        with open(encrypted_path, 'rb') as f:
            data = f.read()

        # 提取盐值和密文
        salt = data[:16]
        encrypted = data[16:]

        # 验证盐值
      if salt != self.salt:
            raise ValueError("密码错误或文件损坏")

      plaintext = self.cipher.decrypt(encrypted)

        with open(output_path, 'wb') as f:
          f.write(plaintext)

        logger.info(f"✓ 数据库已解密: {output_path}")

    def _log_audit(self, action: str, target: str):
        """记录审计日志"""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {action.upper()}: {target}\n"

        with open(self.audit_log_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)

    def cleanup_expired_data(self, directory: str, days: int = 7):
      """清理过期的解密数据"""
        self._log_audit("cleanup", directory)

        cutoff_time = datetime.now() - timedelta(days=days)
        removed_count = 0

        for file_path in Path(directory).rglob("*.db"):
            if file_path.stat().st_mtime < cutoff_time.timestamp():
              file_path.unlink()
          removed_count += 1
                logger.info(f"✓ 已删除过期文件: {file_path}")

        logger.info(f"✓ 清理完成，删除 {removed_count} 个过期文件")


# 使用示例
if __name__ == "__main__":
    # 初始化安全管理器
    manager = DataSecurityManager(master_password="your-strong-password")

    # 加密数据库
    manager.encrypt_database(
        "output/decrypted_db/MicroMsg.db",
        "output/encrypted_db/MicroMsg.db.enc"
    )

    # 解密数据库（需要时）
    manager.decrypt_database(
        "output/encrypted_db/MicroMsg.db.enc",
      "output/temp/MicroMsg.db"
    )

    # 清理7天前的临时文件
    manager.cleanup_expired_data("output/temp", days=7)
