#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
社交关系图谱分析
从微信聊天记录中构建社交网络，分析人际关系和社区结构
"""

import os
import sys
import sqlite3
import json
import networkx as nx
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Set
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
BASE_DIR = Path(__file__).parent
DECRYPTED_DB_DIR = BASE_DIR / 'output' / 'decrypted_db'
OUTPUT_DIR = BASE_DIR / 'output' / 'social_graph'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class SocialGraphAnalyzer:
    """社交关系图谱分析器"""

    def __init__(self, db_paths: List[Path], contact_db: Path):
        self.db_paths = db_paths
        self.contact_db = contact_db
        self.graph = nx.Graph()
        self.directed_graph = nx.DiGraph()
        self.contacts = {}
        self.chatrooms = {}

    def load_contacts(self):
        """加载联系人信息"""
        logger.info("加载联系人信息...")
        conn = sqlite3.connect(self.contact_db)
        cursor = conn.cursor()

        # 加载联系人
        cursor.execute("""
            SELECT UserName, Alias, Remark, NickName, Type
            FROM Contact
            WHERE Type IN (1, 3, 259)
        """)

        for row in cursor.fetchall():
            wxid, alias, remark, nickname, contact_type = row
            display_name = remark or nickname or alias or wxid
            self.contacts[wxid] = {
                'wxid': wxid,
                'display_name': display_name,
                'type': contact_type
            }

        # 加载群聊
        cursor.execute("""
            SELECT UserName, NickName
            FROM Contact
            WHERE Type = 2
        """)

        for row in cursor.fetchall():
            chatroom_id, chatroom_name = row
            self.chatrooms[chatroom_id] = {
                'chatroom_id': chatroom_id,
                'name': chatroom_name or chatroom_id
            }

        conn.close()
        logger.info(f"加载了 {len(self.contacts)} 个联系人，{len(self.chatrooms)} 个群聊")

    def build_graph_from_messages(self):
        """从消息记录构建社交网络图"""
        logger.info("开始构建社交网络图...")

        # 统计数据
        group_cooccurrence = defaultdict(lambda: defaultdict(int))  # 群聊共现
        reply_interactions = defaultdict(lambda: defaultdict(int))  # 回复互动
        private_chats = defaultdict(lambda: defaultdict(int))       # 私聊

        for db_path in self.db_paths:
            if not db_path.exists():
                continue

            logger.info(f"处理数据库: {db_path.name}")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            try:
                # 查询所有消息
                cursor.execute("""
                    SELECT StrTalker, IsSender, CreateTime, StrContent, Type
                    FROM MSG
                    ORDER BY StrTalker, CreateTime
                """)

                # 按聊天对象分组处理
                current_talker = None
                talker_messages = []

                for row in cursor.fetchall():
                    talker, is_sender, create_time, content, msg_type = row

                    # 新的聊天对象，处理上一个
                    if talker != current_talker:
                        if current_talker:
                            self._process_talker_messages(
                                current_talker, talker_messages,
                                group_cooccurrence, reply_interactions, private_chats
                            )
                        current_talker = talker
                        talker_messages = []

                    talker_messages.append({
                        'is_sender': is_sender,
                        'time': create_time,
                        'content': content or '',
                        'type': msg_type
                    })

                # 处理最后一个聊天对象
                if current_talker and talker_messages:
                    self._process_talker_messages(
                        current_talker, talker_messages,
                        group_cooccurrence, reply_interactions, private_chats
                    )

            except Exception as e:
                logger.error(f"处理数据库 {db_path.name} 失败: {e}")
            finally:
                conn.close()

        # 构建图
        self._build_graph_from_stats(group_cooccurrence, reply_interactions, private_chats)

        logger.info(f"社交网络图构建完成: {self.graph.number_of_nodes()} 个节点, {self.graph.number_of_edges()} 条边")

    def _process_talker_messages(self, talker: str, messages: List[Dict],
                                  group_cooccurrence: Dict, reply_interactions: Dict,
                                  private_chats: Dict):
        """处理单个聊天对象的消息"""

        # 判断是群聊还是私聊
        if talker.endswith('@chatroom'):
            # 群聊：分析共现和回复
            self._analyze_group_chat(talker, messages, group_cooccurrence, reply_interactions)
        else:
            # 私聊：直接建立关系
            my_wxid = 'wxid_ucag2pjrmhm822'  # 主角
            if talker in self.contacts:
                private_chats[my_wxid][talker] += len(messages)

    def _analyze_group_chat(self, chatroom_id: str, messages: List[Dict],
                           group_cooccurrence: Dict, reply_interactions: Dict):
        """分析群聊消息"""

        # 提取发言者（从消息内容中解析，微信群聊消息格式）
        # 注意：这里简化处理，实际需要解析 BytesExtra 字段

        # 统计共现：在同一个群聊中发言的人
        senders = set()
        for msg in messages:
            if not msg['is_sender']:
                # 非自己发送的消息，需要从内容中提取发送者
                # 简化处理：假设已知发送者
                pass
            else:
                senders.add('wxid_ucag2pjrmhm822')

        # 群聊共现：任意两个在同一群聊中发言的人
        senders_list = list(senders)
        for i in range(len(senders_list)):
            for j in range(i + 1, len(senders_list)):
                user1, user2 = senders_list[i], senders_list[j]
                group_cooccurrence[user1][user2] += 1
                group_cooccurrence[user2][user1] += 1

        # 回复互动：5分钟窗口内的连续发言
        REPLY_WINDOW = 5 * 60 * 1000  # 5分钟（毫秒）
        for i in range(len(messages) - 1):
            msg1 = messages[i]
            msg2 = messages[i + 1]

            if msg2['time'] - msg1['time'] <= REPLY_WINDOW:
                # 简化：假设是回复关系
                sender1 = 'wxid_ucag2pjrmhm822' if msg1['is_sender'] else 'unknown'
                sender2 = 'wxid_ucag2pjrmhm822' if msg2['is_sender'] else 'unknown'

                if sender1 != 'unknown' and sender2 != 'unknown' and sender1 != sender2:
                    reply_interactions[sender1][sender2] += 1

    def _build_graph_from_stats(self, group_cooccurrence: Dict,
                                reply_interactions: Dict, private_chats: Dict):
        """从统计数据构建图"""

        # 添加节点
        all_users = set()
        for d in [group_cooccurrence, reply_interactions, private_chats]:
            all_users.update(d.keys())
            for sub_d in d.values():
                all_users.update(sub_d.keys())

        for user in all_users:
            if user in self.contacts:
                self.graph.add_node(user, **self.contacts[user])
                self.directed_graph.add_node(user, **self.contacts[user])

        # 添加边：群聊共现
        for user1, targets in group_cooccurrence.items():
            for user2, weight in targets.items():
                if user1 < user2:  # 避免重复
                    self.graph.add_edge(user1, user2, weight=weight, type='cooccurrence')

        # 添加边：回复互动（有向）
        for user1, targets in reply_interactions.items():
            for user2, weight in targets.items():
                self.directed_graph.add_edge(user1, user2, weight=weight, type='reply')
                # 无向图中也添加
                if self.graph.has_edge(user1, user2):
                    self.graph[user1][user2]['reply_weight'] = weight
                else:
                    self.graph.add_edge(user1, user2, weight=weight, type='reply')

        # 添加边：私聊
        for user1, targets in private_chats.items():
            for user2, weight in targets.items():
                if self.graph.has_edge(user1, user2):
                    self.graph[user1][user2]['private_weight'] = weight
                else:
                    self.graph.add_edge(user1, user2, weight=weight, type='private')

    def analyze_centrality(self) -> Dict:
        """计算中心性指标"""
        logger.info("计算中心性指标...")

        metrics = {}

        # 度中心性
        degree_centrality = nx.degree_centrality(self.graph)

        # PageRank
        pagerank = nx.pagerank(self.graph, weight='weight')

        # 介数中心性（计算量大，只对小图计算）
        if self.graph.number_of_nodes() < 500:
            betweenness = nx.betweenness_centrality(self.graph, weight='weight')
        else:
            betweenness = {}

        # 接近中心性
        if self.graph.number_of_nodes() < 500:
            closeness = nx.closeness_centrality(self.graph)
        else:
            closeness = {}

        # 整合结果
        for node in self.graph.nodes():
            metrics[node] = {
                'degree_centrality': degree_centrality.get(node, 0),
                'pagerank': pagerank.get(node, 0),
                'betweenness': betweenness.get(node, 0),
                'closeness': closeness.get(node, 0),
                'degree': self.graph.degree(node)
            }

        return metrics

    def detect_communities(self) -> Dict:
        """社区发现"""
        logger.info("进行社区发现...")

        try:
            # 使用 Louvain 算法
            import community as community_louvain
            partition = community_louvain.best_partition(self.graph, weight='weight')
        except ImportError:
            logger.warning("未安装 python-louvain，使用 greedy_modularity_communities")
            from networkx.algorithms import community
            communities = community.greedy_modularity_communities(self.graph, weight='weight')
            partition = {}
            for i, comm in enumerate(communities):
                for node in comm:
                    partition[node] = i

        # 统计每个社区的大小
        community_sizes = Counter(partition.values())

        logger.info(f"发现 {len(community_sizes)} 个社区")
        for comm_id, size in community_sizes.most_common(10):
            logger.info(f"  社区 {comm_id}: {size} 人")

        return partition

    def generate_report(self, centrality: Dict, communities: Dict):
        """生成分析报告"""
        logger.info("生成分析报告...")

        # 保存 JSON 数据
        report_data = {
            'summary': {
                'total_nodes': self.graph.number_of_nodes(),
                'total_edges': self.graph.number_of_edges(),
                'num_communities': len(set(communities.values())),
                'generated_at': datetime.now().isoformat()
            },
            'top_central_users': [],
            'communities': {}
        }

        # Top 20 中心性用户
        sorted_users = sorted(centrality.items(), key=lambda x: x[1]['pagerank'], reverse=True)
        for wxid, metrics in sorted_users[:20]:
            user_info = self.contacts.get(wxid, {'display_name': wxid})
            report_data['top_central_users'].append({
                'wxid': wxid,
                'display_name': user_info['display_name'],
                'pagerank': metrics['pagerank'],
                'degree': metrics['degree'],
                'community': communities.get(wxid, -1)
            })

        # 社区信息
        community_members = defaultdict(list)
        for wxid, comm_id in communities.items():
            user_info = self.contacts.get(wxid, {'display_name': wxid})
            community_members[comm_id].append({
                'wxid': wxid,
                'display_name': user_info['display_name']
            })

        for comm_id, members in community_members.items():
            report_data['communities'][str(comm_id)] = {
                'size': len(members),
                'members': members[:10]  # 只保存前10个
            }

        # 保存 JSON
        json_path = OUTPUT_DIR / 'social_graph_analysis.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        logger.info(f"JSON 报告已保存: {json_path}")

        # 生成 Markdown 报告
        self._generate_markdown_report(report_data, centrality, communities)

    def _generate_markdown_report(self, report_data: Dict, centrality: Dict, communities: Dict):
        """生成 Markdown 报告"""

        md_lines = [
            "# 社交关系图谱分析报告",
            "",
            f"生成时间: {report_data['summary']['generated_at']}",
            "",
            "## 网络概览",
            "",
            f"- **节点数**: {report_data['summary']['total_nodes']}",
            f"- **边数**: {report_data['summary']['total_edges']}",
            f"- **社区数**: {report_data['summary']['num_communities']}",
            "",
            "---",
            "",
            "## Top 20 核心人物（按 PageRank 排序）",
            "",
            "| 排名 | 姓名 | PageRank | 度数 | 社区 |",
            "|------|------|----------|------|------|"
        ]

        for i, user in enumerate(report_data['top_central_users'], 1):
            md_lines.append(
                f"| {i} | {user['display_name']} | {user['pagerank']:.4f} | {user['degree']} | {user['community']} |"
            )

        md_lines.extend([
            "",
            "---",
            "",
            "## 社区结构",
            ""
        ])

        # 按社区大小排序
        sorted_communities = sorted(
            report_data['communities'].items(),
            key=lambda x: x[1]['size'],
            reverse=True
        )

        for comm_id, comm_info in sorted_communities[:10]:
            md_lines.append(f"### 社区 {comm_id} ({comm_info['size']} 人)")
            md_lines.append("")
            md_lines.append("核心成员:")
            for member in comm_info['members']:
                md_lines.append(f"- {member['display_name']}")
            md_lines.append("")

        # 保存 Markdown
        md_path = OUTPUT_DIR / 'social_graph_analysis.md'
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))

        logger.info(f"Markdown 报告已保存: {md_path}")

    def export_graph(self):
        """导出图数据"""
        logger.info("导出图数据...")

        # 导出为 GraphML（可用于 Gephi 等工具）
        graphml_path = OUTPUT_DIR / 'social_graph.graphml'
        nx.write_graphml(self.graph, graphml_path)
        logger.info(f"GraphML 已保存: {graphml_path}")

        # 导出为 JSON（可用于 ECharts/D3.js）
        graph_json = {
            'nodes': [],
            'links': []
        }

        for node in self.graph.nodes():
            user_info = self.contacts.get(node, {'display_name': node})
            graph_json['nodes'].append({
                'id': node,
                'name': user_info['display_name'],
                'symbolSize': self.graph.degree(node)
            })

        for u, v, data in self.graph.edges(data=True):
            graph_json['links'].append({
                'source': u,
                'target': v,
                'weight': data.get('weight', 1)
            })

        json_path = OUTPUT_DIR / 'social_graph.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(graph_json, f, ensure_ascii=False, indent=2)

        logger.info(f"图 JSON 已保存: {json_path}")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始社交关系图谱分析")
    logger.info("=" * 60)

    # 查找数据库文件
    msg_dbs = list(DECRYPTED_DB_DIR.glob('Multi/MSG*.db'))
    contact_db = DECRYPTED_DB_DIR / 'MicroMsg.db'

    if not msg_dbs:
        logger.error("未找到消息数据库")
        return

    if not contact_db.exists():
        logger.error("未找到联系人数据库")
        return

    logger.info(f"找到 {len(msg_dbs)} 个消息数据库")

    # 创建分析器
    analyzer = SocialGraphAnalyzer(msg_dbs, contact_db)

    # 1. 加载联系人
    analyzer.load_contacts()

    # 2. 构建社交网络图
    analyzer.build_graph_from_messages()

    # 3. 计算中心性
    centrality = analyzer.analyze_centrality()

    # 4. 社区发现
    communities = analyzer.detect_communities()

    # 5. 生成报告
    analyzer.generate_report(centrality, communities)

    # 6. 导出图数据
    analyzer.export_graph()

    logger.info("=" * 60)
    logger.info("社交关系图谱分析完成！")
    logger.info(f"输出目录: {OUTPUT_DIR}")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
