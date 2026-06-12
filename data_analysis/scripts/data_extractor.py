#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据提取框架 - WeChatMsgArchive 数据分析流水线

职责：
1. 从解密后的微信数据库（v3/v4）中提取原始数据
2. 统一数据格式，输出为标准化的中间数据（JSON/SQLite）
3. 支持增量提取和全量提取两种模式

依赖：项目已有的 wxManager 模块
"""

import os
import sys
import json
import sqlite3
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Optional, Iterator, Tuple, Set
from pathlib import Path

# 引入项目核心模块
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from wxManager.model.message import MessageType
from wxManager.model.contact import ContactType, Person

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# 数据模型定义
# =============================================================================

@dataclass
class UnifiedMessage:
    """统一消息模型（版本无关）"""
    server_id: int
    local_id: int
    sort_seq: int
    timestamp: int
    str_time: str
    msg_type: int
    msg_type_name: str
    talker_id: str
    is_sender: bool
    sender_id: str
    sender_name: str
    content: str
    xml_content: str = ''
    compress_content: bytes = b''
    status: int = 0
    source_version: str = 'v3'  # 'v3' or 'v4'
    
    # 派生字段
    date: str = field(init=False)
    hour: int = field(init=False)
    weekday: int = field(init=False)
    is_work_hours: bool = field(init=False)
    is_weekend: bool = field(init=False)
    message_length: int = field(init=False)
    
    def __post_init__(self):
        dt = datetime.fromtimestamp(self.timestamp)
        self.date = dt.strftime('%Y-%m-%d')
        self.hour = dt.hour
        self.weekday = dt.weekday()
        self.is_work_hours = 9 <= self.hour <= 18
        self.is_weekend = self.weekday in (5, 6)
        self.message_length = len(self.content) if self.content else 0
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d['compress_content'] = ''  # 二进制不输出
        return d


@dataclass
class UnifiedContact:
    """统一联系人模型"""
    wxid: str
    alias: str
    remark: str
    nickname: str
    display_name: str
    contact_type: int
    contact_type_names: List[str]
    gender: str
    region: Tuple[str, str, str]
    signature: str
    label_list: List[str]
    avatar_url: str
    source_version: str = 'v3'
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ChatRoomInfo:
    """统一群聊信息模型"""
    chatroom_id: str
    chatroom_name: str
    owner_id: str
    member_count: int
    member_list: List[Dict]  # [{'wxid': ..., 'display_name': ...}]
    announce: str
    create_time: int
    source_version: str = 'v3'
    
    def to_dict(self) -> dict:
        return asdict(self)


# =============================================================================
# 抽象提取器基类
# =============================================================================

class BaseDataExtractor(ABC):
    """数据提取器抽象基类"""
    
    def __init__(self, db_dir: str, output_dir: str):
        self.db_dir = Path(db_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
    
    @abstractmethod
    def version(self) -> str:
        """返回版本标识 'v3' 或 'v4'"""
        pass
    
    @abstractmethod
    def get_contact_sql(self) -> str:
        """获取联系人查询 SQL"""
        pass
    
    @abstractmethod
    def get_chatroom_sql(self) -> str:
        """获取群聊查询 SQL"""
        pass
    
    @abstractmethod
    def get_message_sql(self, talker_id: str) -> str:
        """获取消息查询 SQL"""
        pass
    
    @abstractmethod
    def parse_contact_row(self, row: tuple) -> UnifiedContact:
        """解析联系人行数据"""
        pass
    
    @abstractmethod
    def parse_message_row(self, row: tuple, talker_id: str) -> UnifiedMessage:
        """解析消息行数据"""
        pass
    
    def init_db(self):
        """初始化中间数据库"""
        db_path = self.output_dir / f'unified_data_{self.version()}.db'
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()
        logger.info(f"中间数据库已初始化: {db_path}")
    
    def _create_tables(self):
        """创建标准化表结构"""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                server_id INTEGER PRIMARY KEY,
                local_id INTEGER,
                sort_seq INTEGER,
                timestamp INTEGER,
                str_time TEXT,
                date TEXT,
                hour INTEGER,
                weekday INTEGER,
                is_work_hours INTEGER,
                is_weekend INTEGER,
                msg_type INTEGER,
                msg_type_name TEXT,
                talker_id TEXT,
                is_sender INTEGER,
                sender_id TEXT,
                sender_name TEXT,
                content TEXT,
                xml_content TEXT,
                status INTEGER,
                message_length INTEGER,
                source_version TEXT
            );
            
            CREATE TABLE IF NOT EXISTS contacts (
                wxid TEXT PRIMARY KEY,
                alias TEXT,
                remark TEXT,
                nickname TEXT,
                display_name TEXT,
                contact_type INTEGER,
                contact_type_names TEXT,
                gender TEXT,
                region TEXT,
                signature TEXT,
                label_list TEXT,
                avatar_url TEXT,
                source_version TEXT
            );
            
            CREATE TABLE IF NOT EXISTS chatrooms (
                chatroom_id TEXT PRIMARY KEY,
                chatroom_name TEXT,
                owner_id TEXT,
                member_count INTEGER,
                announce TEXT,
                create_time INTEGER,
                source_version TEXT
            );
            
            CREATE TABLE IF NOT EXISTS chatroom_members (
                chatroom_id TEXT,
                wxid TEXT,
                display_name TEXT,
                join_time INTEGER,
                PRIMARY KEY (chatroom_id, wxid)
            );
            
            CREATE INDEX IF NOT EXISTS idx_msg_talker_time 
                ON messages(talker_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_msg_sender 
                ON messages(sender_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_msg_date 
                ON messages(date);
            CREATE INDEX IF NOT EXISTS idx_msg_type 
                ON messages(msg_type, timestamp);
        """)
        self._conn.commit()
    
    def extract_contacts(self) -> List[UnifiedContact]:
        """提取所有联系人/群聊信息"""
        mic_path = self._find_db('MicroMsg.db') or self._find_db('contact.db')
        if not mic_path:
            logger.error("找不到联系人数据库")
            return []
        
        conn = sqlite3.connect(mic_path)
        cur = conn.cursor()
        cur.execute(self.get_contact_sql())
        
        contacts = []
        for row in cur.fetchall():
            try:
                contact = self.parse_contact_row(row)
                contacts.append(contact)
            except Exception as e:
                logger.warning(f"解析联系人行失败: {e}")
        
        conn.close()
        self._save_contacts(contacts)
        logger.info(f"提取联系人: {len(contacts)} 条")
        return contacts
    
    def extract_chatrooms(self) -> List[ChatRoomInfo]:
        """提取群聊信息及成员列表"""
        mic_path = self._find_db('MicroMsg.db') or self._find_db('contact.db')
        if not mic_path:
            return []
        
        conn = sqlite3.connect(mic_path)
        cur = conn.cursor()
        cur.execute(self.get_chatroom_sql())
        
        chatrooms = []
        for row in cur.fetchall():
            try:
                chatroom = self.parse_chatroom_row(row, conn)
                chatrooms.append(chatroom)
            except Exception as e:
                logger.warning(f"解析群聊行失败: {e}")
        
        conn.close()
        self._save_chatrooms(chatrooms)
        logger.info(f"提取群聊: {len(chatrooms)} 个")
        return chatrooms
    
    def extract_messages(self, talker_ids: Optional[List[str]] = None,
                         incremental_after: int = 0) -> int:
        """
        提取消息记录
        
        Args:
            talker_ids: 指定提取的聊天对象，None 表示全部
            incremental_after: 增量提取的时间戳阈值
        
        Returns:
            提取的消息总数
        """
        total = 0
        
        if talker_ids is None:
            talker_ids = self._get_all_talkers()
        
        for talker_id in talker_ids:
            try:
                count = self._extract_single_talker(talker_id, incremental_after)
                total += count
                logger.info(f"提取 [{talker_id}] 消息: {count} 条")
            except Exception as e:
                logger.error(f"提取 [{talker_id}] 失败: {e}")
        
        logger.info(f"消息提取完成，总计: {total} 条")
        return total
    
    def _extract_single_talker(self, talker_id: str, incremental_after: int) -> int:
        """提取单个聊天对象的消息"""
        db_files = self._get_message_db_files(talker_id)
        count = 0
        
        for db_path in db_files:
            if not Path(db_path).exists():
                continue
            
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            sql = self.get_message_sql(talker_id)
            params = [talker_id]
            
            if incremental_after > 0:
                sql = sql.replace('ORDER BY', f'AND CreateTime > ? ORDER BY')
                params.append(incremental_after)
            
            try:
                cur.execute(sql, params)
                rows = cur.fetchall()
                
                messages = []
                for row in rows:
                    try:
                        msg = self.parse_message_row(row, talker_id)
                        messages.append(msg)
                    except Exception as e:
                        logger.debug(f"解析消息失败: {e}")
                
                self._save_messages(messages)
                count += len(messages)
            except Exception as e:
                logger.warning(f"查询数据库失败 [{db_path}]: {e}")
            finally:
                conn.close()
        
        return count
    
    def _save_contacts(self, contacts: List[UnifiedContact]):
        """批量保存联系人"""
        for c in contacts:
            self._conn.execute("""
                INSERT OR REPLACE INTO contacts 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                c.wxid, c.alias, c.remark, c.nickname, c.display_name,
                c.contact_type, ','.join(c.contact_type_names),
                c.gender, ','.join(c.region), c.signature,
                ','.join(c.label_list), c.avatar_url, c.source_version
            ))
        self._conn.commit()
    
    def _save_messages(self, messages: List[UnifiedMessage]):
        """批量保存消息"""
        for m in messages:
            self._conn.execute("""
                INSERT OR IGNORE INTO messages 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                m.server_id, m.local_id, m.sort_seq, m.timestamp, m.str_time,
                m.date, m.hour, m.weekday, int(m.is_work_hours), int(m.is_weekend),
                m.msg_type, m.msg_type_name, m.talker_id, int(m.is_sender),
                m.sender_id, m.sender_name, m.content, m.xml_content,
                m.status, m.message_length, m.source_version
            ))
        self._conn.commit()
    
    def _save_chatrooms(self, chatrooms: List[ChatRoomInfo]):
        """批量保存群聊信息"""
        for cr in chatrooms:
            self._conn.execute("""
                INSERT OR REPLACE INTO chatrooms
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                cr.chatroom_id, cr.chatroom_name, cr.owner_id,
                cr.member_count, cr.announce, cr.create_time, cr.source_version
            ))
            
            for member in cr.member_list:
                self._conn.execute("""
                    INSERT OR REPLACE INTO chatroom_members
                    VALUES (?, ?, ?, ?)
                """, (
                    cr.chatroom_id, member.get('wxid', ''),
                    member.get('display_name', ''), 0
                ))
        self._conn.commit()
    
    def _find_db(self, name: str) -> Optional[str]:
        """在解密目录中查找数据库文件"""
        for root, dirs, files in os.walk(self.db_dir):
            for f in files:
                if f.lower() == name.lower():
                    return os.path.join(root, f)
        return None
    
    def _get_all_talkers(self) -> List[str]:
        """获取所有聊天对象ID"""
        # 优先从 Session 表获取
        session_db = self._find_db('Session.db') or self._find_db('session.db')
        if session_db:
            conn = sqlite3.connect(session_db)
            cur = conn.cursor()
            try:
                cur.execute("SELECT strUsrName FROM Session")
                talkers = [r[0] for r in cur.fetchall() if r[0]]
                if talkers:
                    return talkers
            except:
                pass
            finally:
                conn.close()

        # 如果 Session.db 不存在，从已提取的联系人和群聊中获取
        logger.info("Session.db 不存在，从联系人和群聊中获取 talker_id")
        talkers = []
        try:
            cur = self._conn.cursor()
            cur.execute("SELECT wxid FROM contacts")
            talkers.extend([r[0] for r in cur.fetchall()])
            cur.execute("SELECT chatroom_id FROM chatrooms")
            talkers.extend([r[0] for r in cur.fetchall()])
        except Exception as e:
            logger.warning(f"从中间数据库获取 talker_id 失败: {e}")

        return talkers
    
    def _get_message_db_files(self, talker_id: str) -> List[str]:
        """获取可能存储该 talker 消息的数据库文件列表"""
        # 子类可重写，v3 需要扫描所有 MSG*.db
        dbs = []
        for root, dirs, files in os.walk(self.db_dir):
            for f in files:
                if f.endswith('.db') and 'MSG' in f.upper():
                    dbs.append(os.path.join(root, f))
        return dbs
    
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


# =============================================================================
# v3 提取器实现
# =============================================================================

class V3DataExtractor(BaseDataExtractor):
    """微信 v3 数据提取器"""
    
    def version(self) -> str:
        return 'v3'
    
    def get_contact_sql(self) -> str:
        return """
            SELECT 
                c.UserName, c.Alias, c.Remark, c.NickName, c.Type, c.PYInitial,
                c.RemarkPYInitial, c.ExTraBuf, c.LabelIDList,
                h.smallHeadImgUrl, h.bigHeadImgUrl
            FROM Contact c
            LEFT JOIN ContactHeadImgUrl h ON c.UserName = h.usrName
            ORDER BY c.Type DESC, c.RemarkPYInitial
        """
    
    def get_chatroom_sql(self) -> str:
        return """
            SELECT 
                cr.ChatRoomName, cr.UserNameList, cr.DisplayNameList, cr.RoomData,
                ci.Announcement
            FROM ChatRoom cr
            LEFT JOIN ChatRoomInfo ci ON cr.ChatRoomName = ci.ChatRoomName
        """
    
    def get_message_sql(self, talker_id: str) -> str:
        return """
            SELECT 
                localId, MsgSvrID, Sequence, CreateTime, Type, SubType,
                IsSender, StrTalker, StrContent, CompressContent, BytesExtra, Status
            FROM MSG
            WHERE StrTalker = ?
            ORDER BY Sequence
        """
    
    def parse_contact_row(self, row: tuple) -> UnifiedContact:
        wxid, alias, remark, nickname, ctype, py_init, remark_py, extra_buf, label_ids, small_url, big_url = row
        
        # 确定展示名称
        display_name = remark or nickname or wxid
        
        # 解析 contact_type 位掩码
        type_names = []
        if ctype & ContactType.Chatroom: type_names.append('群聊')
        elif ctype & ContactType.Normal: type_names.append('联系人')
        if ctype & ContactType.Star: type_names.append('星标')
        if ctype & ContactType.Sticky: type_names.append('置顶')
        if ctype & ContactType.Public: type_names.append('公众号')
        if ctype & ContactType.OpenIM: type_names.append('企业微信')
        if ctype & ContactType.Stranger: type_names.append('陌生人')
        if ctype & ContactType.Unknown: type_names.append('未知/已退出')
        
        # 解析 extra_buf 获取性别、地区、签名（简化版，实际需完整解析）
        gender = '未知'
        region = ('', '', '')
        signature = ''
        if extra_buf:
            try:
                # 此处调用项目已有的 extra_buf 解析器
                gender, region, signature = self._parse_extra_buf(extra_buf)
            except:
                pass
        
        return UnifiedContact(
            wxid=wxid or '',
            alias=alias or '',
            remark=remark or '',
            nickname=nickname or '未命名',
            display_name=display_name,
            contact_type=ctype or 0,
            contact_type_names=type_names,
            gender=gender,
            region=region,
            signature=signature,
            label_list=[],
            avatar_url=small_url or '',
            source_version='v3'
        )
    
    def parse_chatroom_row(self, row: tuple, conn: sqlite3.Connection) -> ChatRoomInfo:
        chatroom_id, username_list, display_list, room_data, announce = row
        
        # 从 Contact 表获取群名称
        cur = conn.cursor()
        cur.execute("SELECT NickName, Remark FROM Contact WHERE UserName = ?", (chatroom_id,))
        r = cur.fetchone()
        chatroom_name = (r[1] or r[0] or chatroom_id) if r else chatroom_id
        
        # 解析成员列表
        members = []
        if username_list:
            wxids = username_list.split('\x07')
            names = display_list.split('\x07') if display_list else []
            for i, wxid in enumerate(wxids):
                if wxid:
                    members.append({
                        'wxid': wxid,
                        'display_name': names[i] if i < len(names) else ''
                    })
        
        return ChatRoomInfo(
            chatroom_id=chatroom_id,
            chatroom_name=chatroom_name,
            owner_id='',
            member_count=len(members),
            member_list=members,
            announce=announce or '',
            create_time=0,
            source_version='v3'
        )
    
    def parse_message_row(self, row: tuple, talker_id: str) -> UnifiedMessage:
        local_id, server_id, seq, create_time, msg_type, sub_type, is_sender, \
        str_talker, str_content, compress_content, bytes_extra, status = row
        
        # 映射消息类型
        type_key = (msg_type, sub_type)
        # 简化映射，实际使用项目完整映射表
        type_name = MessageType.name(msg_type) if hasattr(MessageType, 'name') else '未知'
        
        # 解析发送者
        sender_id = ''
        sender_name = '我' if is_sender else '未知'
        
        if not is_sender and talker_id.endswith('@chatroom'):
            # 从 bytes_extra 解析实际发送者（简化处理）
            sender_id = self._parse_sender_from_extra(bytes_extra) or ''
        else:
            sender_id = talker_id if not is_sender else 'self'
        
        # 清洗内容
        content = str_content or ''
        # 去除控制字符
        content = ''.join(c for c in content if ord(c) >= 32 or c in '\n\r\t')
        
        dt = datetime.fromtimestamp(create_time) if create_time else datetime.now()
        
        return UnifiedMessage(
            server_id=server_id or local_id,
            local_id=local_id,
            sort_seq=seq or local_id,
            timestamp=create_time or 0,
            str_time=dt.strftime('%Y-%m-%d %H:%M:%S'),
            msg_type=msg_type,
            msg_type_name=type_name,
            talker_id=talker_id,
            is_sender=bool(is_sender),
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            xml_content='',
            compress_content=compress_content or b'',
            status=status or 0,
            source_version='v3'
        )
    
    def _parse_extra_buf(self, buf: bytes) -> Tuple[str, Tuple[str, str, str], str]:
        """解析 ExtraBuf，返回 (gender, region, signature)"""
        # 实际实现应调用 wxManager.parser 模块
        return '未知', ('', '', ''), ''
    
    def _parse_sender_from_extra(self, extra: bytes) -> Optional[str]:
        """从 BytesExtra 解析发送者 wxid"""
        # 实际实现应调用项目 protobuf 解析器
        if not extra:
            return None
        return None


# =============================================================================
# v4 提取器实现
# =============================================================================

class V4DataExtractor(BaseDataExtractor):
    """微信 v4 数据提取器"""
    
    def version(self) -> str:
        return 'v4'
    
    def get_contact_sql(self) -> str:
        return """
            SELECT 
                username, alias, remark, nick_name, local_type, flag,
                pin_yin_initial, extra_buffer, description,
                small_head_url, big_head_url, chat_room_type
            FROM contact
            ORDER BY local_type DESC, pin_yin_initial
        """
    
    def get_chatroom_sql(self) -> str:
        return """
            SELECT username, owner, ext_buffer FROM chat_room
        """
    
    def get_message_sql(self, talker_id: str) -> str:
        # v4 按表分片，表名 Msg_<md5(talker_id)>
        table_name = f"Msg_{hashlib.md5(talker_id.encode()).hexdigest()}"
        return f"""
            SELECT 
                local_id, server_id, sort_seq, create_time, local_type, 0,
                real_sender_id, origin_source, message_content,
                compress_content, packed_info_data, status
            FROM {table_name}
            WHERE origin_source = ?
            ORDER BY sort_seq
        """
    
    def parse_contact_row(self, row: tuple) -> UnifiedContact:
        wxid, alias, remark, nickname, ctype, flag, py_init, extra_buf, desc, \
        small_url, big_url, cr_type = row
        
        display_name = remark or nickname or wxid
        
        type_names = []
        if ctype & ContactType.Chatroom or cr_type: type_names.append('群聊')
        elif ctype & ContactType.Normal: type_names.append('联系人')
        if ctype & ContactType.Star: type_names.append('星标')
        if ctype & ContactType.Public: type_names.append('公众号')
        
        return UnifiedContact(
            wxid=wxid or '',
            alias=alias or '',
            remark=remark or '',
            nickname=nickname or '未命名',
            display_name=display_name,
            contact_type=ctype or 0,
            contact_type_names=type_names,
            gender='未知',
            region=('', '', ''),
            signature=desc or '',
            label_list=[],
            avatar_url=small_url or '',
            source_version='v4'
        )
    
    def parse_chatroom_row(self, row: tuple, conn: sqlite3.Connection) -> ChatRoomInfo:
        chatroom_id, owner, ext_buffer = row
        
        cur = conn.cursor()
        cur.execute("SELECT nick_name, remark FROM contact WHERE username = ?", (chatroom_id,))
        r = cur.fetchone()
        chatroom_name = (r[1] or r[0] or chatroom_id) if r else chatroom_id
        
        # 解析 ext_buffer 获取成员列表（简化）
        members = []
        
        return ChatRoomInfo(
            chatroom_id=chatroom_id,
            chatroom_name=chatroom_name,
            owner_id=owner or '',
            member_count=len(members),
            member_list=members,
            announce='',
            create_time=0,
            source_version='v4'
        )
    
    def parse_message_row(self, row: tuple, talker_id: str) -> UnifiedMessage:
        local_id, server_id, seq, create_time, msg_type, sub_type, real_sender, \
        origin_source, msg_content, compress_content, packed_info, status = row
        
        type_name = MessageType.name(msg_type) if hasattr(MessageType, 'name') else '未知'
        
        # 解析 content 前缀获取发送者（群聊格式: "wxid:content"）
        is_sender = False
        sender_id = real_sender or ''
        content = msg_content or ''
        
        if talker_id.endswith('@chatroom') and ':' in content:
            parts = content.split(':', 1)
            if len(parts) == 2 and parts[0].startswith('wxid_'):
                sender_id = parts[0]
                content = parts[1]
        
        dt = datetime.fromtimestamp(create_time) if create_time else datetime.now()
        
        return UnifiedMessage(
            server_id=server_id or local_id,
            local_id=local_id,
            sort_seq=seq or local_id,
            timestamp=create_time or 0,
            str_time=dt.strftime('%Y-%m-%d %H:%M:%S'),
            msg_type=msg_type,
            msg_type_name=type_name,
            talker_id=talker_id,
            is_sender=is_sender,
            sender_id=sender_id,
            sender_name=sender_id,
            content=content,
            xml_content='',
            compress_content=compress_content or b'',
            status=status or 0,
            source_version='v4'
        )


# =============================================================================
# 工厂和主入口
# =============================================================================

def create_extractor(version: str, db_dir: str, output_dir: str) -> BaseDataExtractor:
    """创建对应版本的数据提取器"""
    if version == 'v3':
        return V3DataExtractor(db_dir, output_dir)
    elif version == 'v4':
        return V4DataExtractor(db_dir, output_dir)
    else:
        raise ValueError(f"不支持的版本: {version}")


def run_full_extraction(version: str, db_dir: str, output_dir: str,
                        talker_ids: Optional[List[str]] = None):
    """执行完整数据提取流水线"""
    extractor = create_extractor(version, db_dir, output_dir)
    
    try:
        extractor.init_db()
        logger.info("=" * 60)
        logger.info(f"开始提取微信 {version} 数据")
        logger.info("=" * 60)
        
        # 步骤1: 提取联系人
        logger.info("[1/3] 提取联系人...")
        contacts = extractor.extract_contacts()
        
        # 步骤2: 提取群聊
        logger.info("[2/3] 提取群聊信息...")
        chatrooms = extractor.extract_chatrooms()
        
        # 步骤3: 提取消息
        logger.info("[3/3] 提取消息记录...")
        total_messages = extractor.extract_messages(talker_ids=talker_ids)
        
        logger.info("=" * 60)
        logger.info("提取完成!")
        logger.info(f"  联系人: {len(contacts)}")
        logger.info(f"  群聊: {len(chatrooms)}")
        logger.info(f"  消息: {total_messages}")
        logger.info("=" * 60)
        
    finally:
        extractor.close()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='微信数据提取框架')
    parser.add_argument('--version', choices=['v3', 'v4'], required=True, help='微信版本')
    parser.add_argument('--db-dir', required=True, help='解密后的数据库目录')
    parser.add_argument('--output-dir', default='./data_analysis/output', help='输出目录')
    parser.add_argument('--talkers', nargs='+', help='指定提取的聊天对象 wxid')
    
    args = parser.parse_args()
    
    run_full_extraction(
        version=args.version,
        db_dir=args.db_dir,
        output_dir=args.output_dir,
        talker_ids=args.talkers
    )
