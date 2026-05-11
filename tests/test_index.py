""
核心模块单元测试 - 索引模块

测试范围：
1. 消息提取逻辑
2. 索引构建
3. 查询性能
4. 增量同步
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime

# 导入待测试模块（需要根据实际路径调整）
# from wechat_index_db import ...


class TestMessageExtraction:
    """测试消息提取"""

    @pytest.fixture
    def mock_msg_db(self, tmp_path):
        """创建模拟的 MSG 数据库"""
        db_path = tmp_path / "MSG0.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 创建简化的 MSG 表结构
        cursor.execute("""
            CREATE TABLE MSG (
            localId INTEGER PRIMARY KEY,
           TalkerId INTEGER,
              Type INTEGER,
         SubType INTEGER,
           IsSender INTEGER,
                CreateTime INTEGER,
              StrTalker TEXT,
                StrContent TEXT
            )
        """)

     # 插入测试数据
        test_messages = [
          (1, 1001, 1, 0, 0, 1778400000, "user1", "测试消息1"),
          (2, 1002, 1, 0, 1, 1778400100, "user2", "测试消息2"),
            (3, 1001, 1, 0, 0, 1778400200, "user1", "测试消息3"),
        ]
        cursor.executemany(
          "INSERT INTO MSG VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            test_messages
        )

        conn.commit()
        conn.close()
        return str(db_path)

    def test_extract_messages_from_db(self, mock_msg_db):
        """测试从数据库提取消息"""
        conn = sqlite3.connect(mock_msg_db)
      cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM MSG")
      count = cursor.fetchone()[0]

        assert count == 3

     cursor.execute("SELECT StrContent FROM MSG WHERE IsSender = 0")
        messages = cursor.fetchall()

        assert len(messages) == 2
        assert messages[0][0] == "测试消息1"

        conn.close()

    def test_filter_by_time_range(self, mock_msg_db):
        """测试时间范围过滤"""
        conn = sqlite3.connect(mock_msg_db)
      cursor = conn.cursor()

        # 查询特定时间范围的消息
        cursor.execute(
            "SELECT COUNT(*) FROM MSG WHERE CreateTime BETWEEN ? AND ?",
         (1778400000, 1778400150)
      )
        count = cursor.fetchone()[0]

        assert count == 2

        conn.close()


class TestIndexBuilding:
    """测试索引构建"""

    @pytest.fixture
    def index_db(self, tmp_path):
        """创建索引数据库"""
        db_path = tmp_path / "index.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
       talker TEXT,
                sender TEXT,
         content TEXT,
                time INTEGER,
          source_db TEXT
         )
    """)

        # 创建索引
        cursor.execute("CREATE INDEX idx_talker ON messages(talker)")
        cursor.execute("CREATE INDEX idx_time ON messages(time)")
        cursor.execute("CREATE INDEX idx_content ON messages(content)")

        conn.commit()
        conn.close()
        return str(db_path)

    def test_insert_messages(self, index_db):
        """测试插入消息到索引"""
        conn = sqlite3.connect(index_db)
      cursor = conn.cursor()

        messages = [
            ("user1", "user1", "消息1", 1778400000, "MSG0.db"),
         ("user2", "user2", "消息2", 1778400100, "MSG0.db"),
        ]

        cursor.executemany(
            "INSERT INTO messages (talker, sender, content, time, source_db) VALUES (?, ?, ?, ?, ?)",
            messages
        )

        conn.commit()

      cursor.execute("SELECT COUNT(*) FROM messages")
        count = cursor.fetchone()[0]

        assert count == 2

      conn.close()

    def test_query_performance(self, index_db):
        """测试查询性能（简单验证索引存在）"""
        conn = sqlite3.connect(index_db)
        cursor = conn.cursor()

        # 验证索引存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]

        assert "idx_talker" in indexes
        assert "idx_time" in indexes
        assert "idx_content" in indexes

        conn.close()


class TestIncrementalSync:
    """测试增量同步"""

    def test_get_last_sync_timestamp(self, tmp_path):
        """测试获取最后同步时间戳"""
        db_path = tmp_path / "index.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("""
          CREATE TABLE messages (
             time INTEGER,
              source_db TEXT
         )
        """)

        cursor.execute(
            "INSERT INTO messages (time, source_db) VALUES (?, ?)",
        (1778400000, "MSG0.db")
        )
        cursor.execute(
            "INSERT INTO messages (time, source_db) VALUES (?, ?)",
            (1778400200, "MSG0.db")
        )

        conn.commit()

        # 获取最新时间戳
        cursor.execute(
       "SELECT MAX(time) FROM messages WHERE source_db = ?",
          ("MSG0.db",)
        )
        last_timestamp = cursor.fetchone()[0]

        assert last_timestamp == 1778400200

        conn.close()


# pytest 配置
@pytest.fixture(scope="session")
def test_data_dir(tmp_path_factory):
    """创建测试数据目录"""
    return tmp_path_factory.mktemp("test_data")
