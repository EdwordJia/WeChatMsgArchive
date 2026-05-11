"""
MCP 工具定义
"""
from typing import Any, Dict, List
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from .database import WeChatDatabase


class WeChatTools:
    """微信数据 MCP 工具集"""

  def __init__(self, db_path: str = None):
        self.db = WeChatDatabase(db_path)

    def search_messages(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        搜索消息内容

        参数:
            keyword (str): 搜索关键词
            limit (int, optional): 返回数量限制，默认100
            days (int, optional): 最近N天，默认7天
        """
        keyword = arguments.get('keyword')
        if not keyword:
            return {'error': '缺少参数: keyword'}

        limit = arguments.get('limit', 100)
        days = arguments.get('days', 7)
        since_time = int((datetime.now() - timedelta(days=days)).timestamp())

        try:
            messages = self.db.search_messages(keyword, limit, since_time)
            return {
                'success': True,
                'count': len(messages),
                'messages': messages
            }
        except Exception as e:
            return {'error': str(e)}

    def get_contact_messages(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取指定联系人的消息

        参数:
            wxid (str): 微信ID
            days (int, optional): 最近N天，默认7天
            limit (int, optional): 返回数量限制，默认100
        """
        wxid = arguments.get('wxid')
        if not wxid:
            return {'error': '缺少参数: wxid'}

        days = arguments.get('days', 7)
        limit = arguments.get('limit', 100)

        try:
            messages = self.db.get_contact_messages(wxid, days, limit)
            return {
                'success': True,
                'wxid': wxid,
                'count': len(messages),
                'messages': messages
            }
        except Exception as e:
            return {'error': str(e)}

    def get_group_messages(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取群聊消息

        参数:
            group_id (str): 群聊ID
            days (int, optional): 最近N天，默认7天
            limit (int, optional): 返回数量限制，默认100
            sender_wxid (str, optional): 发送者wxid，用于筛选特定成员
        """
        group_id = arguments.get('group_id')
        if not group_id:
            return {'error': '缺少参数: group_id'}

        days = arguments.get('days', 7)
        limit = arguments.get('limit', 100)
        sender_wxid = arguments.get('sender_wxid')

        try:
            messages = self.db.get_group_messages(group_id, days, limit, sender_wxid)
            return {
                'success': True,
                'group_id': group_id,
                'count': len(messages),
                'messages': messages
            }
        except Exception as e:
            return {'error': str(e)}

    def search_by_time_range(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        按时间范围查询消息

        参数:
            start_time (int): 开始时间戳
            end_time (int): 结束时间戳
            talker_id (str, optional): 对话者ID
            limit (int, optional): 返回数量限制，默认100
        """
        start_time = arguments.get('start_time')
        end_time = arguments.get('end_time')

        if not start_time or not end_time:
            return {'error': '缺少参数: start_time 或 end_time'}

        talker_id = arguments.get('talker_id')
        limit = arguments.get('limit', 100)

        try:
            messages = self.db.search_by_time_range(start_time, end_time, talker_id, limit)
            return {
                'success': True,
                'count': len(messages),
                'messages': messages
            }
        except Exception as e:
            return {'error': str(e)}

    def get_contact_info(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取联系人信息

        参数:
            wxid (str, optional): 微信ID
            nickname (str, optional): 昵称
        """
        wxid = arguments.get('wxid')
        nickname = arguments.get('nickname')

        if not wxid and not nickname:
            return {'error': '需要提供 wxid 或 nickname 参数'}

        try:
            contacts = self.db.get_contact_info(wxid, nickname)
            return {
                'success': True,
                'count': len(contacts),
                'contacts': contacts
            }
        except Exception as e:
            return {'error': str(e)}

    def get_all_groups(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取所有群聊列表

        参数: 无
        """
        try:
            groups = self.db.get_all_groups()
            return {
                'success': True,
                'count': len(groups),
                'groups': groups
            }
        except Exception as e:
            return {'error': str(e)}

    def sync_messages(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        同步微信消息到索引数据库

        参数:
            incremental (bool, optional): 是否增量同步，默认True
        """
        incremental = arguments.get('incremental', True)

        try:
            result = self.db.sync_data(incremental)
            return result
        except Exception as e:
            return {'error': str(e)}

    def get_sync_status(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取数据同步状态

        参数: 无
        """
        try:
            result = self.db.get_sync_status()
            return result
        except Exception as e:
            return {'error': str(e)}


# 工具定义（MCP 格式）
TOOLS = [
    {
        "name": "search_messages",
        "description": "搜索微信消息内容，支持关键词搜索和时间范围过滤",
        "inputSchema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量限制，默认100",
                    "default": 100
                },
                "days": {
                    "type": "integer",
                    "description": "最近N天，默认7天",
                    "default": 7
                }
            },
            "required": ["keyword"]
        }
    },
    {
        "name": "get_contact_messages",
        "description": "获取指定联系人的聊天消息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "wxid": {
                    "type": "string",
                    "description": "微信ID"
                },
                "days": {
                    "type": "integer",
                    "description": "最近N天，默认7天",
                    "default": 7
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量限制，默认100",
                    "default": 100
                }
            },
            "required": ["wxid"]
        }
    },
    {
        "name": "get_group_messages",
        "description": "获取群聊消息，可选择筛选特定成员的消息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "group_id": {
                    "type": "string",
                    "description": "群聊ID（通常以@chatroom结尾）"
                },
                "days": {
                    "type": "integer",
                    "description": "最近N天，默认7天",
                    "default": 7
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量限制，默认100",
                    "default": 100
                },
                "sender_wxid": {
                    "type": "string",
                    "description": "发送者wxid（可选），用于筛选特定成员的消息"
                }
            },
            "required": ["group_id"]
        }
    },
    {
        "name": "search_by_time_range",
        "description": "按时间范围查询消息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "start_time": {
                    "type": "integer",
                    "description": "开始时间戳（Unix timestamp）"
                },
                "end_time": {
                    "type": "integer",
                    "description": "结束时间戳（Unix timestamp）"
                },
                "talker_id": {
                    "type": "string",
                    "description": "对话者ID（可选）"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量限制，默认100",
                    "default": 100
                }
            },
            "required": ["start_time", "end_time"]
        }
    },
    {
        "name": "get_contact_info",
        "description": "获取联系人信息，支持通过wxid或昵称查询",
        "inputSchema": {
            "type": "object",
            "properties": {
                "wxid": {
                    "type": "string",
                    "description": "微信ID"
                },
                "nickname": {
                    "type": "string",
                    "description": "昵称（支持模糊搜索）"
                }
            }
        }
    },
    {
        "name": "get_all_groups",
        "description": "获取所有群聊列表",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "sync_messages",
        "description": "同步微信消息到索引数据库，支持增量同步和全量同步",
        "inputSchema": {
            "type": "object",
            "properties": {
                "incremental": {
                    "type": "boolean",
                    "description": "是否增量同步（默认True），False为全量同步",
                    "default": True
                }
            }
        }
    },
    {
        "name": "get_sync_status",
        "description": "获取数据同步状态，包括上次同步时间、消息总数等信息",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]
