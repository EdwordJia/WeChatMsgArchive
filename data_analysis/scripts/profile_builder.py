#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分析数据集构建器 - WeChatMsgArchive 数据分析流水线

职责：
1. 读取清洗后的数据 (cleaned_data.db)
2. 构建用户画像、关系图谱、项目追踪等分析数据集
3. 输出为结构化的 JSON/SQLite，供 Markdown 导出器使用

分析维度：
- 用户画像：发言习惯、活跃时段、内容偏好、社交特征
- 关系图谱：群聊共现、互动频率、回复关系、亲密度
- 项目追踪：关键词聚类、话题演化、任务分配、进度提取
"""

import os
import sys
import json
import sqlite3
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Set, Counter, DefaultDict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# 数据模型
# =============================================================================

@dataclass
class UserProfile:
    """用户画像模型"""
    wxid: str
    display_name: str
    
    # 基础统计
    total_messages: int = 0
    total_chars: int = 0
    active_days: int = 0
    first_seen: str = ''
    last_seen: str = ''
    
    # 时间模式
    hourly_distribution: Dict[int, int] = field(default_factory=dict)  # 0-23
    weekday_distribution: Dict[int, int] = field(default_factory=dict)  # 0-6
    work_life_ratio: float = 0.0  # 工作时间占比
    
    # 内容偏好
    type_distribution: Dict[str, int] = field(default_factory=dict)
    avg_message_length: float = 0.0
    max_message_length: int = 0
    url_share_count: int = 0
    file_share_count: int = 0
    image_share_count: int = 0
    
    # 社交特征
    groups_joined: List[str] = field(default_factory=list)
    groups_active_in: int = 0
    top_interact_with: List[Tuple[str, int]] = field(default_factory=list)
    reply_rate: float = 0.0  # 被回复率
    
    # 标签（由分析生成）
    tags: List[str] = field(default_factory=list)
    persona_summary: str = ''
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RelationEdge:
    """关系图谱边模型"""
    source: str  # wxid
    target: str  # wxid
    relation_type: str  # 'co_group', 'reply', 'mention', 'direct_chat'
    weight: float  # 关系强度
    first_seen: str = ''
    last_seen: str = ''
    common_groups: List[str] = field(default_factory=list)
    interaction_count: int = 0
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProjectTopic:
    """项目/话题追踪模型"""
    topic_id: str
    topic_name: str
    keywords: List[str] = field(default_factory=list)
    
    # 时间线
    start_time: str = ''
    end_time: str = ''
    active_days: int = 0
    
    # 参与者
    participants: List[str] = field(default_factory=list)
    participant_messages: Dict[str, int] = field(default_factory=dict)
    
    # 消息摘要
    key_messages: List[Dict] = field(default_factory=list)
    message_count: int = 0
    
    # 状态推断
    status: str = 'ongoing'  # ongoing, completed, stalled
    progress_indicators: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return asdict(self)


# =============================================================================
# 分析器基类
# =============================================================================

class BaseAnalyzer(ABC):
    """分析器抽象基类"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
    
    def open(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
    
    def close(self):
        if self.conn:
            self.conn.close()
    
    @abstractmethod
    def analyze(self) -> dict:
        """执行分析，返回结果字典"""
        pass


# =============================================================================
# 用户画像分析器
# =============================================================================

class UserProfileAnalyzer(BaseAnalyzer):
    """用户画像分析器"""
    
    def analyze(self) -> Dict[str, UserProfile]:
        logger.info("开始构建用户画像...")
        profiles: Dict[str, UserProfile] = {}
        
        # 基础统计已在 data_cleaner 中计算，直接读取
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM user_stats")
        
        for row in cur.fetchall():
            p = UserProfile(
                wxid=row['wxid'],
                display_name=row['display_name'] or row['wxid'],
                total_messages=row['total_messages'],
                total_chars=row['total_chars'],
                active_days=row['active_days'],
                first_seen=row['first_seen'],
                last_seen=row['last_seen'],
                avg_message_length=row['avg_message_length']
            )
            profiles[p.wxid] = p
        
        # 补充时间分布
        self._enrich_hourly_pattern(profiles)
        self._enrich_type_distribution(profiles)
        self._enrich_group_membership(profiles)
        self._enrich_interaction_pairs(profiles)
        self._generate_tags(profiles)
        
        logger.info(f"用户画像构建完成: {len(profiles)} 人")
        return profiles
    
    def _enrich_hourly_pattern(self, profiles: Dict[str, UserProfile]):
        """补充用户的小时级活跃分布"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT sender_id, hour, COUNT(*) as cnt,
                   SUM(CASE WHEN is_work_hours = 1 THEN 1 ELSE 0 END) as work_cnt
            FROM messages_clean
            WHERE sender_id != 'self'
            GROUP BY sender_id, hour
        """)
        
        for row in cur:
            wxid = row['sender_id']
            if wxid not in profiles:
                continue
            profiles[wxid].hourly_distribution[row['hour']] = row['cnt']
        
        # 计算工作生活比
        for p in profiles.values():
            work_msgs = sum(c for h, c in p.hourly_distribution.items() if 9 <= h <= 18)
            total = sum(p.hourly_distribution.values())
            p.work_life_ratio = round(work_msgs / total, 2) if total > 0 else 0
    
    def _enrich_type_distribution(self, profiles: Dict[str, UserProfile]):
        """补充消息类型分布"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT sender_id, msg_type_name, COUNT(*) as cnt,
                   MAX(content_length) as max_len,
                   SUM(CASE WHEN has_url = 1 THEN 1 ELSE 0 END) as url_cnt
            FROM messages_clean
            WHERE sender_id != 'self'
            GROUP BY sender_id, msg_type_name
        """)
        
        for row in cur:
            wxid = row['sender_id']
            if wxid not in profiles:
                continue
            p = profiles[wxid]
            p.type_distribution[row['msg_type_name']] = row['cnt']
            p.max_message_length = max(p.max_message_length, row['max_len'] or 0)
            p.url_share_count += row['url_cnt']
    
    def _enrich_group_membership(self, profiles: Dict[str, UserProfile]):
        """补充用户所在群聊"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT DISTINCT sender_id, talker_id
            FROM messages_clean
            WHERE talker_id LIKE '%@chatroom' AND sender_id != 'self'
        """)
        
        group_members: DefaultDict[str, Set[str]] = defaultdict(set)
        for row in cur:
            group_members[row['sender_id']].add(row['talker_id'])
        
        for wxid, groups in group_members.items():
            if wxid in profiles:
                profiles[wxid].groups_joined = list(groups)
                profiles[wxid].groups_active_in = len(groups)
    
    def _enrich_interaction_pairs(self, profiles: Dict[str, UserProfile]):
        """补充用户最常互动对象"""
        cur = self.conn.cursor()
        # 在群聊中，找到经常回复该用户的人
        cur.execute("""
            SELECT 
                m1.sender_id as user,
                m2.sender_id as replier,
                COUNT(*) as reply_count
            FROM messages_clean m1
            JOIN messages_clean m2 ON m1.talker_id = m2.talker_id
                AND m2.timestamp > m1.timestamp
                AND m2.timestamp < m1.timestamp + 3600
                AND m2.sender_id != m1.sender_id
                AND m1.sender_id != 'self'
                AND m2.sender_id != 'self'
            WHERE m1.talker_id LIKE '%@chatroom'
            GROUP BY m1.sender_id, m2.sender_id
            HAVING reply_count >= 3
            ORDER BY reply_count DESC
        """)
        
        interactions: DefaultDict[str, Counter] = defaultdict(Counter)
        for row in cur:
            interactions[row['user']][row['replier']] = row['reply_count']
        
        for wxid, counter in interactions.items():
            if wxid in profiles:
                profiles[wxid].top_interact_with = counter.most_common(5)
    
    def _generate_tags(self, profiles: Dict[str, UserProfile]):
        """为用户生成标签和摘要"""
        for p in profiles.values():
            tags = []
            
            # 活跃程度标签
            if p.total_messages > 1000:
                tags.append('高活跃')
            elif p.total_messages > 100:
                tags.append('活跃')
            else:
                tags.append('低频')
            
            # 时段标签
            if p.work_life_ratio > 0.7:
                tags.append('工作狂')
            elif p.work_life_ratio < 0.3:
                tags.append('夜猫子/生活化')
            
            # 内容偏好标签
            text_ratio = p.type_distribution.get('文本', 0) / max(p.total_messages, 1)
            if text_ratio > 0.8:
                tags.append('话痨型')
            elif p.type_distribution.get('图片', 0) > p.total_messages * 0.3:
                tags.append('视觉型')
            elif p.type_distribution.get('语音', 0) > p.total_messages * 0.2:
                tags.append('语音偏好')
            
            # 社交标签
            if p.groups_active_in > 5:
                tags.append('社交广泛')
            elif p.groups_active_in == 1:
                tags.append('专注型')
            
            # 长文标签
            if p.avg_message_length > 100:
                tags.append('深度表达')
            elif p.avg_message_length < 20:
                tags.append('简洁型')
            
            p.tags = tags
            p.persona_summary = self._generate_summary(p)
    
    def _generate_summary(self, p: UserProfile) -> str:
        """生成用户一句话摘要"""
        parts = []
        parts.append(f"{p.display_name} 是")
        parts.append(f"一个在 {p.active_days} 天内有 {p.total_messages} 条发言的{'群成员' if p.groups_active_in > 0 else '联系人'}")
        
        if p.tags:
            parts.append(f"，特征为{'、'.join(p.tags[:3])}")
        
        if p.work_life_ratio > 0.6:
            parts.append("。倾向于在工作时间交流")
        elif p.work_life_ratio < 0.3:
            parts.append("。倾向于在非工作时间交流")
        
        parts.append("。")
        return ''.join(parts)


