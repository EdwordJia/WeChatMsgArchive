# -*- coding: utf-8 -*-
"""
微信消息获取模块

从解密的微信数据库中获取最近的群消息
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional


class WeChatMessageFetcher:
    """微信消息获取器"""

    def __init__(self, db_dir: str = "output/decrypted_db"):
        """
        初始化

        Args:
            db_dir: 解密数据库目录
        """
        self.db_dir = Path(db_dir)
        self.micromsg_db = self.db_dir / "MicroMsg.db"

    def fetch_recent_messages(self, hours: int = 24, chatroom_filter: Optional[List[str]] = None) -> List[Dict]:
        """
        获取最近的群消息

        Args:
            hours: 获取最近N小时的消息
            chatroom_filter: 群聊ID过滤列表，None表示所有群

        Returns:
            消息列表，每条消息包含：content, sender, time, chatroom
        """
        messages = []

        if not self.micromsg_db.exists():
            print(f"数据库不存在: {self.micromsg_db}")
            return messages

        try:
            conn = sqlite3.connect(str(self.micromsg_db))
            cursor = conn.cursor()

            # 计算时间戳（微信使用秒级时间戳）
            cutoff_time = int((datetime.now() - timedelta(hours=hours)).timestamp())

            # 查询群聊消息
            # 注意：实际的表结构可能不同，需要根据实际情况调整
            query = """
                SELECT
                    content,
                    sender,
                    create_time,
                    chatroom_id
                FROM messages
                WHERE create_time > ?
                AND chatroom_id LIKE '%@chatroom'
                ORDER BY create_time DESC
                LIMIT 100
            """

            try:
                cursor.execute(query, (cutoff_time,))
                rows = cursor.fetchall()

                for row in rows:
                    content, sender, create_time, chatroom_id = row

                    # 过滤群聊
                    if chatroom_filter and chatroom_id not in chatroom_filter:
                        continue

                    messages.append({
                        "content": content,
                        "sender": sender,
                        "time": datetime.fromtimestamp(create_time).strftime("%Y-%m-%d %H:%M:%S"),
                        "chatroom": chatroom_id
                    })

            except sqlite3.OperationalError as e:
                print(f"查询失败（表结构可能不同）: {e}")
                # 返回空列表，不影响流程
                return []

            conn.close()

        except Exception as e:
            print(f"获取消息失败: {e}")

        return messages

    def get_chatroom_list(self) -> List[Dict]:
        """
        获取所有群聊列表

        Returns:
            群聊列表，每个群包含：chatroom_id, name, member_count
        """
        chatrooms = []

        if not self.micromsg_db.exists():
            return chatrooms

        try:
            conn = sqlite3.connect(str(self.micromsg_db))
            cursor = conn.cursor()

            # 查询群聊信息
            query = """
                SELECT
                    UserName,
                    NickName,
                    ChatRoomMemberCount
                FROM Contact
                WHERE UserName LIKE '%@chatroom'
                ORDER BY ChatRoomMemberCount DESC
            """

            try:
                cursor.execute(query)
                rows = cursor.fetchall()

                for row in rows:
                    username, nickname, member_count = row
                    chatrooms.append({
                        "chatroom_id": username,
                        "name": nickname or "未命名群聊",
                        "member_count": member_count or 0
                    })

            except sqlite3.OperationalError as e:
                print(f"查询群聊失败: {e}")

            conn.close()

        except Exception as e:
            print(f"获取群聊列表失败: {e}")

        return chatrooms


# 便捷函数
def fetch_recent_messages(hours: int = 24) -> List[Dict]:
    """
    快速获取最近的群消息

    Args:
        hours: 获取最近N小时的消息

    Returns:
        消息列表
    """
    fetcher = WeChatMessageFetcher()
    return fetcher.fetch_recent_messages(hours=hours)


if __name__ == "__main__":
    # 测试
    print("测试微信消息获取...")
    fetcher = WeChatMessageFetcher()

    # 获取群聊列表
    chatrooms = fetcher.get_chatroom_list()
    print(f"\n找到 {len(chatrooms)} 个群聊")
    for i, room in enumerate(chatrooms[:5], 1):
        print(f"{i}. {room['name']} ({room['member_count']}人)")

    # 获取最近24小时的消息
    messages = fetcher.fetch_recent_messages(hours=24)
    print(f"\n找到 {len(messages)} 条最近消息")
    for i, msg in enumerate(messages[:5], 1):
        print(f"{i}. [{msg['time']}] {msg['sender']}: {msg['content'][:50]}...")
