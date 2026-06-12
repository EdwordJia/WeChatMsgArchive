# -*- coding: utf-8 -*-
"""Group WeChat messages into conversation threads for requirement analysis."""

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional


def _timestamp(msg: Dict) -> int:
    ts = msg.get("timestamp")
    if isinstance(ts, (int, float)):
        return int(ts)
    time_text = msg.get("time")
    if time_text:
        try:
            return int(datetime.strptime(time_text, "%Y-%m-%d %H:%M:%S").timestamp())
        except ValueError:
            return 0
    return 0


def _channel(msg: Dict) -> str:
    return msg.get("chatroom") or msg.get("sender_wxid") or "unknown"


@lru_cache(maxsize=1)
def _wechat_dir() -> str:
    info_path = Path("output/decrypted_db/info.json")
    if not info_path.exists():
        return ""
    try:
        return json.loads(info_path.read_text(encoding="utf-8")).get("wx_dir") or ""
    except Exception:
        return ""


def _msg_attach_dir(chatroom: str) -> Path:
    wx_dir = _wechat_dir()
    if not wx_dir or not chatroom:
        return Path()
    attach_hash = hashlib.md5(chatroom.encode()).hexdigest()
    return Path(wx_dir) / "FileStorage" / "MsgAttach" / attach_hash


def _find_local_attachment(chatroom: str, identifiers: List[str], suffixes: tuple[str, ...] = ()) -> Optional[str]:
    base = _msg_attach_dir(chatroom)
    if not base.exists():
        return None
    ids = [item.lower() for item in identifiers if item]
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if suffixes and path.suffix.lower() not in suffixes:
            continue
        if any(item in name for item in ids):
            return str(path.resolve())
    return None


def _parse_xml(content: str) -> Optional[ET.Element]:
    try:
        return ET.fromstring(content.strip())
    except ET.ParseError:
        return None


def _xml_attr(content: str, tag: str, name: str) -> str:
    root = _parse_xml(content)
    if root is not None:
        node = root.find(".//" + tag)
        if node is not None:
            return node.get(name) or ""
    match = re.search(r"<" + re.escape(tag) + r"\b[^>]*\b" + re.escape(name) + r'="([^"]*)"', content)
    return match.group(1) if match else ""


def _voice_trans_text(content: str) -> str:
    return _xml_attr(content, "voicetrans", "transtext")


def _meaningful_content(msg: Dict) -> Optional[str]:
    content = (msg.get("content") or "").strip()
    if not content or content == "[无文本内容]":
        return None
    lower = content.lower()
    if "<voicetrans" in lower:
        text = _voice_trans_text(content).strip()
        return "语音转文字：" + text if text else None
    if lower.startswith("<?xml") or lower.startswith("<msg"):
        return None
    if "<img " in lower or "<videomsg" in lower or "<voicemsg" in lower or "<appmsg" in lower:
        return None
    if content.startswith("<revokemsg>"):
        return None
    return content


def _evidence_line(msg: Dict) -> Optional[str]:
    sender = msg.get("sender") or msg.get("sender_wxid") or "未知"
    time_text = msg.get("time") or ""
    content = (msg.get("content") or "").strip()
    msg_type = msg.get("msg_type") or msg.get("type") or ""
    chatroom = msg.get("chatroom") or ""
    if not content or content == "[无文本内容]":
        return f"[{time_text}] {sender}: 无文本/附件消息(type={msg_type})"
    lower = content.lower()
    if "<videomsg" in lower:
        md5 = _xml_attr(content, "videomsg", "md5")
        newmd5 = _xml_attr(content, "videomsg", "newmd5")
        playlength = _xml_attr(content, "videomsg", "playlength")
        size = _xml_attr(content, "videomsg", "length")
        local_path = _find_local_attachment(chatroom, [md5, newmd5], (".mp4", ".mov", ".dat"))
        parts = ["视频证据"]
        if playlength:
            parts.append(playlength + "秒")
        if size:
            parts.append("size=" + size)
        if md5:
            parts.append("md5=" + md5)
        parts.append("路径=" + local_path if local_path else "本地视频文件未定位")
        return f"[{time_text}] {sender}: " + "，".join(parts)
    if "<voicemsg" in lower:
        length = _xml_attr(content, "voicemsg", "voicelength")
        text = _voice_trans_text(content).strip()
        parts = ["语音证据"]
        if length:
            parts.append("时长=" + length)
        if text:
            parts.append("转写=" + text)
        return f"[{time_text}] {sender}: " + "，".join(parts)
    if "<appmsg" in lower:
        title_match = re.search(r"<title>(.*?)</title>", content, re.S)
        fileext = _xml_attr(content, "appattach", "fileext")
        file_name = title_match.group(1).strip() if title_match else ""
        parts = ["文件/小程序证据"]
        if file_name:
            parts.append("文件名=" + file_name)
        if fileext:
            parts.append("扩展名=" + fileext)
        return f"[{time_text}] {sender}: " + "，".join(parts)
    if "<img " in lower or lower.startswith("<?xml") or lower.startswith("<msg"):
        md5 = _xml_attr(content, "img", "md5")
        local_path = _find_local_attachment(chatroom, [md5], (".jpg", ".jpeg", ".png", ".gif", ".dat"))
        parts = ["图片/XML证据"] if not md5 else ["图片证据"]
        if md5:
            parts.append("md5=" + md5)
        parts.append("路径=" + local_path if local_path else "本地图片文件未定位")
        return f"[{time_text}] {sender}: " + "，".join(parts)
    if content.startswith("<revokemsg>"):
        return f"[{time_text}] {sender}: 撤回消息证据"
    return None


