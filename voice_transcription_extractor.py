# -*- coding: utf-8 -*-
"""
微信语音消息转录提取模块

从解密的微信数据库中提取语音消息的内置转录文本。
微信 Type=34（语音）消息的 StrContent XML 中包含 <voicetrans transtext="..."> 标签，
这是微信自带的语音转文字结果，准确度远高于 Whisper 等外部模型。

关键发现：
- 语音音频不在 MediaMSG 数据库中通过 Reserved0=MsgSvrID 匹配（实测无匹配）
- StrContent XML 直接包含 <voicemsg> 和 <voicetrans> 标签
- <voicetrans> 的 transtext 属性就是微信内置的语音转文字结果
- istransend="true" 表示转录完成，tranfailfinish="0" 表示未失败

使用方式：
    extractor = VoiceTranscriptionExtractor("output/decrypted_db")
    transcriptions = extractor.extract_by_chatroom("47390535442@chatroom")
    for t in transcriptions:
        print(f"[{t.time_str}] ({t.duration:.1f}s) {t.text}")
"""

import re
import sqlite3
import os
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional


@dataclass
class VoiceTranscription:
    msgsvrid: int
    create_time: int
    time_str: str
    duration_ms: int
    duration_sec: float
    text: str
    sender_wxid: str
    aeskey: str
    voiceformat: int
    has_transcription: bool
    source_db: str