# =============================================================================
# 关系图谱分析器
# =============================================================================

class RelationGraphAnalyzer(BaseAnalyzer):
    """关系图谱分析器"""
    
    def analyze(self) -> Dict[str, List[RelationEdge]]:
        logger.info("开始构建关系图谱...")
        
        edges: DefaultDict[str, List[RelationEdge]] = defaultdict(list)
        edge_map: Dict[Tuple[str, str], RelationEdge] = {}
        
        # 1. 群聊共现关系
        self._build_co_group_edges(edge_map)
        
        # 2. 回复关系
        self._build_reply_edges(edge_map)
        
        # 3. 直接聊天关系
        self._build_direct_chat_edges(edge_map)
        
        # 转为邻接表
        for (s, t), edge in edge_map.items():
            edges[s].append(edge)
            edges[t].append(edge)
        
        logger.info(f"关系图谱构建完成: {len(edge_map)} 条边")
        return dict(edges)
    
    def _build_co_group_edges(self, edge_map: Dict[Tuple[str, str], RelationEdge]):
        """基于群聊共现构建关系"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT DISTINCT talker_id, sender_id
            FROM messages_clean
            WHERE talker_id LIKE '%@chatroom' AND sender_id != 'self'
        """)
        
        group_members: DefaultDict[str, Set[str]] = defaultdict(set)
        for row in cur:
            group_members[row['talker_id']].add(row['sender_id'])
        
        for group_id, members in group_members.items():
            members = list(members)
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    a, b = sorted([members[i], members[j]])
                    key = (a, b)
                    
                    if key not in edge_map:
                        edge_map[key] = RelationEdge(
                            source=a, target=b,
                            relation_type='co_group',
                            weight=0, common_groups=[]
                        )
                    
                    edge = edge_map[key]
                    edge.weight += 1
                    if group_id not in edge.common_groups:
                        edge.common_groups.append(group_id)
    
    def _build_reply_edges(self, edge_map: Dict[Tuple[str, str], RelationEdge]):
        """基于消息回复构建关系"""
        cur = self.conn.cursor()
        # 简化：在同一群聊中，短时间内（5分钟内）的连续发言视为互动
        cur.execute("""
            SELECT 
                m1.sender_id as sender1,
                m2.sender_id as sender2,
                m1.talker_id,
                COUNT(*) as cnt
            FROM messages_clean m1
            JOIN messages_clean m2 
                ON m1.talker_id = m2.talker_id
                AND m2.timestamp > m1.timestamp
                AND m2.timestamp <= m1.timestamp + 300
                AND m1.sender_id < m2.sender_id
            WHERE m1.sender_id != 'self' AND m2.sender_id != 'self'
            GROUP BY m1.sender_id, m2.sender_id, m1.talker_id
            HAVING cnt >= 2
        """)
        
        for row in cur:
            a, b = row['sender1'], row['sender2']
            key = (a, b)
            
            if key not in edge_map:
                edge_map[key] = RelationEdge(
                    source=a, target=b,
                    relation_type='reply',
                    weight=0
                )
            
            edge = edge_map[key]
            edge.weight += row['cnt'] * 2  # 回复关系权重更高
            edge.interaction_count += row['cnt']
    
    def _build_direct_chat_edges(self, edge_map: Dict[Tuple[str, str], RelationEdge]):
        """基于私聊构建关系"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT talker_id, COUNT(*) as cnt, MIN(str_time), MAX(str_time)
            FROM messages_clean
            WHERE talker_id NOT LIKE '%@chatroom' AND talker_id != 'self'
            GROUP BY talker_id
        """)
        
        for row in cur:
            other = row['talker_id']
            key = ('self', other)
            
            edge_map[key] = RelationEdge(
                source='self', target=other,
                relation_type='direct_chat',
                weight=row['cnt'],
                first_seen=row['MIN(str_time)'],
                last_seen=row['MAX(str_time)'],
                interaction_count=row['cnt']
            )


