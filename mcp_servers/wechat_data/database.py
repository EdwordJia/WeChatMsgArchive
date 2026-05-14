"""
微信数据库访问层
提供统一的数据访问接口
"""
import sqlite3
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from pathlib import Path


class WeChatDatabase:
    """微信数据库访问类"""

    def __init__(self, db_path: str = None):
        """
        初始化数据库连接

        Args:
            db_path: 数据库路径，默认使用 output/wechat_index.db
        """
        if db_path is None:
            db_path = os.path.join(os.getcwd(), 'output', 'wechat_index.db')

        self.db_path = db_path
        # 使用数据库文件所在目录作为基准，而不是当前工作目录
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        self.decrypted_db_dir = os.path.join(db_dir, 'decrypted_db', 'Multi')

        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"数据库文件不存在: {self.db_path}")

    def _get_connection(self, db_path: str = None) -> sqlite3.Connection:
        """获取数据库连接"""
        path = db_path or self.db_path
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    def search_messages(
        self,
        keyword: str,
        limit: int = 100,
        since_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索消息内容

        Args:
            keyword: 搜索关键词
            limit: 返回数量限制
            since_time: 起始时间戳（可选）

        Returns:
            消息列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = """
            SELECT create_time, content, is_sender, talker, sender_wxid, msg_type
            FROM messages
            WHERE content LIKE ?
        """
        params = [f'%{keyword}%']

        if since_time:
            query += " AND create_time >= ?"
            params.append(since_time)

        query += " ORDER BY create_time DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_contact_messages(
        self,
        wxid: str,
        days: int = 7,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取指定联系人的消息

        Args:
            wxid: 微信ID
            days: 最近N天
            limit: 返回数量限制

        Returns:
            消息列表
        """
        since_time = int((datetime.now() - timedelta(days=days)).timestamp())

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT create_time, content, is_sender, talker, msg_type
            FROM messages
            WHERE talker = ? AND create_time >= ?
            ORDER BY create_time DESC
            LIMIT ?
        """, (wxid, since_time, limit))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_group_messages(
        self,
        group_id: str,
        days: int = 7,
        limit: int = 100,
        sender_wxid: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取群聊消息

        Args:
            group_id: 群聊ID
            days: 最近N天
            limit: 返回数量限制
            sender_wxid: 发送者wxid（可选，用于筛选特定成员）

        Returns:
            消息列表
        """
        since_time = int((datetime.now() - timedelta(days=days)).timestamp())

        # 从解密数据库查询
        msg_dbs = [
            os.path.join(self.decrypted_db_dir, 'MSG0.db'),
            os.path.join(self.decrypted_db_dir, 'MSG1.db')
        ]

        all_messages = []

        for db_path in msg_dbs:
            if not os.path.exists(db_path):
                continue

            try:
                conn = self._get_connection(db_path)
                cursor = conn.cursor()

                query = """
                    SELECT CreateTime as create_time,
                           StrContent as content,
                           IsSender as is_sender,
                           StrTalker as talker,
                           Type as msg_type
                    FROM MSG
                    WHERE StrTalker = ? AND CreateTime >= ?
                """
                params = [group_id, since_time]

                if sender_wxid:
                    query += " AND StrContent LIKE ?"
                    params.append(f'%{sender_wxid}%')

                query += " ORDER BY CreateTime DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                rows = cursor.fetchall()

                for row in rows:
                    msg = dict(row)
                    # 处理二进制内容
                    if isinstance(msg['content'], bytes):
                        msg['content'] = msg['content'].decode('utf-8', errors='ignore')
                    all_messages.append(msg)

                conn.close()
            except Exception as e:
                print(f"查询 {db_path} 失败: {e}")

        # 按时间排序并限制数量
        all_messages.sort(key=lambda x: x['create_time'], reverse=True)
        return all_messages[:limit]

    def search_by_time_range(
        self,
        start_time: int,
        end_time: int,
        talker_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        按时间范围查询消息

        Args:
            start_time: 开始时间戳
            end_time: 结束时间戳
            talker_id: 对话者ID（可选）
            limit: 返回数量限制

        Returns:
            消息列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = """
            SELECT create_time, content, is_sender, talker, sender_wxid, msg_type
            FROM messages
            WHERE create_time >= ? AND create_time <= ?
        """
        params = [start_time, end_time]

        if talker_id:
            query += " AND talker = ?"
            params.append(talker_id)

        query += " ORDER BY create_time DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_contact_info(
        self,
        wxid: Optional[str] = None,
        nickname: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取联系人信息

        Args:
            wxid: 微信ID
            nickname: 昵称

        Returns:
            联系人列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if wxid:
            cursor.execute("""
                SELECT wxid, nickname, remark, type
                FROM contacts
                WHERE wxid = ?
            """, (wxid,))
        elif nickname:
            cursor.execute("""
                SELECT wxid, nickname, remark, type
                FROM contacts
                WHERE nickname LIKE ? OR remark LIKE ?
            """, (f'%{nickname}%', f'%{nickname}%'))
        else:
            return []

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_all_groups(self) -> List[Dict[str, Any]]:
        """
        获取所有群聊列表

        Returns:
            群聊列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT wxid, nickname, remark, type
            FROM contacts
            WHERE wxid LIKE '%@chatroom'
            ORDER BY nickname
        """)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def sync_data(self, incremental: bool = True) -> Dict[str, Any]:
        """
        同步微信数据到索引数据库

        Args:
            incremental: 是否增量同步（默认True），False为全量同步

        Returns:
            同步结果统计
        """
        try:
            # 导入同步逻辑
            project_dir = Path(os.getcwd())
            sys.path.insert(0, str(project_dir))

            from wechat_index_db import WeChatIndexDB
            from wechat_monitor import parse_bytes_extra

            db = WeChatIndexDB()

            # 同步联系人
            db.sync_contacts()

            # 同步消息
            if incremental:
                last_sync = db.get_last_sync_time()
                last_sync_str = datetime.fromtimestamp(last_sync).strftime('%Y-%m-%d %H:%M:%S') if last_sync else '从未同步'
                total = db.sync_messages_incremental(since_timestamp=last_sync)
            else:
                total = db.sync_messages_incremental(since_timestamp=0)
                last_sync_str = '全量同步'

            # 更新同步时间
            now = int(datetime.now().timestamp())
            db.set_last_sync_time(now)
            db.close()

            return {
                'success': True,
                'sync_type': 'incremental' if incremental else 'full',
                'last_sync': last_sync_str,
                'new_messages': total,
                'sync_time': datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S')
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_sync_status(self) -> Dict[str, Any]:
        """
        获取同步状态

        Returns:
            同步状态信息
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 获取上次同步时间
            cursor.execute("SELECT value FROM sync_state WHERE key = 'last_sync_time'")
            row = cursor.fetchone()
            last_sync = int(row['value']) if row else 0

            # 获取消息总数
            cursor.execute("SELECT COUNT(*) as total FROM messages")
            total_messages = cursor.fetchone()['total']

            # 获取最新消息时间
            cursor.execute("SELECT MAX(create_time) as latest FROM messages")
            latest_msg = cursor.fetchone()['latest']

            conn.close()

            return {
                'success': True,
                'last_sync': datetime.fromtimestamp(last_sync).strftime('%Y-%m-%d %H:%M:%S') if last_sync else '从未同步',
                'last_sync_timestamp': last_sync,
                'total_messages': total_messages,
                'latest_message': datetime.fromtimestamp(latest_msg).strftime('%Y-%m-%d %H:%M:%S') if latest_msg else '无消息',
                'latest_message_timestamp': latest_msg or 0
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