class VoiceTranscriptionExtractor:
    """微信语音消息转录提取器"""

    def __init__(self, db_dir: str = "output/decrypted_db"):
        self.db_dir = Path(db_dir)
        self.multi_dir = self.db_dir / "Multi"

    def _query_voice_messages(self, cursor, condition: str, params: list) -> List[tuple]:
        cursor.execute(f"""
            SELECT MsgSvrID, CreateTime, StrContent, 'unknown'
            FROM MSG
            WHERE Type=34 AND {condition}
            ORDER BY CreateTime
        """, params)
        return cursor.fetchall()

    def _parse_voice_xml(self, content: str) -> dict:
        result = {
            'text': '',
            'sender_wxid': '',
            'aeskey': '',
            'voiceformat': 0,
            'duration_ms': 0,
            'has_transcription': False,
        }

        # Extract voicetrans text (微信内置语音转文字)
        trans_match = re.search(r'transtext="([^"]*)"', content)
        if trans_match:
            result['text'] = trans_match.group(1)
            result['has_transcription'] = True

        # Extract istransend flag
        is_trans_end = re.search(r'istransend="([^"]*)"', content)
        result['is_trans_end'] = is_trans_end and is_trans_end.group(1) == 'true'

        # Extract voicelength (duration in ms)
        length_match = re.search(r'voicelength="(\d+)"', content)
        if length_match:
            result['duration_ms'] = int(length_match.group(1))

        # Extract sender wxid
        sender_match = re.search(r'fromusername="([^"]*)"', content)
        if sender_match:
            result['sender_wxid'] = sender_match.group(1)

        # Extract aeskey
        aeskey_match = re.search(r'aeskey="([^"]*)"', content)
        if aeskey_match:
            result['aeskey'] = aeskey_match.group(1)

        # Extract voiceformat
        format_match = re.search(r'voiceformat="(\d+)"', content)
        if format_match:
            result['voiceformat'] = int(format_match.group(1))

        return result

    def extract_by_chatroom(self, chatroom_id: str) -> List[VoiceTranscription]:
        """提取指定群聊的语音转录

        Args:
            chatroom_id: 群聊ID，如 "47390535442@chatroom"

        Returns:
            VoiceTranscription 列表
        """
        results = []
        msg_dbs = sorted(self.multi_dir.glob("MSG*.db"))

        for db_path in msg_dbs:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            try:
                rows = self._query_voice_messages(
                    cursor,
                    "StrTalker=?",
                    [chatroom_id]
                )
            except sqlite3.OperationalError:
                conn.close()
                continue

            for row in rows:
                msgsvrid, create_time, content, _ = row
                parsed = self._parse_voice_xml(content or '')
                time_str = datetime.fromtimestamp(create_time).strftime('%H:%M:%S')
                duration_sec = parsed['duration_ms'] / 1000

                vt = VoiceTranscription(
                    msgsvrid=msgsvrid,
                    create_time=create_time,
                    time_str=time_str,
                    duration_ms=parsed['duration_ms'],
                    duration_sec=duration_sec,
                    text=parsed['text'],
                    sender_wxid=parsed['sender_wxid'],
                    aeskey=parsed['aeskey'],
                    voiceformat=parsed['voiceformat'],
                    has_transcription=parsed['has_transcription'],
                    source_db=db_path.name,
                )
                results.append(vt)

            conn.close()

        results.sort(key=lambda x: x.create_time)
        return results

    def extract_by_sender(self, sender_wxid: str, chatroom_id: Optional[str] = None) -> List[VoiceTranscription]:
        """提取指定发送者的语音转录

        Args:
            sender_wxid: 发送者wxid
            chatroom_id: 可选，限定群聊范围

        Returns:
            VoiceTranscription 列表
        """
        results = []
        msg_dbs = sorted(self.multi_dir.glob("MSG*.db"))

        for db_path in msg_dbs:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            try:
                if chatroom_id:
                    # Filter by fromusername in XML + chatroom
                    cursor.execute("""
                        SELECT MsgSvrID, CreateTime, StrContent
                        FROM MSG
                        WHERE Type=34 AND StrTalker=?
                        ORDER BY CreateTime
                    """, [chatroom_id])
                else:
                    # Search all voice messages, filter by fromusername in XML
                    cursor.execute("""
                        SELECT MsgSvrID, CreateTime, StrContent
                        FROM MSG
                        WHERE Type=34
                        ORDER BY CreateTime
                    """)
            except sqlite3.OperationalError:
                conn.close()
                continue

            for row in cursor.fetchall():
                msgsvrid, create_time, content = row
                parsed = self._parse_voice_xml(content or '')

                if parsed['sender_wxid'] != sender_wxid:
                    continue

                time_str = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')
                duration_sec = parsed['duration_ms'] / 1000

                vt = VoiceTranscription(
                    msgsvrid=msgsvrid,
                    create_time=create_time,
                    time_str=time_str,
                    duration_ms=parsed['duration_ms'],
                    duration_sec=duration_sec,
                    text=parsed['text'],
                    sender_wxid=parsed['sender_wxid'],
                    aeskey=parsed['aeskey'],
                    voiceformat=parsed['voiceformat'],
                    has_transcription=parsed['has_transcription'],
                    source_db=db_path.name,
                )
                results.append(vt)

            conn.close()

        results.sort(key=lambda x: x.create_time)
        return results

    def save_transcriptions(self, transcriptions: List[VoiceTranscription],
                            output_path: str, header: str = "") -> str:
        """保存转录结果到文件

        Args:
            transcriptions: 转录列表
            output_path: 输出文件路径
            header: 文件头部说明

        Returns:
            输出文件路径
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        total = len(transcriptions)
        has_text = sum(1 for t in transcriptions if t.has_transcription)
        no_text = total - has_text
        total_duration = sum(t.duration_sec for t in transcriptions)

        with open(output_path, 'w', encoding='utf-8') as f:
            if header:
                f.write(header + "\n\n")
            f.write(f"# 共 {total} 条语音，{has_text} 条有转录，{no_text} 条无转录\n")
            f.write(f"# 总时长 {total_duration:.1f}s ({total_duration/60:.1f}min)\n\n")

            for t in transcriptions:
                text = t.text if t.has_transcription else "[无转录文本]"
                f.write(f"[{t.time_str}] ({t.duration_sec:.1f}s) {text}\n")

        return output_path

    def save_as_json(self, transcriptions: List[VoiceTranscription],
                     output_path: str) -> str:
        """保存转录结果为JSON"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump([asdict(t) for t in transcriptions], f, ensure_ascii=False, indent=2)
        return output_path


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    # 示例用法
    extractor = VoiceTranscriptionExtractor()

    if len(sys.argv) > 1:
        chatroom_id = sys.argv[1]
    else:
        chatroom_id = "47390535442@chatroom"  # 海钓小程序群

    transcriptions = extractor.extract_by_chatroom(chatroom_id)

    print(f"找到 {len(transcriptions)} 条语音消息")
    for t in transcriptions:
        text = t.text if t.has_transcription else "[无转录文本]"
        print(f"[{t.time_str}] ({t.duration_sec:.1f}s) {text}")

    # 保存结果
    if transcriptions:
        output_dir = f"output/voice_{chatroom_id.replace('@chatroom', '')}"
        extractor.save_transcriptions(
            transcriptions,
            f"{output_dir}/wechat_transcriptions.txt",
            header=f"# 语音转录 - 群 {chatroom_id}"
        )
        extractor.save_as_json(transcriptions, f"{output_dir}/wechat_transcriptions.json")
        print(f"\n已保存到 {output_dir}/")