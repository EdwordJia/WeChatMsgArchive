#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据清洗和预处理框架 - WeChatMsgArchive 数据分析流水线

职责：
1. 读取 data_extractor 生成的标准化数据
2. 执行数据清洗、去重、异常处理
3. 生成分析就绪的数据集（用户画像、关系图谱、项目追踪）
4. 输出清洗报告

输入：unified_data_v3.db / unified_data_v4.db
输出：cleaned_data.db + 清洗报告 JSON
"""

import os
import sys
import json
import re
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Set, Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import defaultdict
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# 清洗配置
# =============================================================================

class CleanConfig:
    """数据清洗配置参数"""
    # 时间戳有效范围
    MIN_TIMESTAMP = 1262275200  # 2010-01-01
    MAX_TIMESTAMP_OFFSET = 86400 * 30  # 允许未来30天
    
    # 内容长度限制
    MAX_CONTENT_LENGTH = 50000
    MIN_CONTENT_LENGTH = 0
    
    # 发送者未知占位符
    UNKNOWN_SENDER_PREFIX = "unknown_sender"
    
    # 消息类型白名单（分析关注的类型）
    ANALYSIS_TYPES = {1, 3, 34, 43, 47, 49, 50, 10000}
    
    # 链接正则
    URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+', re.IGNORECASE)
    
    # 文件扩展名提取
    FILE_EXT_PATTERN = re.compile(r'\.([a-zA-Z0-9]+)(?:\?.*)?$')
    
    # 中文分词前置清理
    NON_CHINESE_PATTERN = re.compile(r'[^\u4e00-\u9fa5a-zA-Z0-9]')


# =============================================================================
# 清洗报告模型
# =============================================================================

@dataclass
class CleanReport:
    """数据清洗报告"""
    run_time: str
    source_db: str
    total_messages_before: int
    total_messages_after: int
    removed_duplicates: int
    removed_invalid_time: int
    removed_empty_content: int
    removed_too_long: int
    unknown_senders_fixed: int
    type_distribution_before: Dict[str, int]
    type_distribution_after: Dict[str, int]
    date_range: Tuple[str, str]
    top_talkers: List[Tuple[str, int]]
    issues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def save(self, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


# =============================================================================
# 数据清洗器
# =============================================================================

class DataCleaner:
    """数据清洗主类"""
    
    def __init__(self, input_db: str, output_db: str):
        self.input_db = Path(input_db)
        self.output_db = Path(output_db)
        self.output_db.parent.mkdir(parents=True, exist_ok=True)
        
        self.src_conn: Optional[sqlite3.Connection] = None
        self.dst_conn: Optional[sqlite3.Connection] = None
        
        self.report = CleanReport(
            run_time=datetime.now().isoformat(),
            source_db=str(input_db),
            total_messages_before=0,
            total_messages_after=0,
            removed_duplicates=0,
            removed_invalid_time=0,
            removed_empty_content=0,
            removed_too_long=0,
            unknown_senders_fixed=0,
            type_distribution_before={},
            type_distribution_after={},
            date_range=('', ''),
            top_talkers=[]
        )
    
    def open(self):
        self.src_conn = sqlite3.connect(self.input_db)
        self.dst_conn = sqlite3.connect(self.output_db)
        self.dst_conn.execute("PRAGMA journal_mode=WAL")
        self._create_clean_tables()
    
    def close(self):
        if self.src_conn:
            self.src_conn.close()
        if self.dst_conn:
            self.dst_conn.close()
    
    def _create_clean_tables(self):
        """创建清洗后的表结构"""
        self.dst_conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages_clean (
                server_id INTEGER PRIMARY KEY,
                local_id INTEGER,
                timestamp INTEGER,
                str_time TEXT,
                date TEXT,
                hour INTEGER,
                weekday INTEGER,
                is_work_hours INTEGER,
                is_weekend INTEGER,
                msg_type INTEGER,
                msg_type_name TEXT,
                talker_id TEXT,
                talker_name TEXT,
                is_sender INTEGER,
                sender_id TEXT,
                sender_name TEXT,
                content TEXT,
                content_clean TEXT,
                content_length INTEGER,
                has_url INTEGER,
                url_list TEXT,
                is_reply INTEGER,
                reply_to_id INTEGER,
                status INTEGER,
                source_version TEXT
            );
            
            CREATE TABLE IF NOT EXISTS user_stats (
                wxid TEXT PRIMARY KEY,
                display_name TEXT,
                total_messages INTEGER,
                total_chars INTEGER,
                text_messages INTEGER,
                image_messages INTEGER,
                voice_messages INTEGER,
                video_messages INTEGER,
                link_messages INTEGER,
                file_messages INTEGER,
                first_seen TEXT,
                last_seen TEXT,
                active_days INTEGER,
                peak_hour INTEGER,
                avg_message_length REAL,
                is_my_contact INTEGER
            );
            
            CREATE TABLE IF NOT EXISTS talker_stats (
                talker_id TEXT PRIMARY KEY,
                talker_name TEXT,
                is_chatroom INTEGER,
                total_messages INTEGER,
                my_messages INTEGER,
                other_messages INTEGER,
                member_count INTEGER,
                first_message TEXT,
                last_message TEXT,
                active_days INTEGER,
                message_types TEXT
            );
            
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                total_messages INTEGER,
                unique_talkers INTEGER,
                unique_senders INTEGER,
                work_hours_messages INTEGER,
                weekend_messages INTEGER
            );
            
            CREATE INDEX IF NOT EXISTS idx_clean_talker ON messages_clean(talker_id);
            CREATE INDEX IF NOT EXISTS idx_clean_sender ON messages_clean(sender_id);
            CREATE INDEX IF NOT EXISTS idx_clean_date ON messages_clean(date);
            CREATE INDEX IF NOT EXISTS idx_clean_type ON messages_clean(msg_type);
        """)
        self.dst_conn.commit()
    
    def run(self) -> CleanReport:
        """执行完整清洗流程"""
        logger.info("=" * 60)
        logger.info("开始数据清洗")
        logger.info("=" * 60)
        
        # 统计清洗前数据
        self._count_before()
        
        # 步骤1: 清洗消息数据
        logger.info("[1/4] 清洗消息记录...")
        self._clean_messages()
        
        # 步骤2: 计算用户统计
        logger.info("[2/4] 计算用户统计...")
        self._compute_user_stats()
        
        # 步骤3: 计算聊天对象统计
        logger.info("[3/4] 计算聊天对象统计...")
        self._compute_talker_stats()
        
        # 步骤4: 计算日期统计
        logger.info("[4/4] 计算日期统计...")
        self._compute_daily_stats()
        
        # 统计清洗后数据
        self._count_after()
        
        logger.info("=" * 60)
        logger.info("清洗完成!")
        logger.info(f"  清洗前消息数: {self.report.total_messages_before}")
        logger.info(f"  清洗后消息数: {self.report.total_messages_after}")
        logger.info(f"  去重: {self.report.removed_duplicates}")
        logger.info(f"  无效时间: {self.report.removed_invalid_time}")
        logger.info(f"  空内容: {self.report.removed_empty_content}")
        logger.info("=" * 60)
        
        return self.report
    
    def _count_before(self):
        """统计清洗前数据"""
        cur = self.src_conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM messages")
        self.report.total_messages_before = cur.fetchone()[0]
        
        cur.execute("SELECT msg_type_name, COUNT(*) FROM messages GROUP BY msg_type_name")
        self.report.type_distribution_before = {r[0]: r[1] for r in cur.fetchall()}
        
        cur.execute("SELECT MIN(date), MAX(date) FROM messages WHERE date != ''")
        self.report.date_range = cur.fetchone()
    
    def _clean_messages(self):
        """核心消息清洗逻辑"""
        cur = self.src_conn.cursor()
        cur.execute("""
            SELECT 
                server_id, local_id, timestamp, str_time, date, hour, weekday,
                is_work_hours, is_weekend, msg_type, msg_type_name, talker_id,
                is_sender, sender_id, sender_name, content, xml_content, status, source_version
            FROM messages
            ORDER BY timestamp
        """)
        
        seen_server_ids: Set[int] = set()
        insert_sql = """
            INSERT OR IGNORE INTO messages_clean
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        batch = []
        batch_size = 5000
        
        for row in cur:
            result = self._process_single_message(row, seen_server_ids)
            if result:
                batch.append(result)
                seen_server_ids.add(result[0])
                
                if len(batch) >= batch_size:
                    self.dst_conn.executemany(insert_sql, batch)
                    self.dst_conn.commit()
                    batch = []
        
        if batch:
            self.dst_conn.executemany(insert_sql, batch)
            self.dst_conn.commit()
    
    def _process_single_message(self, row: tuple, seen_ids: Set[int]) -> Optional[tuple]:
        """
        处理单条消息，返回清洗后的元组或 None（表示丢弃）
        """
        (server_id, local_id, timestamp, str_time, date, hour, weekday,
         is_work_hours, is_weekend, msg_type, msg_type_name, talker_id,
         is_sender, sender_id, sender_name, content, xml_content, status, source_version) = row
        
        # 规则1: 去重
        if server_id in seen_ids:
            self.report.removed_duplicates += 1
            return None
        
        # 规则2: 时间戳校验
        now = int(datetime.now().timestamp())
        if not timestamp or timestamp < CleanConfig.MIN_TIMESTAMP or timestamp > now + CleanConfig.MAX_TIMESTAMP_OFFSET:
            self.report.removed_invalid_time += 1
            # 尝试用 local_id 或 server_id 替代（不丢弃，标记问题）
            timestamp = 0
            str_time = 'Invalid'
            date = 'Invalid'
        
        # 规则3: 内容校验
        if content is None:
            content = ''
        
        # 去除控制字符
        content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', content)
        
        # 根据消息类型填充默认内容
        if not content.strip():
            content = self._default_content_for_type(msg_type, msg_type_name)
        
        # 规则4: 超长内容截断
        content_length = len(content)
        if content_length > CleanConfig.MAX_CONTENT_LENGTH:
            content = content[:CleanConfig.MAX_CONTENT_LENGTH] + '...[截断]'
            self.report.removed_too_long += 1
        
        # 规则5: 发送者修复
        if not sender_id or sender_id == 'unknown':
            sender_id = f"{CleanConfig.UNKNOWN_SENDER_PREFIX}_{hash(talker_id) % 10000}"
            self.report.unknown_senders_fixed += 1
        
        # 派生字段计算
        content_clean = self._clean_content(content)
        has_url = 1 if CleanConfig.URL_PATTERN.search(content) else 0
        url_list = ','.join(CleanConfig.URL_PATTERN.findall(content)) if has_url else ''
        is_reply, reply_to_id = self._detect_reply(content, xml_content)
        
        # 查询 talker 名称
        talker_name = self._get_talker_name(talker_id)
        
        return (
            server_id, local_id, timestamp, str_time, date, hour, weekday,
            is_work_hours, is_weekend, msg_type, msg_type_name, talker_id,
            talker_name, is_sender, sender_id, sender_name or sender_id,
            content, content_clean, content_length, has_url, url_list,
            is_reply, reply_to_id, status, source_version
        )
    
    def _default_content_for_type(self, msg_type: int, type_name: str) -> str:
        """根据类型生成默认内容描述"""
        defaults = {
            1: '[空文本]',
            3: '[图片]',
            34: '[语音]',
            43: '[视频]',
            47: '[表情包]',
            48: '[位置]',
            49: '[链接/卡片]',
            50: '[音视频通话]',
        }
        return defaults.get(msg_type, f'[{type_name or "未知内容"}]')
    
    def _clean_content(self, content: str) -> str:
        """清理内容用于文本分析"""
        # 去除 XML 标签
        content = re.sub(r'<[^>]+>', ' ', content)
        # 去除 URL
        content = CleanConfig.URL_PATTERN.sub(' ', content)
        # 去除多余空白
        content = re.sub(r'\s+', ' ', content).strip()
        return content
    
    def _detect_reply(self, content: str, xml_content: str) -> Tuple[int, int]:
        """检测是否为回复消息"""
        # 简化实现：检查是否包含引用标记
        if xml_content and '<refermsg>' in xml_content:
            # 实际应解析 XML 获取引用的 server_id
            return 1, 0
        if content.startswith('回复') or '「' in content[:20]:
            return 1, 0
        return 0, 0
    
    def _get_talker_name(self, talker_id: str) -> str:
        """获取聊天对象名称"""
        try:
            cur = self.src_conn.cursor()
            cur.execute("SELECT display_name FROM contacts WHERE wxid = ?", (talker_id,))
            r = cur.fetchone()
            return r[0] if r else talker_id
        except:
            return talker_id
    
    def _compute_user_stats(self):
        """计算每个用户的发送统计"""
        cur = self.dst_conn.cursor()
        
        cur.execute("""
            SELECT 
                sender_id,
                sender_name,
                COUNT(*) as total,
                SUM(content_length) as total_chars,
                SUM(CASE WHEN msg_type = 1 THEN 1 ELSE 0 END) as text_count,
                SUM(CASE WHEN msg_type = 3 THEN 1 ELSE 0 END) as image_count,
                SUM(CASE WHEN msg_type = 34 THEN 1 ELSE 0 END) as voice_count,
                SUM(CASE WHEN msg_type = 43 THEN 1 ELSE 0 END) as video_count,
                SUM(CASE WHEN msg_type = 49 THEN 1 ELSE 0 END) as link_count,
                SUM(CASE WHEN msg_type = 6 THEN 1 ELSE 0 END) as file_count,
                MIN(str_time), MAX(str_time),
                COUNT(DISTINCT date),
                AVG(content_length)
            FROM messages_clean
            WHERE is_sender = 0 OR sender_id != 'self'
            GROUP BY sender_id
        """)
        
        for row in cur.fetchall():
            (wxid, name, total, chars, text_c, img_c, voice_c, video_c, link_c, file_c,
             first, last, active_days, avg_len) = row
            
            cur.execute("""
                INSERT OR REPLACE INTO user_stats
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                wxid, name, total, chars or 0, text_c or 0, img_c or 0,
                voice_c or 0, video_c or 0, link_c or 0, file_c or 0,
                first, last, active_days, 0, round(avg_len or 0, 2), 1
            ))
        
        self.dst_conn.commit()
    
    def _compute_talker_stats(self):
        """计算每个聊天对象的统计"""
        cur = self.dst_conn.cursor()
        
        cur.execute("""
            SELECT 
                talker_id,
                talker_name,
                COUNT(*) as total,
                SUM(CASE WHEN is_sender = 1 THEN 1 ELSE 0 END) as my_count,
                SUM(CASE WHEN is_sender = 0 THEN 1 ELSE 0 END) as other_count,
                COUNT(DISTINCT sender_id) as member_count,
                MIN(str_time), MAX(str_time),
                COUNT(DISTINCT date),
                GROUP_CONCAT(DISTINCT msg_type_name)
            FROM messages_clean
            GROUP BY talker_id
        """)
        
        for row in cur.fetchall():
            (tid, tname, total, my_c, other_c, members, first, last, days, types) = row
            is_chatroom = 1 if tid and tid.endswith('@chatroom') else 0
            
            cur.execute("""
                INSERT OR REPLACE INTO talker_stats
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tid, tname, is_chatroom, total, my_c, other_c,
                members, first, last, days, types or ''
            ))
        
        self.dst_conn.commit()
    
    def _compute_daily_stats(self):
        """计算每日统计"""
        cur = self.dst_conn.cursor()
        
        cur.execute("""
            SELECT 
                date,
                COUNT(*) as total,
                COUNT(DISTINCT talker_id) as talkers,
                COUNT(DISTINCT sender_id) as senders,
                SUM(CASE WHEN is_work_hours = 1 THEN 1 ELSE 0 END) as work_msgs,
                SUM(CASE WHEN is_weekend = 1 THEN 1 ELSE 0 END) as weekend_msgs
            FROM messages_clean
            WHERE date != 'Invalid'
            GROUP BY date
            ORDER BY date
        """)
        
        for row in cur.fetchall():
            cur.execute("""
                INSERT OR REPLACE INTO daily_stats
                VALUES (?, ?, ?, ?, ?, ?)
            """, row)
        
        self.dst_conn.commit()
    
    def _count_after(self):
        """统计清洗后数据"""
        cur = self.dst_conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM messages_clean")
        self.report.total_messages_after = cur.fetchone()[0]
        
        cur.execute("SELECT msg_type_name, COUNT(*) FROM messages_clean GROUP BY msg_type_name")
        self.report.type_distribution_after = {r[0]: r[1] for r in cur.fetchall()}
        
        cur.execute("SELECT talker_id, COUNT(*) FROM messages_clean GROUP BY talker_id ORDER BY COUNT(*) DESC LIMIT 10")
        self.report.top_talkers = cur.fetchall()


# =============================================================================
# 便捷入口
# =============================================================================

def run_cleaning(input_db: str, output_db: str, report_path: Optional[str] = None):
    """运行清洗流程"""
    cleaner = DataCleaner(input_db, output_db)
    try:
        cleaner.open()
        report = cleaner.run()
        
        if report_path:
            report.save(report_path)
            logger.info(f"清洗报告已保存: {report_path}")
        
        return report
    finally:
        cleaner.close()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='微信数据清洗框架')
    parser.add_argument('--input-db', required=True, help='输入的标准化数据库')
    parser.add_argument('--output-db', required=True, help='清洗后的输出数据库')
    parser.add_argument('--report', help='清洗报告输出路径')
    
    args = parser.parse_args()
    run_cleaning(args.input_db, args.output_db, args.report)
