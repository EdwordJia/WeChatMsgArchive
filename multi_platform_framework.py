#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多平台消息分析框架
支持微信、飞书、企业微信等多个平台
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
import sqlite3
import json
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# 统一数据模型
# ============================================================================

@dataclass
class Contact:
    """联系人统一模型"""
    id: str
    platform: str
    name: str
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    type: str = 'user'  # user, bot, system
    metadata: Optional[Dict] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class Group:
    """群组统一模型"""
    id: str
    platform: str
    name: str
    member_count: int
    owner_id: Optional[str] = None
    created_at: Optional[datetime] = None
    metadata: Optional[Dict] = None

    def to_dict(self):
        data = asdict(self)
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        return data


@dataclass
class Message:
    """消息统一模型"""
    id: str
    platform: str
    talker_id: str
    sender_id: str
    content: str
    msg_type: str  # text, image, video, file, etc.
    timestamp: datetime
    is_sender: bool
    metadata: Optional[Dict] = None

    def to_dict(self):
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


# ============================================================================
# 平台适配器接口
# ============================================================================

class PlatformAdapter(ABC):
    """平台适配器基类"""

    @abstractmethod
    def get_platform_name(self) -> str:
        """获取平台名称"""
        pass

    @abstractmethod
    def connect(self) -> bool:
        """连接到数据源"""
        pass

    @abstractmethod
    def disconnect(self):
        """断开连接"""
        pass

    @abstractmethod
    def get_contacts(self) -> List[Contact]:
        """获取联系人列表"""
        pass

    @abstractmethod
    def get_groups(self) -> List[Group]:
        """获取群组列表"""
        pass

    @abstractmethod
    def get_messages(
        self,
        talker_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Message]:
        """获取消息列表"""
        pass

    @abstractmethod
    def get_message_count(self, talker_id: str) -> int:
        """获取消息数量"""
        pass


# ============================================================================
# 微信适配器实现
# ============================================================================

