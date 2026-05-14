#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
商机识别
从微信聊天记录中识别可商业化的项目机会
"""

import os
import sys
import sqlite3
import json
import re
from datetime import datetime
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, List, Tuple
import jieba
import jieba.analyse
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
OUTPUT_DIR = BASE_DIR / 'output' / 'business_opportunities'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 商机关键词
OPPORTUNITY_KEYWORDS = {
    '需求痛点': [
        '痛点', '问题', '困难', '麻烦', '不方便', '效率低', '成本高',
        '需要', '想要', '希望', '能不能', '有没有', '怎么办',
        '太慢', '太贵', '太复杂', '不好用', '不稳定'
    ],
    '市场需求': [
        '市场', '需求', '客户', '用户', '订单', '询价', '咨询',
        '很多人', '大家都', '行业', '趋势', '机会', '空白',
        '竞争', '对手', '份额', '增长'
    ],
    '技术可行': [
        '可以做', '能实现', '有方案', '技术', '开发', '实现',
        '简单', '容易', '快速', '成熟', '现成', '开源'
    ],
    '商业价值': [
        '赚钱', '盈利', '收益', '变现', '付费', '订阅', '会员',
        '价格', '报价', '成本', '利润', '回报', 'ROI',
        '投资', '融资', '估值', '商业模式'
    ],
    '资源优势': [
        '资源', '人脉', '渠道', '客户', '技术', '团队', '经验',
        '优势', '擅长', '专业', '积累', '关系', '合作'
    ]
}

# 情感倾向词
SENTIMENT_KEYWORDS = {
    '积极': [
        '好', '不错', '可以', '行', '赞', '棒', '优秀', '厉害',
        '成功', '完成', '搞定', '解决', '满意', '喜欢'
    ],
    '消极': [
        '不行', '不好', '差', '烂', '糟糕', '失败', '问题', '麻烦',
        '困难', '难', '复杂', '慢', '贵', '不满意'
    ],
    '中性': [
        '可能', '也许', '或许', '大概', '应该', '一般', '还行'
    ]
}

# 商业价值评分权重
VALUE_WEIGHTS = {
    '需求痛点': 0.25,
    '市场需求': 0.25,
    '技术可行': 0.20,
    '商业价值': 0.20,
    '资源优势': 0.10
}


class OpportunityAnalyzer:
    """商机分析器"""

    def __init__(self, db_paths: List[Path], my_wxid: str = 'wxid_ucag2pjrmhm822'):
        self.db_paths = db_paths
        self.my_wxid = my_wxid
        self.opportunities = []
        self.conversations = defaultdict(list)

    def load_messages(self) -> List[Dict]:
        """加载所有消息"""
        logger.info("加载消息...")
        messages = []

        for db_path in self.db_paths:
            if not db_path.exists():
                continue

            logger.info(f"处理数据库: {db_path.name}")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            try:
                # 查询所有文本消息
                cursor.execute("""
                    SELECT StrTalker, IsSender, CreateTime, StrContent, Type
                    FROM MSG
                    WHERE Type = 1
                    ORDER BY CreateTime
                """)

                for row in cursor.fetchall():
                    talker, is_sender, create_time, content, msg_type = row
                    if content:
                        messages.append({
                            'talker': talker,
                            'is_sender': is_sender,
                            'time': create_time,
                            'datetime': datetime.fromtimestamp(create_time / 1000) if create_time else None,
                            'content': content
                        })

            except Exception as e:
                logger.error(f"处理数据库 {db_path.name} 失败: {e}")
            finally:
                conn.close()

        logger.info(f"加载了 {len(messages)} 条消息")
        return messages

    def analyze_opportunities(self, messages: List[Dict]):
        """分析商机"""
        logger.info("分析商机...")

        # 按对话分组
        for msg in messages:
            self.conversations[msg['talker']].append(msg)

        # 分析每个对话
        for talker, msgs in self.conversations.items():
            self._analyze_conversation(talker, msgs)

        logger.info(f"识别了 {len(self.opportunities)} 个商机")

    def _analyze_conversation(self, talker: str, messages: List[Dict]):
        """分析单个对话"""
        # 合并消息内容
        full_text = ' '.join([msg['content'] for msg in messages])

        # 检查是否包含商机关键词
        keyword_scores = {}
        for category, keywords in OPPORTUNITY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in full_text)
            keyword_scores[category] = score

        # 计算总分
        total_score = sum(
            keyword_scores.get(cat, 0) * weight
            for cat, weight in VALUE_WEIGHTS.items()
        )

        # 如果分数足够高，记录为商机
        if total_score > 1.0:  # 阈值
            # 提取关键信息
            keywords = jieba.analyse.extract_tags(full_text, topK=10)

            # 情感分析
            sentiment = self._analyze_sentiment(full_text)

            # 提取需求描述
            pain_points = self._extract_pain_points(messages)

            opportunity = {
                'talker': talker,
                'score': round(total_score, 2),
                'keyword_scores': keyword_scores,
                'keywords': keywords,
                'sentiment': sentiment,
                'pain_points': pain_points,
                'message_count': len(messages),
                'first_time': messages[0]['datetime'].isoformat() if messages[0]['datetime'] else None,
                'last_time': messages[-1]['datetime'].isoformat() if messages[-1]['datetime'] else None,
                'sample_messages': [
                    {
                        'time': msg['datetime'].isoformat() if msg['datetime'] else None,
                        'content': msg['content'][:200],
                        'is_sender': msg['is_sender']
                    }
                    for msg in messages[:5]  # 只保存前5条
                ]
            }

            self.opportunities.append(opportunity)

    def _analyze_sentiment(self, text: str) -> Dict:
        """情感分析"""
        sentiment_scores = {
            '积极': 0,
            '消极': 0,
            '中性': 0
        }

        for sentiment, keywords in SENTIMENT_KEYWORDS.items():
            sentiment_scores[sentiment] = sum(1 for kw in keywords if kw in text)

        total = sum(sentiment_scores.values())
        if total > 0:
            sentiment_ratio = {
                k: round(v / total, 2)
                for k, v in sentiment_scores.items()
            }
        else:
            sentiment_ratio = {'中性': 1.0}

        return {
            'scores': sentiment_scores,
            'ratio': sentiment_ratio,
            'dominant': max(sentiment_ratio.items(), key=lambda x: x[1])[0]
        }

    def _extract_pain_points(self, messages: List[Dict]) -> List[str]:
        """提取痛点描述"""
        pain_points = []

        pain_patterns = [
            r'(不能|无法|不会|不行|没有|缺少)(.{1,20})',
            r'(.{1,20})(太慢|太贵|太复杂|不好用|不稳定)',
            r'(问题|困难|麻烦|痛点)是(.{1,30})',
            r'(需要|想要|希望)(.{1,30})'
        ]

        for msg in messages:
            content = msg['content']
            for pattern in pain_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    pain_point = ''.join(match).strip()
                    if len(pain_point) > 5:  # 过滤太短的
                        pain_points.append(pain_point)

        return pain_points[:10]  # 最多返回10个

    def rank_opportunities(self):
        """对商机进行排序"""
        logger.info("对商机进行排序...")

        # 按分数排序
        self.opportunities.sort(key=lambda x: x['score'], reverse=True)

        # 添加排名
        for i, opp in enumerate(self.opportunities, 1):
            opp['rank'] = i

    def generate_report(self):
        """生成报告"""
        logger.info("生成报告...")

        # 保存 JSON 数据
        report_data = {
            'summary': {
                'total_opportunities': len(self.opportunities),
                'high_value': len([o for o in self.opportunities if o['score'] >= 3.0]),
                'medium_value': len([o for o in self.opportunities if 2.0 <= o['score'] < 3.0]),
                'low_value': len([o for o in self.opportunities if o['score'] < 2.0]),
                'generated_at': datetime.now().isoformat()
            },
            'opportunities': self.opportunities[:50]  # 只保存前50个
        }

        # 保存 JSON
        json_path = OUTPUT_DIR / 'business_opportunities.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        logger.info(f"JSON 报告已保存: {json_path}")

        # 生成 Markdown 报告
        self._generate_markdown_report(report_data)

    def _generate_markdown_report(self, report_data: Dict):
        """生成 Markdown 报告"""

        md_lines = [
            "# 商机识别报告",
            "",
            f"生成时间: {report_data['summary']['generated_at']}",
            "",
            "## 商机概览",
            "",
            f"- **总商机数**: {report_data['summary']['total_opportunities']}",
            f"- **高价值商机** (≥3.0分): {report_data['summary']['high_value']}",
            f"- **中等价值商机** (2.0-3.0分): {report_data['summary']['medium_value']}",
            f"- **低价值商机** (<2.0分): {report_data['summary']['low_value']}",
            "",
            "---",
            "",
            "## 商机列表",
            ""
        ]

        for opp in report_data['opportunities'][:20]:  # 只显示前20个
            md_lines.append(f"### #{opp['rank']} - {opp['talker']}")
            md_lines.append("")
            md_lines.append(f"**综合评分**: {opp['score']} 分")
            md_lines.append("")
            md_lines.append("**维度评分**:")
            for cat, score in opp['keyword_scores'].items():
                md_lines.append(f"- {cat}: {score}")
            md_lines.append("")

            md_lines.append(f"**关键词**: {', '.join(opp['keywords'])}")
            md_lines.append(f"**情感倾向**: {opp['sentiment']['dominant']} ({opp['sentiment']['ratio']})")
            md_lines.append(f"**消息数量**: {opp['message_count']}")
            md_lines.append("")

            if opp['pain_points']:
                md_lines.append("**识别的痛点**:")
                for pain in opp['pain_points'][:5]:
                    md_lines.append(f"- {pain}")
                md_lines.append("")

            if opp['sample_messages']:
                md_lines.append("**对话样本**:")
                md_lines.append("")
                for msg in opp['sample_messages'][:3]:
                    sender = "我" if msg['is_sender'] else "对方"
                    md_lines.append(f"- [{sender}] {msg['content']}")
                md_lines.append("")

            md_lines.append("---")
            md_lines.append("")

        # 保存 Markdown
        md_path = OUTPUT_DIR / 'business_opportunities.md'
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))

        logger.info(f"Markdown 报告已保存: {md_path}")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始商机识别")
    logger.info("=" * 60)

    # 查找数据库文件
    msg_dbs = list(DECRYPTED_DB_DIR.glob('Multi/MSG*.db'))

    if not msg_dbs:
        logger.error("未找到消息数据库")
        return

    logger.info(f"找到 {len(msg_dbs)} 个消息数据库")

    # 创建分析器
    analyzer = OpportunityAnalyzer(msg_dbs)

    # 1. 加载消息
    messages = analyzer.load_messages()

    # 2. 分析商机
    analyzer.analyze_opportunities(messages)

    # 3. 排序
    analyzer.rank_opportunities()

    # 4. 生成报告
    analyzer.generate_report()

    logger.info("=" * 60)
    logger.info("商机识别完成！")
    logger.info(f"输出目录: {OUTPUT_DIR}")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
