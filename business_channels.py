# -*- coding: utf-8 -*-
"""Business chatroom whitelist + project mapping."""

# id (wxid_xxx for private, xxx@chatroom for group) -> kanban project name
CHANNEL_TO_PROJECT = {
    "49734720477@chatroom": "ai-zs",          # 4.21ai训练管理 (legal doc generator)
    "wxid_tm60ob3bb94x22": "ai-zs",           # 编程仝芷硕(报价合适) (ai-zs customer contact)
    "wxid_5pppo6f5tpgz22": "travel-sentiment-analysis",  # 风临野
    "wxid_7070920730612": "MCE",              # 烨林 (MCE crawler)
    "54026338684@chatroom": "travel-sentiment-analysis",  # 3-person group
    "wxid_xi8r819u9oso22": "wordpress-decoration",  # 密码机
    "44601760933@chatroom": "xiaozhan-emoji-generator",  # 肖战表情包
}


def get_business_channels():
    """Return list of all business channel ids (groups + privates)."""
    return list(CHANNEL_TO_PROJECT.keys())


def channel_to_project(channel_id):
    """Return kanban project name for a chatroom/wxid, or None if unknown."""
    return CHANNEL_TO_PROJECT.get(channel_id)