def _format_line(msg: Dict) -> Optional[str]:
    content = _meaningful_content(msg)
    if not content:
        return None
    sender = msg.get("sender") or msg.get("sender_wxid") or "未知"
    time_text = msg.get("time") or ""
    return f"[{time_text}] {sender}: {content}"


def _thread_content(messages: List[Dict], max_chars: int) -> str:
    lines = [line for msg in messages if (line := _format_line(msg))]
    text = "\n".join(lines)
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _thread_evidence(messages: List[Dict]) -> List[str]:
    return [line for msg in messages if (line := _evidence_line(msg))]


def _source_message(messages: List[Dict]) -> Dict:
    for msg in reversed(messages):
        if _meaningful_content(msg) and msg.get("is_sender") != 1:
            return msg
    for msg in reversed(messages):
        if _meaningful_content(msg):
            return msg
    return messages[-1]


def _new_thread(messages: List[Dict], max_chars: int) -> Dict:
    first = messages[0]
    last = messages[-1]
    source = _source_message(messages)
    evidence = _thread_evidence(messages)
    content = _thread_content(messages, max_chars)
    return {
        "content": content,
        "evidence_summary": evidence,
        "attachment_count": len(evidence),
        "messages": messages,
        "message_count": len(messages),
        "start_time": first.get("time"),
        "end_time": last.get("time"),
        "timestamp": _timestamp(last),
        "chatroom": _channel(first),
        "sender": source.get("sender"),
        "sender_wxid": source.get("sender_wxid"),
        "source_message": source,
    }


def build_threads(messages: List[Dict], window_minutes: int = 30, max_thread_size: int = 10, max_thread_chars: int = 6000) -> List[Dict]:
    """Build conversation threads from raw messages.

    Messages are grouped by channel and time gap. The output shape stays close to
    a message dict so existing analyzers can consume it with minimal changes.
    """
    if not messages:
        return []

    by_channel: Dict[str, List[Dict]] = {}
    for msg in messages:
        by_channel.setdefault(_channel(msg), []).append(msg)

    threads: List[Dict] = []
    max_gap = max(1, window_minutes) * 60
    max_size = max(1, max_thread_size)

    for channel_messages in by_channel.values():
        ordered = sorted(channel_messages, key=_timestamp)
        current: List[Dict] = []
        last_ts = None

        for msg in ordered:
            ts = _timestamp(msg)
            should_flush = False
            if current and last_ts is not None and ts - last_ts > max_gap:
                should_flush = True
            if current and len(current) >= max_size:
                should_flush = True
            if should_flush:
                threads.append(_new_thread(current, max_thread_chars))
                current = []

            current.append(msg)
            last_ts = ts

        if current:
            threads.append(_new_thread(current, max_thread_chars))

    threads.sort(key=lambda item: item.get("timestamp", 0), reverse=True)
    return threads


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    sample = [
        {"content": "这个页面颜色不对", "sender": "客户", "time": "2026-05-29 09:00:00", "timestamp": 1780026000, "chatroom": "demo"},
        {"content": "好的我看下", "sender": "我", "time": "2026-05-29 09:02:00", "timestamp": 1780026120, "chatroom": "demo"},
        {"content": "Logo也换掉", "sender": "客户", "time": "2026-05-29 09:04:00", "timestamp": 1780026240, "chatroom": "demo"},
    ]
    for thread in build_threads(sample):
        print(thread["content"])
