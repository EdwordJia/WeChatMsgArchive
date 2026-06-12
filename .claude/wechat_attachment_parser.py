# -*- coding: utf-8 -*-
"""Parse WeChat multimodal message XML attachments and match local files."""

import hashlib
import re
from pathlib import Path
from typing import Dict, List, Optional

# WeChat message type mapping
MSG_TYPE_MAP = {
    1: "text",
    3: "image",
    34: "voice",
    43: "video",
    47: "emoji",
    49: "app",
    10000: "system",
}


def _extract_xml_attr(xml_text: str, tag: str, attr: str) -> Optional[str]:
    """Extract attribute value from XML tag."""
    if not xml_text:
        return None
    pattern = rf'<{tag}\s+[^>]*{attr}=["\']([^"\']+)["\']'
    m = re.search(pattern, xml_text, re.IGNORECASE)
    return m.group(1) if m else None


def _extract_xml_text(xml_text: str, tag: str) -> Optional[str]:
    """Extract text content between XML tags."""
    if not xml_text:
        return None
    pattern = rf'<{tag}[^>]*>([^<]*)</{tag}>'
    m = re.search(pattern, xml_text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def _extract_voice_trans(xml_text: str) -> Optional[str]:
    """Extract voice transcription from WeChat XML."""
    if not xml_text:
        return None
    # WeChat voice transcription format: <voicetrans transtext="...">
    m = re.search(r'transtext=["\']([^"\']+)["\']', xml_text)
    if m:
        return m.group(1)
    # Alternative format
    m = re.search(r'<voicetrans[^>]*>([^<]*)</voicetrans>', xml_text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _extract_all_attrs(xml_text: str, tag: str) -> Dict[str, str]:
    """Extract all attributes from an XML tag."""
    if not xml_text:
        return {}
    pattern = rf'<{tag}\s+([^>]+)>'
    m = re.search(pattern, xml_text, re.IGNORECASE)
    if not m:
        return {}
    attrs = {}
    attr_text = m.group(1)
    for am in re.finditer(r'(\w+)=["\']([^"\']+)["\']', attr_text):
        attrs[am.group(1).lower()] = am.group(2)
    return attrs


def _find_image_by_md5(chatroom_id: str, md5: str, db_dir: str = "output/decrypted_db") -> Optional[str]:
    """Find local image file by md5 hash in group_images directory."""
    if not md5:
        return None
    md5_lower = md5.lower()
    img_dir = Path(db_dir).parent / "group_images" / chatroom_id
    if not img_dir.exists():
        return None
    # Check if any file's md5 matches
    for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        for f in img_dir.glob(f"*{ext}"):
            # Fast check: filename itself might be the md5
            if md5_lower in f.stem.lower():
                return str(f)
    return None


def _compute_file_md5(path: Path) -> str:
    """Compute md5 of a file."""
    h = hashlib.md5()
    with open(path, "rb") as fp:
        while True:
            chunk = fp.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest().lower()


def _find_image_by_content_md5(chatroom_id: str, xml_md5: str, db_dir: str = "output/decrypted_db") -> Optional[str]:
    """Find local image by computing file md5 and matching against XML md5."""
    if not xml_md5:
        return None
    xml_md5_lower = xml_md5.lower()
    img_dir = Path(db_dir).parent / "group_images" / chatroom_id
    if not img_dir.exists():
        return None
    # Build a cache of md5 -> file path for this directory
    cache_file = img_dir / ".md5_cache.json"
    cache = {}
    if cache_file.exists():
        try:
            import json
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    # Check cache first
    if xml_md5_lower in cache:
        cached_path = Path(cache[xml_md5_lower])
        if cached_path.exists():
            return str(cached_path)
    # Compute md5 for files not in cache
    for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
        for f in img_dir.glob(f"*{ext}"):
            if f.name == ".md5_cache.json":
                continue
            try:
                file_md5 = _compute_file_md5(f)
                cache[file_md5] = str(f)
                if file_md5 == xml_md5_lower:
                    # Save cache before returning
                    try:
                        cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                    except Exception:
                        pass
                    return str(f)
            except Exception:
                continue
    # Save cache even if no match found
    try:
        cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return None


def parse_attachments(msg_type: int, content: str, chatroom_id: str = "", db_dir: str = "output/decrypted_db") -> List[Dict]:
    """Parse WeChat message attachments from XML content.

    Returns a list of attachment dicts with keys:
    - type: "image" | "voice" | "video" | "file" | "emoji" | "link" | "unknown"
    - subtype: specific subtype (e.g., "appmsg" for type 49)
    - md5: file md5 hash (for images)
    - local_path: matched local file path (if found)
    - description: human-readable description
    - meta: dict of additional metadata
    """
    attachments = []
    if not content:
        return attachments

    xml = content.strip()
    if not xml.startswith("<"):
        return attachments

    msg_type_name = MSG_TYPE_MAP.get(msg_type, f"type{msg_type}")

    # Image (Type 3)
    if msg_type == 3:
        attrs = _extract_all_attrs(xml, "img")
        md5 = attrs.get("md5", "")
        length = attrs.get("length", "")
        desc = f"[图片]"
        if md5:
            desc += f" md5={md5[:16]}..."
        local_path = _find_image_by_content_md5(chatroom_id, md5, db_dir)
        att = {
            "type": "image",
            "md5": md5,
            "local_path": local_path,
            "description": desc,
            "meta": {k: v for k, v in attrs.items() if k in ("length", "cdnthumburl", "aeskey", "cdnthumblength")},
        }
        attachments.append(att)

    # Voice (Type 34)
    elif msg_type == 34:
        attrs = _extract_all_attrs(xml, "voicemsg")
        voice_len = attrs.get("voicelength", "")
        trans = _extract_voice_trans(xml)
        desc = "[语音]"
        if voice_len:
            try:
                seconds = int(voice_len) / 1000
                desc += f" {seconds:.1f}秒"
            except Exception:
                pass
        if trans:
            desc += f" 转文字: {trans}"
        att = {
            "type": "voice",
            "description": desc,
            "meta": {k: v for k, v in attrs.items() if k in ("voicelength", "clientmsgid", "fromusername")},
            "transcription": trans,
        }
        attachments.append(att)

    # Video (Type 43)
    elif msg_type == 43:
        attrs = _extract_all_attrs(xml, "videomsg")
        desc = "[视频]"
        att = {
            "type": "video",
            "description": desc,
            "meta": attrs,
        }
        attachments.append(att)

    # Emoji (Type 47)
    elif msg_type == 47:
        attrs = _extract_all_attrs(xml, "emoji")
        desc = "[表情包]"
        att = {
            "type": "emoji",
            "description": desc,
            "meta": attrs,
        }
        attachments.append(att)

    # App / File / Link (Type 49)
    elif msg_type == 49:
        app_attrs = _extract_all_attrs(xml, "appmsg")
        app_type = app_attrs.get("type", "")
        title = _extract_xml_text(xml, "title") or ""
        des = _extract_xml_text(xml, "des") or ""
        url = _extract_xml_text(xml, "url") or ""

        if app_type == "6":
            desc = f"[文件] {title}" if title else "[文件]"
            att_type = "file"
        elif app_type == "5":
            desc = f"[链接] {title}" if title else "[链接]"
            att_type = "link"
        elif app_type == "33" or app_type == "36":
            desc = f"[小程序] {title}" if title else "[小程序]"
            att_type = "miniprogram"
        elif app_type == "19":
            desc = f"[合并转发聊天记录] {title}" if title else "[合并转发聊天记录]"
            att_type = "forward"
        else:
            desc = f"[应用消息{type}] {title}" if title else f"[应用消息{type}]"
            att_type = "app"

        att = {
            "type": att_type,
            "description": desc,
            "meta": {"app_type": app_type, "title": title, "des": des, "url": url},
        }
        attachments.append(att)

    # System message (Type 10000)
    elif msg_type == 10000:
        desc = f"[系统消息] {content[:80]}"
        att = {
            "type": "system",
            "description": desc,
            "meta": {},
        }
        attachments.append(att)

    return attachments


def summarize_attachments(attachments: List[Dict]) -> str:
    """Create a human-readable summary of attachments for task body."""
    if not attachments:
        return ""
    lines = []
    for att in attachments:
        desc = att.get("description", "")
        local_path = att.get("local_path")
        if local_path:
            desc += f" [本地文件: {local_path}]"
        lines.append(f"- {desc}")
    return "\n".join(lines)


def get_reference_image_paths(attachments: List[Dict]) -> List[str]:
    """Get list of local image file paths from attachments."""
    return [att["local_path"] for att in attachments if att.get("type") == "image" and att.get("local_path")]


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    # Test with sample data
    test_xml = '<?xml version="1.0"?><msg><img md5="a1b2c3d4e5f6" length="12345" cdnthumburl="http://example.com" aeskey="abc123"/></msg>'
    result = parse_attachments(3, test_xml, "49584724187@chatroom")
    print("Image parse:", result)

    voice_xml = '<msg><voicemsg voicelength="5432" clientmsgid="abc" fromusername="wxid_xxx"/></msg>'
    result2 = parse_attachments(34, voice_xml)
    print("Voice parse:", result2)
