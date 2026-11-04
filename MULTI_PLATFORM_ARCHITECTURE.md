---
id: mod-multi-platform
type: module-design
title: 多平台消息分析框架（PlatformAdapter）
status: draft
parent: arch-overview
---

# 多平台扩展架构设计

生成时间: 2026-04-27

## 概述

本文档描述如何将现有的微信消息分析系统扩展到飞书和企业微信平台，实现统一的多平台消息分析架构。

## 设计目标

1. **平台无关性**: 核心分析逻辑与具体平台解耦
2. **可扩展性**: 易于添加新的平台支持
3. **统一接口**: 提供一致的数据访问和分析接口
4. **性能优化**: 支持并行处理多个平台数据
5. **数据隔离**: 不同平台数据独立存储和管理

## 架构设计

### 1. 分层架构

```
┌─────────────────────────────────────────────────────────┐
│                    应用层 (Application)                  │
│  - 用户画像分析  - 关系图谱  - 项目追踪  - 商机识别    │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                    服务层 (Service)                      │
│  - 分析服务  - 报告服务  - 导出服务  - 缓存服务        │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                  数据访问层 (Data Access)                │
│  - 统一数据接口  - 查询构建器  - 数据映射              │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                  平台适配层 (Adapter)                    │
│  - 微信适配器  - 飞书适配器  - 企业微信适配器          │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                  数据源层 (Data Source)                  │
│  - 微信数据库  - 飞书API  - 企业微信API                │
└─────────────────────────────────────────────────────────┘
```

### 2. 核心组件

