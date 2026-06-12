# -*- coding: utf-8 -*-
"""Business chatroom whitelist + project mapping.

DEPRECATED: 所有配置已迁移到 pipeline.yaml + config_loader.py
此文件保留仅为向后兼容，所有函数委托给 config_loader。
"""

from config_loader import (
    get_business_channels,
    channel_to_project,
    is_sender_allowed,
)


# 旧代码可能直接 import 这些常量，保留为属性代理
def _proxy_channel_to_project():
    """Build CHANNEL_TO_PROJECT dict from config_loader for compatibility."""
    from config_loader import _build_channel_map
    cmap = _build_channel_map()
    return {cid: entry["project"] for cid, entry in cmap.items()}


def _proxy_sender_whitelist():
    """Build CHANNEL_SENDER_WHITELIST dict from config_loader for compatibility."""
    from config_loader import _build_channel_map
    cmap = _build_channel_map()
    result = {}
    for cid, entry in cmap.items():
        wl = entry.get("sender_whitelist", [])
        if wl:
            result[cid] = wl
    return result


# Lazy proxies — evaluated on first access
CHANNEL_TO_PROJECT = _proxy_channel_to_project()
CHANNEL_SENDER_WHITELIST = _proxy_sender_whitelist()