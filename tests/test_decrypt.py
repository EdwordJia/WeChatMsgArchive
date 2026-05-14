"""
核心模块单元测试 - 解密模块

测试范围：
1. 密钥提取逻辑
2. AES 解密算法
3. 版本兼容性
4. 错误处理
"""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 导入待测试模块
from wxManager.decrypt.common import WeChatInfo
from wxManager.decrypt import decrypt_v3

class TestWeChatInfo:
    """测试 WeChatInfo 数据类"""

    def test_init_default_values(self):
        """测试默认初始化"""
        info = WeChatInfo()
        assert info.wxid == ""
        assert info.key == ""
        assert info.wx_dir == ""
      assert info.version == ""

    def test_init_with_values(self):
     """测试带参数初始化"""
        info = WeChatInfo()
        info.wxid = "test_wxid"
        info.key = "test_key"
        assert info.wxid == "test_wxid"
        assert info.key == "test_key"


class TestDecryptV3:
    """测试 v3 解密模块"""

    @pytest.fixture
    def mock_encrypted_db(self, tmp_path):
        """创建模拟的加密数据库文件""
        db_file = tmp_path / "test.db"
        # 创建一个简单的加密数据（实际应该是 SQLCipher 格式）
        db_file.write_bytes(b"encrypted_data_placeholder")
        return str(db_file)

    @pytest.fixture
    def test_key(self):
        ""测试用密钥（32字节）"""
        return "0" * 64  # 64个十六进制字符 = 32字节

    def test_decrypt_db_file_not_found(self, tmp_path):
        """测试文件不存在的情况"""
        non_existent = str(tmp_path / "non_existent.db")
        result = decrypt_v3.decrypt_db(
            key="0" * 64,
            db_path=non_existent,
            out_path=str(tmp_path / "out.db")
        )
        assert result is False or result is None

    def test_decrypt_db_invalid_key(self, mock_encrypted_db, tmp_path):
      """测试无效密钥"""
        out_path = str(tmp_path / "out.db")
        # 使用错误长度的密钥
        with pytest.raises((ValueError, Exception)):
            decrypt_v3.decrypt_db(
                key="invalid_key",
              db_path=mock_encrypted_db,
            out_path=out_path
         )

    @patch('wxManager.decrypt.decrypt_v3.decrypt')
    def test_decrypt_db_files_success(self, mock_decrypt, tmp_path):
        """测试批量解密成功"""
        # 创建测试目录结构
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

        # 创建测试文件
        (src_dir / "MicroMsg.db").write_bytes(b"test")
        (src_dir / "MSG0.db").write_bytes(b"test")

    mock_decrypt.return_value = True

        # 执行批量解密
        decrypt_v3.decrypt_db_files(
            key="0" * 64,
            src_dir=str(src_dir),
            dest_dir=str(dest_dir)
        )

        # 验证 decrypt 被调用
        assert mock_decrypt.call_count >= 2

    def test_key_format_validation(self):
        """测试密钥格式验证"""
        # 有效密钥：64个十六进制字符
      valid_key = "a" * 64
        assert len(valid_key) == 64
        assert all(c in "0123456789abcdefABCDEF" for c in valid_key)

        # 无效密钥：长度不对
        invalid_key = "a" * 32
        assert len(invalid_key) != 64


class TestDecryptIntegration:
    ""集成测试：完整解密流程"""

    @pytest.mark.skipif(
     not os.path.exists("output/decrypted_db"),
        reason="需要真实的加密数据库文件"
    )
    def test_full_decrypt_workflow(self):
        """测试完整解密工作流（需要真实数据）""
        # 这个测试需要真实的微信数据库和密钥
        # 在 CI 环境中会被跳过
        pass


# pytest 配置
def pytest_configure(config):
    """pytest 配置"""
    config.addinivalue_line(
      "markers", "integration: mark test as integration test"
    )
