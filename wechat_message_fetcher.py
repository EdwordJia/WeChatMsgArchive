# -*- coding: utf-8 -*-
"""Legacy wrapper — delegates to wechat_msg_reader (correct MSG table)."""

from wechat_msg_reader import (
    WeChatMessageFetcher as _WeChatMessageFetcher,
    fetch_recent_messages,
    get_chatroom_list,
)


class WeChatMessageFetcher(_WeChatMessageFetcher):
    pass


__all__ = ["WeChatMessageFetcher", "fetch_recent_messages", "get_chatroom_list"]