# =============================================================================
# 项目追踪分析器
# =============================================================================

class ProjectTrackerAnalyzer(BaseAnalyzer):
    """项目/话题追踪分析器"""
    
    # 项目关键词库（可扩展）
    PROJECT_KEYWORDS = {
        '开发': ['开发', '代码', 'bug', '修复', '版本', '上线', '部署', '测试', 'git', 'commit'],
        '设计': ['设计', 'UI', '界面', '原型', 'Figma', 'PS', '配色', '布局'],
        '会议': ['会议', '讨论', '对齐', '决策', '评审', '例会', '周会'],
        '交付': ['交付', '验收', '合同', '付款', '发票', '客户', '需求'],
        '学习': ['学习', '课程', '培训', '分享', '推荐', '资料', '文档'],
    }
    
    def analyze(self) -> List[ProjectTopic]:
        logger.info("开始项目/话题追踪分析...")
        
        topics = []
        
        # 1. 基于关键词发现话题
        keyword_topics = self._discover_by_keywords()
        topics.extend(keyword_topics)
        
        # 2. 基于时间窗口的突发话题
        burst_topics = self._discover_by_burst()
        topics.extend(burst_topics)
        
        # 3. 合并相似话题
        topics = self._merge_similar_topics(topics)
        
        logger.info(f"话题追踪完成: {len(topics)} 个话题")
        return topics
    
    def _discover_by_keywords(self) -> List[ProjectTopic]:
        """基于关键词库发现话题"""
        cur = self.conn.cursor()
        cur.execute("SELECT content, str_time, sender_id, sender_name, talker_id, talker_name FROM messages_clean WHERE msg_type = 1")
        
        topic_messages: DefaultDict[str, List[Dict]] = defaultdict(list)
        
        for row in cur:
            content = row['content'] or ''
            for topic_name, keywords in self.PROJECT_KEYWORDS.items():
                if any(kw in content for kw in keywords):
                    topic_messages[topic_name].append({
                        'content': content[:200],
                        'time': row['str_time'],
                        'sender': row['sender_name'] or row['sender_id'],
                        'talker': row['talker_name'] or row['talker_id']
                    })
        
        topics = []
        for name, msgs in topic_messages.items():
            if len(msgs) < 3:  # 过滤过少的话题
                continue
            
            times = [m['time'] for m in msgs if m['time']]
            participants = list(set(m['sender'] for m in msgs))
            
            topic = ProjectTopic(
                topic_id=f"kw_{hash(name) % 10000:04d}",
                topic_name=name,
                keywords=self.PROJECT_KEYWORDS.get(name, []),
                start_time=min(times) if times else '',
                end_time=max(times) if times else '',
                active_days=len(set(t[:10] for t in times)),
                participants=participants,
                participant_messages={p: sum(1 for m in msgs if m['sender'] == p) for p in participants},
                key_messages=msgs[:10],
                message_count=len(msgs)
            )
            
            # 推断状态
            topic.status = self._infer_status(msgs, times)
            topics.append(topic)
        
        return topics
    
    def _discover_by_burst(self) -> List[ProjectTopic]:
        """基于消息突发密度发现话题"""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT date, talker_id, COUNT(*) as cnt
            FROM messages_clean
            WHERE talker_id LIKE '%@chatroom'
            GROUP BY date, talker_id
            HAVING cnt > 50
            ORDER BY date, cnt DESC
        """)
        
        topics = []
        for row in cur:
            date = row['date']
            talker = row['talker_id']
            
            # 获取该群该日的高频关键词
            cur2 = self.conn.cursor()
            cur2.execute("""
                SELECT content FROM messages_clean
                WHERE date = ? AND talker_id = ? AND msg_type = 1
            """, (date, talker))
            
            words = []
            for r in cur2:
                text = r['content'] or ''
                # 简单提取 4-8 字词组作为话题候选
                for w in re.findall(r'[\u4e00-\u9fa5]{4,8}', text):
                    words.append(w)
            
            if not words:
                continue
            
            # 取最高频词组作为话题名
            most_common = Counter(words).most_common(1)
            if not most_common or most_common[0][1] < 3:
                continue
            
            topic_name = most_common[0][0]
            
            topic = ProjectTopic(
                topic_id=f"burst_{date}_{hash(talker) % 1000:03d}",
                topic_name=topic_name,
                keywords=[topic_name],
                start_time=date,
                end_time=date,
                active_days=1,
                message_count=row['cnt']
            )
            topics.append(topic)
        
        return topics
    
    def _merge_similar_topics(self, topics: List[ProjectTopic]) -> List[ProjectTopic]:
        """合并相似话题"""
        # 简化实现：同名话题合并
        merged: Dict[str, ProjectTopic] = {}
        for t in topics:
            key = t.topic_name
            if key in merged:
                mt = merged[key]
                mt.message_count += t.message_count
                mt.participants = list(set(mt.participants + t.participants))
                mt.key_messages = (mt.key_messages + t.key_messages)[:15]
                if t.start_time and t.start_time < mt.start_time:
                    mt.start_time = t.start_time
                if t.end_time and t.end_time > mt.end_time:
                    mt.end_time = t.end_time
            else:
                merged[key] = t
        
        return list(merged.values())
    
    def _infer_status(self, msgs: List[Dict], times: List[str]) -> str:
        """推断话题状态"""
        if not times:
            return 'unknown'
        
        # 检查最近是否有完成关键词
        recent_msgs = [m['content'] for m in msgs[-5:]]
        completion_words = ['完成', '搞定', '结束', '通过', '上线', '交付', 'OK']
        if any(w in ' '.join(recent_msgs) for w in completion_words):
            return 'completed'
        
        # 检查是否停滞（超过30天无消息）
        try:
            last_time = datetime.strptime(max(times), '%Y-%m-%d %H:%M:%S')
            if (datetime.now() - last_time).days > 30:
                return 'stalled'
        except:
            pass
        
        return 'ongoing'


# =============================================================================
# 数据集构建器主类
# =============================================================================

class AnalysisDatasetBuilder:
    """分析数据集构建器"""
    
    def __init__(self, cleaned_db: str, output_dir: str):
        self.cleaned_db = cleaned_db
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def build_all(self):
        """构建全部分析数据集"""
        logger.info("=" * 60)
        logger.info("开始构建分析数据集")
        logger.info("=" * 60)
        
        # 1. 用户画像
        profile_analyzer = UserProfileAnalyzer(self.cleaned_db)
        profile_analyzer.open()
        profiles = profile_analyzer.analyze()
        profile_analyzer.close()
        self._save_profiles(profiles)
        
        # 2. 关系图谱
        relation_analyzer = RelationGraphAnalyzer(self.cleaned_db)
        relation_analyzer.open()
        relations = relation_analyzer.analyze()
        relation_analyzer.close()
        self._save_relations(relations)
        
        # 3. 项目追踪
        project_analyzer = ProjectTrackerAnalyzer(self.cleaned_db)
        project_analyzer.open()
        projects = project_analyzer.analyze()
        project_analyzer.close()
        self._save_projects(projects)
        
        logger.info("=" * 60)
        logger.info("分析数据集构建完成!")
        logger.info(f"  用户画像: {len(profiles)}")
        logger.info(f"  关系节点: {len(relations)}")
        logger.info(f"  项目话题: {len(projects)}")
        logger.info("=" * 60)
    
    def _save_profiles(self, profiles: Dict[str, UserProfile]):
        """保存用户画像"""
        data = {k: v.to_dict() for k, v in profiles.items()}
        path = self.output_dir / 'user_profiles.json'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"用户画像已保存: {path}")
    
    def _save_relations(self, relations: Dict[str, List[RelationEdge]]):
        """保存关系图谱"""
        data = {}
        for node, edges in relations.items():
            data[node] = [e.to_dict() for e in edges]
        
        path = self.output_dir / 'relation_graph.json'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"关系图谱已保存: {path}")
    
    def _save_projects(self, projects: List[ProjectTopic]):
        """保存项目追踪"""
        data = [p.to_dict() for p in projects]
        path = self.output_dir / 'project_topics.json'
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"项目追踪已保存: {path}")


# =============================================================================
# 入口
# =============================================================================

def run_build_analysis(cleaned_db: str, output_dir: str):
    """运行分析数据集构建"""
    builder = AnalysisDatasetBuilder(cleaned_db, output_dir)
    builder.build_all()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='分析数据集构建器')
    parser.add_argument('--cleaned-db', required=True, help='清洗后的数据库路径')
    parser.add_argument('--output-dir', required=True, help='分析结果输出目录')
    
    args = parser.parse_args()
    run_build_analysis(args.cleaned_db, args.output_dir)
