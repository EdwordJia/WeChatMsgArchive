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



# Per-channel sender whitelist (only these wxids' messages count as requirements)
# Empty list = no restriction (any non-ME counts)
CHANNEL_SENDER_WHITELIST = {
    # 4.21ai训练管理：客户/产品对接人发的才是真需求
    "49734720477@chatroom": ["25984982369994080@openim"],  # 刘皓明（决策方），通过 BytesExtra 解析得到
    # private chats: only the contact themselves
    "wxid_tm60ob3bb94x22": ["wxid_tm60ob3bb94x22"],
    "wxid_5pppo6f5tpgz22": ["wxid_5pppo6f5tpgz22"],
    "wxid_7070920730612": ["wxid_7070920730612"],
    "wxid_xi8r819u9oso22": ["wxid_xi8r819u9oso22"],
}


def is_sender_allowed(channel_id, sender_wxid):
    """Check if a sender's message in a channel should be considered.

    Returns True if sender is whitelisted or no whitelist defined."""
    wl = CHANNEL_SENDER_WHITELIST.get(channel_id)
    if wl is None:
        return True  # channel not configured: allow
    if not wl:
        return True  # empty list: no per-sender filter
    return sender_wxid in wl
