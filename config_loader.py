# -*- coding: utf-8 -*-
"""
Pipeline 统一配置加载器 — 从 pipeline.yaml 读取所有配置

替代 business_channels.py 中的硬编码映射。
提供与旧 API 兼容的函数接口，确保现有脚本零改动即可迁移。
"""

from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None

_PIPELINE_YAML = Path(__file__).parent / "pipeline.yaml"

_cache: Optional[dict] = None


def _load_yaml() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if yaml is None:
        raise ImportError("PyYAML not installed. Run: pip install pyyaml")
    with open(_PIPELINE_YAML, "r", encoding="utf-8") as f:
        _cache = yaml.safe_load(f)
    return _cache


def reload():
    """Force reload pipeline.yaml (use after editing config)."""
    global _cache
    _cache = None
    return _load_yaml()


def get_raw_config() -> dict:
    """Return the full parsed pipeline.yaml dict."""
    return _load_yaml()


# ---- Project queries ----

def get_active_projects() -> Dict[str, dict]:
    """Return {project_name: project_config} for all active projects."""
    cfg = _load_yaml()
    return {k: v for k, v in cfg.get("projects", {}).items() if v.get("status") == "active"}


def get_all_projects() -> Dict[str, dict]:
    """Return all projects including completed ones."""
    return _load_yaml().get("projects", {})


def get_project(name: str) -> Optional[dict]:
    """Get a single project's config by name."""
    return _load_yaml().get("projects", {}).get(name)


def is_project_active(name: str) -> bool:
    """Check if a project is active."""
    proj = get_project(name)
    return proj is not None and proj.get("status") == "active"


# ---- Channel queries (replaces business_channels.py) ----

def _build_channel_map() -> Dict[str, dict]:
    """Build {channel_id: {project, name, sender_whitelist}} for active projects only."""
    result = {}
    for proj_name, proj_cfg in get_active_projects().items():
        for ch in proj_cfg.get("channels", []):
            result[ch["id"]] = {
                "project": proj_name,
                "name": ch.get("name", ""),
                "sender_whitelist": ch.get("sender_whitelist", []),
            }
    return result


def get_business_channels() -> List[str]:
    """Return list of all active business channel ids. Compatible with business_channels.py."""
    return list(_build_channel_map().keys())


def channel_to_project(channel_id: str) -> Optional[str]:
    """Return kanban project name for a channel, or None. Compatible with business_channels.py."""
    cmap = _build_channel_map()
    entry = cmap.get(channel_id)
    return entry["project"] if entry else None


def is_sender_allowed(channel_id: str, sender_wxid: str) -> bool:
    """Check if a sender's message in a channel should be considered.

    Compatible with business_channels.py.
    """
    cmap = _build_channel_map()
    entry = cmap.get(channel_id)
    if entry is None:
        return True  # channel not configured: allow
    wl = entry.get("sender_whitelist")
    if not wl:
        return True  # no whitelist: allow all
    return sender_wxid in wl


# ---- Keyword mapping (replaces auto_pipeline.py project_mapping) ----

def get_keyword_mapping() -> Dict[str, List[str]]:
    """Return {project_name: [keywords]} for active projects only.

    Replaces the hardcoded project_mapping in auto_pipeline.py.
    """
    result = {}
    for proj_name, proj_cfg in get_active_projects().items():
        kws = proj_cfg.get("keywords", [])
        if kws:
            result[proj_name] = kws
    return result


# ---- Pipeline settings ----

def get_pipeline_config() -> dict:
    """Return the pipeline: section of the config."""
    return _load_yaml().get("pipeline", {})


def get_message_fetch_config() -> dict:
    return get_pipeline_config().get("message_fetch", {})


def get_llm_config() -> dict:
    return get_pipeline_config().get("llm_analysis", {})


def get_threading_config() -> dict:
    return get_pipeline_config().get("threading", {})


def get_dedup_config() -> dict:
    return get_pipeline_config().get("dedup", {})


def get_runtime_config() -> dict:
    return get_pipeline_config().get("runtime", {})


def get_kanban_config() -> dict:
    return get_pipeline_config().get("kanban", {})


def get_safe_tags() -> set:
    return set(get_runtime_config().get("safe_tags", []))


def get_approval_tags() -> set:
    return set(get_runtime_config().get("approval_tags", []))


def decide_approval(tags: list) -> bool:
    """Auto-decide require_approval based on tags. Replaces runtime_starter.decide_approval."""
    tags_set = set(tags or [])
    if tags_set & get_approval_tags():
        return True
    if tags_set <= get_safe_tags():
        return False
    return True


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    print("=== Pipeline 配置概览 ===\n")

    print("活跃项目:")
    for name, cfg in get_active_projects().items():
        channels = [ch["name"] for ch in cfg.get("channels", [])]
        kws = cfg.get("keywords", [])
        print(f"  {name}: channels={channels}, keywords={kws}")

    print(f"\n已完成项目: {[k for k, v in get_all_projects().items() if v.get('status') == 'completed']}")

    print(f"\n业务渠道数: {len(get_business_channels())}")
    print(f"关键词映射项目数: {len(get_keyword_mapping())}")

    print(f"\nPipeline 设置:")
    print(f"  消息拉取: {get_message_fetch_config().get('hours')}h, skip_self={get_message_fetch_config().get('skip_self')}")
    print(f"  线程聚合: enabled={get_threading_config().get('enabled')}, window={get_threading_config().get('window_minutes')}min")
    print(f"  LLM 阈值: {get_llm_config().get('threshold')}")
    print(f"  去重上限: {get_dedup_config().get('max_tracked')}")
    print(f"  安全tags: {get_safe_tags()}")
    print(f"  审批tags: {get_approval_tags()}")
