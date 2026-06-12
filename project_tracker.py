#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
副业项目追踪
从微信聊天记录中识别和追踪"长腿叔叔"的副业项目
"""

import os
import sys
import sqlite3
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, List, Tuple, Set
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
OUTPUT_DIR = BASE_DIR / 'output' / 'side_projects'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 副业项目关键词词典
PROJECT_KEYWORDS = {
    '技术类': [
        'AI', '人工智能', '机器学习', '深度学习', 'GPT', 'Claude', 'LLM',
        '大模型', '算法', '开发', '编程', 'Python', 'Java', 'Go',
        '前端', '后端', '全栈', '架构', '系统', '平台', '框架',
        '开源', 'GitHub', '代码', '项目', '产品', 'SaaS', 'API'
    ],
    '商业类': [
        '创业', '合伙', '投资', '融资', '股权', '分红', '收益',
        '客户', '用户', '市场', '推广', '营销', '销售', '渠道',
        '商业模式', '盈利', '变现', '订单', '合同', '签约',
        '外包', '接单', '项目', '需求', '报价', '预算'
    ],
    '咨询类': [
        '咨询', '顾问', '培训', '讲座', '分享', '课程', '教学',
        '指导', '辅导', '方案', '建议', '规划', '策略'
    ],
    '内容类': [
        '写作', '文章', '博客', '公众号', '视频', '直播', '短视频',
        '自媒体', '内容', '创作', '运营', '粉丝', '流量', '变现'
    ],
    '其他': [
        '副业', '兼职', '接私活', '赚钱', '收入', '外快',
        '机会', '合作', '资源', '人脉', '介绍'
    ]
}

# 项目状态关键词
STATUS_KEYWORDS = {
    '启动': ['开始', '启动', '立项', '准备', '计划', '打算', '想做', '要做'],
    '进行中': ['进行', '推进', '开发', '实施', '执行', '做', '在做', '正在'],
    '完成': ['完成', '上线', '发布', '交付', '结束', '搞定', '做完了'],
    '暂停': ['暂停', '搁置', '延期', '推迟', '等待', '先放放'],
    '取消': ['取消', '放弃', '不做了', '算了', '黄了']
}

# 时间表达式模式
TIME_PATTERNS = [
    r'(\d{4})年(\d{1,2})月',
    r'(\d{1,2})月(\d{1,2})日',
    r'(上|下|这|本|去)个?(周|月|季度|年)',
    r'(今天|明天|后天|昨天|前天)',
    r'(最近|近期|这段时间)'
]


class ProjectTracker:
    """副业项目追踪器"""

    def __init__(self, db_paths: List[Path], my_wxid: str = 'wxid_ucag2pjrmhm822'):
        self.db_paths = db_paths
        self.my_wxid = my_wxid
        self.projects = {}
        self.project_events = defaultdict(list)

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
                # 只查询自己发送的消息
                cursor.execute("""
                    SELECT StrTalker, IsSender, CreateTime, StrContent, Type
                    FROM MSG
                    WHERE IsSender = 1 AND Type = 1
                    ORDER BY CreateTime
                """)

                for row in cursor.fetchall():
                    talker, is_sender, create_time, content, msg_type = row
                    if content:
                        messages.append({
                            'talker': talker,
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

    def extract_projects(self, messages: List[Dict]):
        """从消息中提取项目"""
        logger.info("提取项目...")

        for msg in messages:
            content = msg['content']
            msg_time = msg['datetime']

            # 检查是否包含项目关键词
            project_keywords_found = []
            for category, keywords in PROJECT_KEYWORDS.items():
                for keyword in keywords:
                    if keyword in content:
                        project_keywords_found.append((category, keyword))

            if not project_keywords_found:
                continue

            # 提取项目名称（简单规则：关键词前后的名词短语）
            project_name = self._extract_project_name(content, project_keywords_found)

            # 识别项目状态
            status = self._identify_status(content)

            # 提取时间信息
            time_info = self._extract_time_info(content)

            # 创建或更新项目
            if project_name:
                if project_name not in self.projects:
                    self.projects[project_name] = {
                        'name': project_name,
                        'categories': list(set([cat for cat, _ in project_keywords_found])),
                        'keywords': list(set([kw for _, kw in project_keywords_found])),
                        'first_mention': msg_time,
                        'last_mention': msg_time,
                        'status': status or '未知',
                        'events': [],
                        'mentions': 1
                    }
                else:
                    self.projects[project_name]['last_mention'] = msg_time
                    self.projects[project_name]['mentions'] += 1
                    if status:
                        self.projects[project_name]['status'] = status

                # 记录事件
                event = {
                    'time': msg_time,
                    'content': content[:200],  # 只保存前200字符
                    'status': status,
                    'time_info': time_info,
                    'talker': msg['talker']
                }
                self.projects[project_name]['events'].append(event)
                self.project_events[project_name].append(event)

        logger.info(f"识别了 {len(self.projects)} 个项目")

    def _extract_project_name(self, content: str, keywords_found: List[Tuple]) -> str:
        """提取项目名称"""
        # 简单规则：使用第一个关键词作为项目名称
        # 实际应用中可以使用 NER 或更复杂的规则
        if keywords_found:
            return keywords_found[0][1]

        # 尝试提取引号中的内容
        quoted = re.findall(r'[「『""](.+?)[」』""]', content)
        if quoted:
            return quoted[0]

        # 尝试提取"XX项目"模式
        project_match = re.search(r'(\w+)(项目|系统|平台|产品|工具)', content)
        if project_match:
            return project_match.group(0)

        return None

    def _identify_status(self, content: str) -> str:
        """识别项目状态"""
        for status, keywords in STATUS_KEYWORDS.items():
            for keyword in keywords:
                if keyword in content:
                    return status
        return None

    def _extract_time_info(self, content: str) -> str:
        """提取时间信息"""
        for pattern in TIME_PATTERNS:
            match = re.search(pattern, content)
            if match:
                return match.group(0)
        return None

    def analyze_projects(self):
        """分析项目"""
        logger.info("分析项目...")

        for project_name, project in self.projects.items():
            # 计算项目持续时间
            if project['first_mention'] and project['last_mention']:
                duration = (project['last_mention'] - project['first_mention']).days
                project['duration_days'] = duration

            # 分析活跃度
            events = project['events']
            if len(events) > 1:
                # 计算平均提及间隔
                time_diffs = []
                for i in range(1, len(events)):
                    diff = (events[i]['time'] - events[i-1]['time']).days
                    time_diffs.append(diff)
                project['avg_mention_interval'] = sum(time_diffs) / len(time_diffs) if time_diffs else 0
            else:
                project['avg_mention_interval'] = 0

            # 判断项目活跃状态
            if project['last_mention']:
                days_since_last = (datetime.now() - project['last_mention']).days
                if days_since_last > 90:
                    project['active_status'] = '已停滞'
                elif days_since_last > 30:
                    project['active_status'] = '不活跃'
                else:
                    project['active_status'] = '活跃'
            else:
                project['active_status'] = '未知'

    def generate_report(self):
        """生成报告"""
        logger.info("生成报告...")

        # 保存 JSON 数据
        report_data = {
            'summary': {
                'total_projects': len(self.projects),
                'active_projects': len([p for p in self.projects.values() if p.get('active_status') == '活跃']),
                'inactive_projects': len([p for p in self.projects.values() if p.get('active_status') == '不活跃']),
                'stalled_projects': len([p for p in self.projects.values() if p.get('active_status') == '已停滞']),
                'generated_at': datetime.now().isoformat()
            },
            'projects': []
        }

        # 按最后提及时间排序
        sorted_projects = sorted(
            self.projects.items(),
            key=lambda x: x[1].get('last_mention', datetime.min),
            reverse=True
        )

        for project_name, project in sorted_projects:
            project_data = {
                'name': project_name,
                'categories': project['categories'],
                'keywords': project['keywords'],
                'first_mention': project['first_mention'].isoformat() if project['first_mention'] else None,
                'last_mention': project['last_mention'].isoformat() if project['last_mention'] else None,
                'duration_days': project.get('duration_days', 0),
                'mentions': project['mentions'],
                'status': project['status'],
                'active_status': project.get('active_status', '未知'),
                'avg_mention_interval': project.get('avg_mention_interval', 0),
                'events': [
                    {
                        'time': e['time'].isoformat() if e['time'] else None,
                        'content': e['content'],
                        'status': e['status']
                    }
                    for e in project['events'][:10]  # 只保存前10个事件
                ]
            }
            report_data['projects'].append(project_data)

        # 保存 JSON
        json_path = OUTPUT_DIR / 'side_projects.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        logger.info(f"JSON 报告已保存: {json_path}")

        # 生成 Markdown 报告
        self._generate_markdown_report(report_data)

    def _generate_markdown_report(self, report_data: Dict):
        """生成 Markdown 报告"""

        md_lines = [
            "# 副业项目追踪报告",
            "",
            f"生成时间: {report_data['summary']['generated_at']}",
            "",
            "## 项目概览",
            "",
            f"- **总项目数**: {report_data['summary']['total_projects']}",
            f"- **活跃项目**: {report_data['summary']['active_projects']}",
            f"- **不活跃项目**: {report_data['summary']['inactive_projects']}",
            f"- **已停滞项目**: {report_data['summary']['stalled_projects']}",
            "",
            "---",
            "",
            "## 项目列表",
            ""
        ]

        for project in report_data['projects']:
            md_lines.append(f"### {project['name']}")
            md_lines.append("")
            md_lines.append(f"**分类**: {', '.join(project['categories'])}")
            md_lines.append(f"**关键词**: {', '.join(project['keywords'])}")
            md_lines.append(f"**状态**: {project['status']} ({project['active_status']})")
            md_lines.append(f"**首次提及**: {project['first_mention']}")
            md_lines.append(f"**最后提及**: {project['last_mention']}")
            md_lines.append(f"**持续时间**: {project['duration_days']} 天")
            md_lines.append(f"**提及次数**: {project['mentions']}")
            md_lines.append("")

            if project['events']:
                md_lines.append("**关键事件**:")
                md_lines.append("")
                for event in project['events'][:5]:  # 只显示前5个
                    status_str = f" [{event['status']}]" if event['status'] else ""
                    md_lines.append(f"- {event['time']}{status_str}: {event['content']}")
                md_lines.append("")

            md_lines.append("---")
            md_lines.append("")

        # 保存 Markdown
        md_path = OUTPUT_DIR / 'side_projects.md'
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))

        logger.info(f"Markdown 报告已保存: {md_path}")

    def generate_timeline(self):
        """生成项目时间线"""
        logger.info("生成项目时间线...")

        timeline = []
        for project_name, events in self.project_events.items():
            for event in events:
                timeline.append({
                    'project': project_name,
                    'time': event['time'],
                    'content': event['content'],
                    'status': event['status']
                })

        # 按时间排序
        timeline.sort(key=lambda x: x['time'] if x['time'] else datetime.min)

        # 生成时间线 Markdown
        md_lines = [
            "# 副业项目时间线",
            "",
            f"生成时间: {datetime.now().isoformat()}",
            "",
            "---",
            ""
        ]

        current_month = None
        for item in timeline:
            if not item['time']:
                continue

            # 按月分组
            month = item['time'].strftime('%Y年%m月')
            if month != current_month:
                current_month = month
                md_lines.append(f"## {month}")
                md_lines.append("")

            date_str = item['time'].strftime('%Y-%m-%d')
            status_str = f" [{item['status']}]" if item['status'] else ""
            md_lines.append(f"- **{date_str}** - {item['project']}{status_str}")
            md_lines.append(f"  > {item['content']}")
            md_lines.append("")

        # 保存时间线
        timeline_path = OUTPUT_DIR / 'project_timeline.md'
        with open(timeline_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines))

        logger.info(f"时间线已保存: {timeline_path}")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始副业项目追踪")
    logger.info("=" * 60)

    # 查找数据库文件
    msg_dbs = list(DECRYPTED_DB_DIR.glob('Multi/MSG*.db'))

    if not msg_dbs:
        logger.error("未找到消息数据库")
        return

    logger.info(f"找到 {len(msg_dbs)} 个消息数据库")

    # 创建追踪器
    tracker = ProjectTracker(msg_dbs)

    # 1. 加载消息
    messages = tracker.load_messages()

    # 2. 提取项目
    tracker.extract_projects(messages)

    # 3. 分析项目
    tracker.analyze_projects()

    # 4. 生成报告
    tracker.generate_report()

    # 5. 生成时间线
    tracker.generate_timeline()

    logger.info("=" * 60)
    logger.info("副业项目追踪完成！")
    logger.info(f"输出目录: {OUTPUT_DIR}")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