class WeChatAdapter(PlatformAdapter):
    """微信平台适配器"""

    def __init__(self, db_paths: List[Path], contact_db: Optional[Path] = None):
        self.db_paths = db_paths
        self.contact_db = contact_db
        self.connections = []
        self.contact_conn = None

    def get_platform_name(self) -> str:
        return "wechat"

    def connect(self) -> bool:
        """连接到微信数据库"""
        try:
            for db_path in self.db_paths:
                if db_path.exists():
                    conn = sqlite3.connect(db_path)
                    self.connections.append(conn)

            # 连接联系人数据库
            if self.contact_db and self.contact_db.exists():
                self.contact_conn = sqlite3.connect(self.contact_db)

            return len(self.connections) > 0
        except Exception as e:
            logger.error(f"连接微信数据库失败: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        for conn in self.connections:
            conn.close()
        self.connections = []
        if self.contact_conn:
            self.contact_conn.close()
            self.contact_conn = None

    def get_contacts(self) -> List[Contact]:
        """获取联系人"""
        contacts = []

        # 如果有专门的联系人数据库，从那里读取
        if self.contact_conn:
            try:
                cursor = self.contact_conn.cursor()
                cursor.execute("SELECT UserName, NickName, Remark FROM Contact WHERE Type = 1")
                for row in cursor.fetchall():
                    contacts.append(Contact(
                        id=row[0],
                        platform="wechat",
                        name=row[2] or row[1] or row[0],
                        nickname=row[1],
                        type='user'
                    ))
            except Exception as e:
                logger.error(f"获取联系人失败: {e}")

        return contacts

    def get_groups(self) -> List[Group]:
        """获取群组"""
        groups = []

        # 如果有专门的联系人数据库，从那里读取
        if self.contact_conn:
            try:
                cursor = self.contact_conn.cursor()
                cursor.execute("SELECT ChatRoomName, UserNameList FROM ChatRoom")
                for row in cursor.fetchall():
                    member_list = row[1].split('^G') if row[1] else []
                    groups.append(Group(
                        id=row[0],
                        platform="wechat",
                        name=row[0],
                        member_count=len(member_list)
                    ))
            except Exception as e:
                logger.error(f"获取群组失败: {e}")

        return groups

    def get_messages(
        self,
        talker_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Message]:
        """获取消息"""
        messages = []
        for conn in self.connections:
            try:
                cursor = conn.cursor()

                query = "SELECT MsgSvrID, StrTalker, StrContent, Type, IsSender, CreateTime FROM MSG WHERE StrTalker = ?"
                params = [talker_id]

                if start_time:
                    query += " AND CreateTime >= ?"
                    params.append(int(start_time.timestamp() * 1000))

                if end_time:
                    query += " AND CreateTime <= ?"
                    params.append(int(end_time.timestamp() * 1000))

                query += " ORDER BY CreateTime"

                if limit:
                    query += " LIMIT ?"
                    params.append(limit)

                cursor.execute(query, params)

                for row in cursor.fetchall():
                    msg_id, talker, content, msg_type, is_sender, create_time = row
                    messages.append(Message(
                        id=str(msg_id),
                        platform="wechat",
                        talker_id=talker,
                        sender_id="me" if is_sender else talker,
                        content=content or "",
                        msg_type=self._map_message_type(msg_type),
                        timestamp=datetime.fromtimestamp(create_time / 1000) if create_time else datetime.now(),
                        is_sender=bool(is_sender)
                    ))

            except Exception as e:
                logger.error(f"获取消息失败: {e}")

        return messages

    def get_message_count(self, talker_id: str) -> int:
        """获取消息数量"""
        total = 0
        for conn in self.connections:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM MSG WHERE StrTalker = ?", (talker_id,))
                total += cursor.fetchone()[0]
            except Exception as e:
                logger.error(f"获取消息数量失败: {e}")
        return total

    def _map_message_type(self, wechat_type: int) -> str:
        """映射微信消息类型到统一类型"""
        type_map = {
            1: 'text',
            3: 'image',
            34: 'voice',
            43: 'video',
            47: 'emoji',
            49: 'file',
        }
        return type_map.get(wechat_type, 'unknown')


# ============================================================================
# 平台管理器
# ============================================================================

class PlatformManager:
    """平台管理器"""

    def __init__(self):
        self.adapters: Dict[str, PlatformAdapter] = {}

    def register_adapter(self, adapter: PlatformAdapter):
        """注册平台适配器"""
        platform_name = adapter.get_platform_name()
        self.adapters[platform_name] = adapter
        logger.info(f"注册平台适配器: {platform_name}")

    def get_adapter(self, platform: str) -> Optional[PlatformAdapter]:
        """获取平台适配器"""
        return self.adapters.get(platform)

    def get_all_platforms(self) -> List[str]:
        """获取所有已注册的平台"""
        return list(self.adapters.keys())

    def connect_all(self) -> Dict[str, bool]:
        """连接所有平台"""
        results = {}
        for platform, adapter in self.adapters.items():
            results[platform] = adapter.connect()
            if results[platform]:
                logger.info(f"平台 {platform} 连接成功")
            else:
                logger.error(f"平台 {platform} 连接失败")
        return results

    def disconnect_all(self):
        """断开所有平台连接"""
        for adapter in self.adapters.values():
            adapter.disconnect()

    def get_all_contacts(self) -> List[Contact]:
        """获取所有平台的联系人"""
        contacts = []
        for adapter in self.adapters.values():
            contacts.extend(adapter.get_contacts())
        return contacts

    def get_all_groups(self) -> List[Group]:
        """获取所有平台的群组"""
        groups = []
        for adapter in self.adapters.values():
            groups.extend(adapter.get_groups())
        return groups

    def get_all_messages(
        self,
        talker_id: str,
        platform: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Message]:
        """获取消息（可指定平台）"""
        if platform:
            adapter = self.get_adapter(platform)
            if adapter:
                return adapter.get_messages(talker_id, start_time, end_time, limit)
            return []

        # 从所有平台获取
        messages = []
        for adapter in self.adapters.values():
            messages.extend(adapter.get_messages(talker_id, start_time, end_time, limit))

        # 按时间排序
        messages.sort(key=lambda m: m.timestamp)
        return messages

    def export_to_json(self, output_path: Path):
        """导出所有数据到JSON"""
        data = {
            'platforms': self.get_all_platforms(),
            'contacts': [c.to_dict() for c in self.get_all_contacts()],
            'groups': [g.to_dict() for g in self.get_all_groups()],
            'exported_at': datetime.now().isoformat()
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"数据已导出到: {output_path}")


# ============================================================================
# 示例使用
# ============================================================================

def main():
    """示例：使用多平台框架"""
    logger.info("=" * 60)
    logger.info("多平台消息分析框架示例")
    logger.info("=" * 60)

    # 创建平台管理器
    manager = PlatformManager()

    # 注册微信适配器
    base_dir = Path(__file__).parent
    db_dir = base_dir / 'output' / 'decrypted_db' / 'Multi'
    msg_dbs = list(db_dir.glob('MSG*.db'))

    # 查找联系人数据库
    contact_db = base_dir / 'output' / 'decrypted_db' / 'MicroMsg.db'

    if msg_dbs:
        wechat_adapter = WeChatAdapter(msg_dbs, contact_db if contact_db.exists() else None)
        manager.register_adapter(wechat_adapter)
    else:
        logger.warning("未找到微信数据库")

    # 连接所有平台
    logger.info("\n连接平台...")
    results = manager.connect_all()

    # 获取统计信息
    logger.info("\n获取统计信息...")
    contacts = manager.get_all_contacts()
    groups = manager.get_all_groups()

    logger.info(f"总联系人数: {len(contacts)}")
    logger.info(f"总群组数: {len(groups)}")

    # 导出数据
    output_dir = base_dir / 'output' / 'multi_platform'
    output_dir.mkdir(parents=True, exist_ok=True)

    export_path = output_dir / 'platform_data.json'
    manager.export_to_json(export_path)

    # 断开连接
    manager.disconnect_all()

    logger.info("=" * 60)
    logger.info("完成！")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