#### 2.1 平台适配器接口

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime

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
    def get_contacts(self) -> List[Dict]:
        """获取联系人列表"""
        pass

    @abstractmethod
    def get_groups(self) -> List[Dict]:
        """获取群组列表"""
        pass

    @abstractmethod
    def get_messages(
        self,
        talker_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """获取消息列表"""
        pass

    @abstractmethod
    def get_message_count(self, talker_id: str) -> int:
        """获取消息数量"""
        pass
```

#### 2.2 统一数据模型

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

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
```

#### 2.3 平台管理器

```python
class PlatformManager:
    """平台管理器"""

    def __init__(self):
        self.adapters: Dict[str, PlatformAdapter] = {}

    def register_adapter(self, adapter: PlatformAdapter):
        """注册平台适配器"""
        platform_name = adapter.get_platform_name()
        self.adapters[platform_name] = adapter

    def get_adapter(self, platform: str) -> Optional[PlatformAdapter]:
        """获取平台适配器"""
        return self.adapters.get(platform)

    def get_all_platforms(self) -> List[str]:
        """获取所有已注册的平台"""
        return list(self.adapters.keys())

    def get_all_contacts(self) -> List[Contact]:
        """获取所有平台的联系人"""
        contacts = []
        for adapter in self.adapters.values():
            contacts.extend(adapter.get_contacts())
        return contacts

    def get_all_messages(
        self,
        talker_id: str,
        platform: Optional[str] = None
    ) -> List[Message]:
        """获取消息（可指定平台）"""
        if platform:
            adapter = self.get_adapter(platform)
            if adapter:
                return adapter.get_messages(talker_id)
            return []

        # 从所有平台获取
        messages = []
        for adapter in self.adapters.values():
            messages.extend(adapter.get_messages(talker_id))

        # 按时间排序
        messages.sort(key=lambda m: m.timestamp)
        return messages
```

### 3. 平台实现

#### 3.1 微信适配器

```python
class WeChatAdapter(PlatformAdapter):
    """微信平台适配器"""

    def __init__(self, db_paths: List[Path]):
        self.db_paths = db_paths
        self.connections = []

    def get_platform_name(self) -> str:
        return "wechat"

    def connect(self) -> bool:
        for db_path in self.db_paths:
            conn = sqlite3.connect(db_path)
            self.connections.append(conn)
        return True

    def disconnect(self):
        for conn in self.connections:
            conn.close()
        self.connections = []

    def get_contacts(self) -> List[Contact]:
        contacts = []
        for conn in self.connections:
            cursor = conn.cursor()
            cursor.execute("SELECT UserName, NickName, Remark FROM Contact")
            for row in cursor.fetchall():
                contacts.append(Contact(
                    id=row[0],
                    platform="wechat",
                    name=row[2] or row[1],
                    nickname=row[1]
                ))
        return contacts

    def get_messages(
        self,
        talker_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Message]:
        messages = []
        for conn in self.connections:
            cursor = conn.cursor()

            query = "SELECT * FROM MSG WHERE StrTalker = ?"
            params = [talker_id]

            if start_time:
                query += " AND CreateTime >= ?"
                params.append(int(start_time.timestamp() * 1000))

            if end_time:
                query += " AND CreateTime <= ?"
                params.append(int(end_time.timestamp() * 1000))

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)

            for row in cursor.fetchall():
                messages.append(Message(
                    id=str(row[0]),
                    platform="wechat",
                    talker_id=row[1],
                    sender_id=row[2] if row[3] else talker_id,
                    content=row[4] or "",
                    msg_type=self._map_message_type(row[5]),
                    timestamp=datetime.fromtimestamp(row[6] / 1000),
                    is_sender=bool(row[3])
                ))

        return messages

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
```

#### 3.2 飞书适配器

```python
import requests

class FeishuAdapter(PlatformAdapter):
    """飞书平台适配器"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = None
        self.base_url = "https://open.feishu.cn/open-apis"

    def get_platform_name(self) -> str:
        return "feishu"

    def connect(self) -> bool:
        """获取访问令牌"""
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }

        response = requests.post(url, json=data)
        if response.status_code == 200:
            result = response.json()
            self.access_token = result.get('tenant_access_token')
            return True
        return False

    def disconnect(self):
        self.access_token = None

    def get_contacts(self) -> List[Contact]:
        """获取通讯录"""
        url = f"{self.base_url}/contact/v3/users"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        contacts = []
        page_token = None

        while True:
            params = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token

            response = requests.get(url, headers=headers, params=params)
            if response.status_code != 200:
                break

            result = response.json()
            for user in result.get('data', {}).get('items', []):
                contacts.append(Contact(
                    id=user['user_id'],
                    platform="feishu",
                    name=user['name'],
                    nickname=user.get('nickname'),
                    avatar=user.get('avatar', {}).get('avatar_72')
                ))

            page_token = result.get('data', {}).get('page_token')
            if not page_token:
                break

        return contacts

    def get_messages(
        self,
        talker_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Message]:
        """获取消息历史"""
        url = f"{self.base_url}/im/v1/messages"
        headers = {"Authorization": f"Bearer {self.access_token}"}

        params = {
            "container_id_type": "chat",
            "container_id": talker_id,
            "page_size": limit or 100
        }

        if start_time:
            params["start_time"] = int(start_time.timestamp())
        if end_time:
            params["end_time"] = int(end_time.timestamp())

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            return []

        messages = []
        result = response.json()

        for msg in result.get('data', {}).get('items', []):
            messages.append(Message(
                id=msg['message_id'],
                platform="feishu",
                talker_id=talker_id,
                sender_id=msg['sender']['id'],
                content=msg.get('body', {}).get('content', ''),
                msg_type=msg['msg_type'],
                timestamp=datetime.fromtimestamp(int(msg['create_time']) / 1000),
                is_sender=False  # 需要根据实际情况判断
            ))

        return messages
```

#### 3.3 企业微信适配器

```python
class WorkWeChatAdapter(PlatformAdapter):
    """企业微信平台适配器"""

    def __init__(self, corp_id: str, corp_secret: str):
        self.corp_id = corp_id
        self.corp_secret = corp_secret
        self.access_token = None
        self.base_url = "https://qyapi.weixin.qq.com/cgi-bin"

    def get_platform_name(self) -> str:
        return "work_wechat"

    def connect(self) -> bool:
        """获取访问令牌"""
        url = f"{self.base_url}/gettoken"
        params = {
            "corpid": self.corp_id,
            "corpsecret": self.corp_secret
        }

        response = requests.get(url, params=params)
        if response.status_code == 200:
            result = response.json()
            if result.get('errcode') == 0:
                self.access_token = result.get('access_token')
                return True
        return False

    def disconnect(self):
        self.access_token = None

    def get_contacts(self) -> List[Contact]:
        """获取通讯录"""
        url = f"{self.base_url}/user/list"
        params = {
            "access_token": self.access_token,
            "department_id": 1,  # 根部门
            "fetch_child": 1
        }

        response = requests.get(url, params=params)
        if response.status_code != 200:
            return []

        contacts = []
        result = response.json()

        for user in result.get('userlist', []):
            contacts.append(Contact(
                id=user['userid'],
                platform="work_wechat",
                name=user['name'],
                avatar=user.get('avatar'),
                metadata={'department': user.get('department')}
            ))

        return contacts

    def get_messages(
        self,
        talker_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Message]:
        """企业微信需要通过会话存档API获取消息"""
        # 注意：需要开通会话存档功能
        # 这里提供基本框架，实际实现需要根据企业微信API文档
        return []
```

### 4. 使用示例

```python
# 初始化平台管理器
manager = PlatformManager()

# 注册微信适配器
wechat_adapter = WeChatAdapter(db_paths=[...])
manager.register_adapter(wechat_adapter)

# 注册飞书适配器
feishu_adapter = FeishuAdapter(
    app_id="your_app_id",
    app_secret="your_app_secret"
)
manager.register_adapter(feishu_adapter)

# 注册企业微信适配器
work_wechat_adapter = WorkWeChatAdapter(
    corp_id="your_corp_id",
    corp_secret="your_corp_secret"
)
manager.register_adapter(work_wechat_adapter)

# 连接所有平台
for platform in manager.get_all_platforms():
    adapter = manager.get_adapter(platform)
    adapter.connect()

# 获取所有平台的联系人
all_contacts = manager.get_all_contacts()

# 获取特定平台的消息
wechat_messages = manager.get_all_messages(
    talker_id="some_id",
    platform="wechat"
)

# 获取所有平台的消息（合并）
all_messages = manager.get_all_messages(talker_id="some_id")
```

### 5. 配置管理

```python
# config.yaml
platforms:
  wechat:
    enabled: true
    db_paths:
      - "output/decrypted_db/Multi/MSG0.db"
      - "output/decrypted_db/Multi/MSG1.db"

  feishu:
    enabled: true
    app_id: "cli_xxx"
    app_secret: "xxx"

  work_wechat:
    enabled: false
    corp_id: "xxx"
    corp_secret: "xxx"

analysis:
  cache_enabled: true
  cache_ttl: 3600
  parallel_workers: 4
```

### 6. 数据同步策略

1. **实时同步**: 通过Webhook接收新消息
2. **定时同步**: 定期拉取增量数据
3. **全量同步**: 首次使用时全量导入历史数据

### 7. 扩展点

1. **新平台接入**: 实现PlatformAdapter接口
2. **自定义分析**: 继承基础分析类
3. **数据导出**: 实现Exporter接口
4. **通知推送**: 实现Notifier接口

## 实施计划

### 阶段1: 架构重构（1-2周）
- [ ] 设计并实现统一数据模型
- [ ] 实现平台适配器接口
- [ ] 重构现有微信分析代码为适配器模式

### 阶段2: 飞书集成（2-3周）
- [ ] 实现飞书适配器
- [ ] 测试飞书数据获取
- [ ] 验证分析功能兼容性

### 阶段3: 企业微信集成（2-3周）
- [ ] 实现企业微信适配器
- [ ] 处理会话存档API
- [ ] 测试和优化

### 阶段4: 优化和完善（1-2周）
- [ ] 性能优化
- [ ] 文档完善
- [ ] 用户手册

## 技术栈

- **语言**: Python 3.8+
- **数据库**: SQLite (微信), API (飞书/企业微信)
- **HTTP客户端**: requests
- **配置管理**: PyYAML
- **日志**: logging
- **测试**: pytest

## 注意事项

1. **API限流**: 注意各平台的API调用频率限制
2. **权限管理**: 确保有足够的权限访问数据
3. **数据安全**: 敏感信息加密存储
4. **错误处理**: 完善的异常处理和重试机制
5. **日志审计**: 记录所有数据访问操作

## 总结

通过分层架构和适配器模式，我们可以轻松扩展到多个平台，同时保持核心分析逻辑的稳定性和可维护性。
