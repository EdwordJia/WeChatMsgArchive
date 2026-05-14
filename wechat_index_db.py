"""
微信消息索引数据库
解决搜索慢和搜索不到的问题
"""
import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

PROJECT_DIR = Path(__file__).parent
INDEX_DB = PROJECT_DIR / 'output' / 'wechat_index.db'
DECRYPTED_DIR = PROJECT_DIR / 'output' / 'decrypted_db'


class WeChatIndexDB:
    """微信消息索引数据库"""

    def __init__(self):
        self.conn = sqlite3.connect(INDEX_DB)
        self.init_schema()

    def init_schema(self):
        """初始化数据库结构"""
        cur = self.conn.cursor()

        # 联系人表
        cur.execute('''
            CREATE TABLE IF NOT EXISTS contacts (
                wxid TEXT PRIMARY KEY,
                nickname TEXT,
                remark TEXT,
                alias TEXT,
                type INTEGER,
                updated_at INTEGER
            )
        ''')

        # 群聊表
        cur.execute('''
            CREATE TABLE IF NOT EXISTS chatrooms (
                chatroom_id TEXT PRIMARY KEY,
                name TEXT,
                member_list TEXT,
                updated_at INTEGER
            )
        ''')

        # 消息表（全量索引）
        cur.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
                local_id INTEGER,
                talker TEXT,
                sender_wxid TEXT,
                msg_type INTEGER,
                content TEXT,
                create_time INTEGER,
                is_sender INTEGER,
                source_db TEXT,
                indexed_at INTEGER
            )
        ''')

        # 创建索引加速查询
        cur.execute('CREATE INDEX IF NOT EXISTS idx_talker ON messages(talker)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_sender ON messages(sender_wxid)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_time ON messages(create_time)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_content ON messages(content)')

        # 同步状态表
        cur.execute('''
            CREATE TABLE IF NOT EXISTS sync_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at INTEGER
            )
        ''')

        self.conn.commit()

    def get_last_sync_time(self) -> int:
        """获取上次同步时间"""
        cur = self.conn.cursor()
        cur.execute('SELECT value FROM sync_state WHERE key=?', ('last_sync_time',))
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def set_last_sync_time(self, timestamp: int):
        """设置同步时间"""
        cur = self.conn.cursor()
        now = int(datetime.now().timestamp())
        cur.execute('''
            INSERT OR REPLACE INTO sync_state (key, value, updated_at)
            VALUES (?, ?, ?)
        ''', ('last_sync_time', str(timestamp), now))
        self.conn.commit()

    def sync_contacts(self):
        """同步联系人信息"""
        micro_db = DECRYPTED_DIR / 'MicroMsg.db'
        if not micro_db.exists():
            return

        conn_micro = sqlite3.connect(micro_db)
        cur_micro = conn_micro.cursor()

        # 同步联系人
        cur_micro.execute('SELECT UserName, NickName, Remark, Alias, Type FROM Contact')
        now = int(datetime.now().timestamp())

        cur = self.conn.cursor()
        for wxid, nick, remark, alias, ctype in cur_micro.fetchall():
            cur.execute('''
                INSERT OR REPLACE INTO contacts (wxid, nickname, remark, alias, type, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (wxid, nick, remark, alias, ctype, now))

        # 同步群聊
        cur_micro.execute('SELECT ChatRoomName, UserNameList FROM ChatRoom')
        for room_id, members in cur_micro.fetchall():
            cur_micro.execute('SELECT strNickName FROM Session WHERE strUsrName=?', (room_id,))
            row = cur_micro.fetchone()
            name = row[0] if row else room_id

            cur.execute('''
                INSERT OR REPLACE INTO chatrooms (chatroom_id, name, member_list, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (room_id, name, members, now))

        conn_micro.close()
        self.conn.commit()

    def sync_messages_incremental(self, since_timestamp: int = 0):
        """增量同步消息"""
        from wechat_monitor import parse_bytes_extra

        msg_dir = DECRYPTED_DIR / 'Multi'
        all_dbs = []

        if msg_dir.exists():
            all_dbs.extend(msg_dir.glob('MSG*.db'))
        all_dbs.extend(DECRYPTED_DIR.glob('MSG*.db'))

        cur = self.conn.cursor()
        now = int(datetime.now().timestamp())
        total_new = 0

        for db_path in all_dbs:
            try:
                conn_msg = sqlite3.connect(db_path)
                cur_msg = conn_msg.cursor()

                # 只同步新消息
                cur_msg.execute('''
                    SELECT localId, StrTalker, Type, IsSender, CreateTime, StrContent, BytesExtra
                    FROM MSG WHERE CreateTime > ?
                ''', (since_timestamp,))

                for local_id, talker, msg_type, is_sender, ts, content, bytes_extra in cur_msg.fetchall():
                    sender_wxid = '' if is_sender else (parse_bytes_extra(bytes_extra) or '')

                    cur.execute('''
                        INSERT OR IGNORE INTO messages
                        (local_id, talker, sender_wxid, msg_type, content, create_time, is_sender, source_db, indexed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (local_id, talker, sender_wxid, msg_type, content, ts, is_sender, db_path.name, now))

                    if cur.rowcount > 0:
                        total_new += 1

                conn_msg.close()
            except Exception as e:
                print(f'同步 {db_path.name} 失败: {e}')

        self.conn.commit()
        return total_new

    def search_user_messages(self, wxid: str, since_time: int = 0, limit: int = 100) -> List[Dict]:
        """搜索用户消息"""
        cur = self.conn.cursor()
        cur.execute('''
            SELECT m.create_time, m.msg_type, m.content, m.talker, c.name
            FROM messages m
            LEFT JOIN chatrooms c ON m.talker = c.chatroom_id
            WHERE m.sender_wxid = ? AND m.create_time > ?
            ORDER BY m.create_time DESC
            LIMIT ?
        ''', (wxid, since_time, limit))

        results = []
        for ts, msg_type, content, talker, group_name in cur.fetchall():
            results.append({
                'time': datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S'),
                'type': msg_type,
                'content': content,
                'talker': talker,
                'group': group_name or talker,
                'timestamp': ts
            })
        return results

    def search_keyword(self, keyword: str, since_time: int = 0, limit: int = 100) -> List[Dict]:
        """关键词搜索"""
        cur = self.conn.cursor()
        cur.execute('''
            SELECT m.create_time, m.sender_wxid, m.content, m.talker, c.name, ct.nickname, ct.remark
            FROM messages m
            LEFT JOIN chatrooms c ON m.talker = c.chatroom_id
            LEFT JOIN contacts ct ON m.sender_wxid = ct.wxid
            WHERE m.msg_type = 1 AND m.content LIKE ? AND m.create_time > ?
            ORDER BY m.create_time DESC
            LIMIT ?
        ''', (f'%{keyword}%', since_time, limit))

        results = []
        for ts, sender, content, talker, group_name, nick, remark in cur.fetchall():
            results.append({
                'time': datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S'),
                'sender': remark or nick or sender,
                'content': content,
                'group': group_name or talker,
                'timestamp': ts
            })
        return results

    def get_monitored_users_wxids(self, keywords: List[str]) -> Dict[str, List[str]]:
        """获取监控用户的wxid列表"""
        cur = self.conn.cursor()
        result = {}

        for keyword in keywords:
            cur.execute('''
                SELECT wxid FROM contacts
                WHERE nickname LIKE ? OR remark LIKE ?
            ''', (f'%{keyword}%', f'%{keyword}%'))

            wxids = [row[0] for row in cur.fetchall()]
            if wxids:
                result[keyword] = wxids

        return result

    def close(self):
        self.conn.close()


def full_sync():
    """全量同步（首次运行）"""
    print('开始全量同步...')
    db = WeChatIndexDB()

    print('1. 同步联系人和群聊...')
    db.sync_contacts()

    print('2. 同步所有消息...')
    total = db.sync_messages_incremental(since_timestamp=0)
    print(f'   同步了 {total} 条消息')

    now = int(datetime.now().timestamp())
    db.set_last_sync_time(now)

    db.close()
    print('全量同步完成！')


def incremental_sync():
    """增量同步（定时任务调用）"""
    db = WeChatIndexDB()

    last_sync = db.get_last_sync_time()
    print(f'上次同步: {datetime.fromtimestamp(last_sync).strftime("%Y-%m-%d %H:%M:%S")}')

    db.sync_contacts()
    total = db.sync_messages_incremental(since_timestamp=last_sync)
    print(f'新增消息: {total} 条')

    now = int(datetime.now().timestamp())
    db.set_last_sync_time(now)

    db.close()
    return total


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'full':
        full_sync()
    else:
        incremental_sync()
