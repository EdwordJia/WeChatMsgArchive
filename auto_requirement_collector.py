"""
智能需求收集器
从微信消息中自动识别需求和反馈，创建kanban任务
"""
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from wechat_index_db import WeChatIndexDB
from llm_requirement_analyzer import LLMRequirementAnalyzer

sys.stdout.reconfigure(encoding='utf-8')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('requirement_collector.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent
OUTPUT_DIR = PROJECT_DIR / 'output'
OUTPUT_DIR.mkdir(exist_ok=True)


class RequirementCollector:
    """需求收集器"""

    def __init__(self, use_llm=True, confidence_threshold=0.7):
        """
        初始化需求收集器

        Args:
            use_llm: 是否使用 LLM 分析（默认 True）
            confidence_threshold: LLM 置信度阈值（默认 0.7）
        """
        self.db = WeChatIndexDB()
        self.monitor_users = ['三叶草', '编程仝芷硕', 'Estelle', '烨林', '沐光', '密码机']
        self.use_llm = use_llm
        self.confidence_threshold = confidence_threshold

        # 初始化 LLM 分析器
        if self.use_llm:
            try:
                self.llm_analyzer = LLMRequirementAnalyzer()
                if self.llm_analyzer.client:
                    logger.info("✓ LLM 分析器初始化成功")
                else:
                    logger.warning("⚠ LLM API Key 未配置，将使用规则模式")
                    self.use_llm = False
            except Exception as e:
                logger.error(f"✗ LLM 分析器初始化失败: {e}")
                self.use_llm = False
                self.llm_analyzer = None
        else:
            self.llm_analyzer = None
            logger.info("使用规则模式（LLM 已禁用）")

        # 需求关键词（规则模式降级方案）
        self.requirement_keywords = [
            '需要', '希望', '能不能', '可以', '建议', '增加', '添加',
            '改成', '改为', '调整', '优化', '支持', '实现', '功能',
            '要不', '最好', '应该', '如果能', '想要'
        ]

        # Bug关键词（规则模式降级方案）
        self.bug_keywords = [
            'bug', 'BUG', '问题', '报错', '失败', '崩溃', '闪退', '卡死',
            '没有用', '不行', '无效', '异常', '错误', '不对', '失效',
            '没有反应', '没反应', '对接不上', '没对接', '不能用', '用不了',
            '修复', '修改', '运行不了', '解析不出', '没用'
        ]

        # 项目关键词映射
        self.project_keywords = {
            'syc-player': ['播放器', '视频', '音频', 'player', '三叶草'],
            'qt-lens': ['镜片', '检测', 'Qt', '林爱新', 'B-boy'],
            'wechat-archive': ['微信', '聊天记录', '解密', '数据库']
        }

    def identify_project(self, content: str, group: str) -> str:
        """识别项目"""
        for project, keywords in self.project_keywords.items():
            if any(kw in content or kw in group for kw in keywords):
                return project
        return 'general'

    def analyze_message(self, msg: dict, context: list = None) -> dict:
        """
        分析单条消息

        Args:
            msg: 消息字典
            context: 上下文消息列表（可选）

        Returns:
            分析结果字典，如果不是需求则返回 None
        """
        content = msg.get('content', '')
        if not content or len(content) < 5:
            return None

        # 优先使用 LLM 分析
        if self.use_llm and self.llm_analyzer:
            try:
                llm_result = self.llm_analyzer.analyze_message(content, context)

                # 检查置信度
                if llm_result['is_requirement'] and llm_result['confidence'] >= self.confidence_threshold:
                    logger.info(f"✓ LLM 识别需求: {llm_result['type']} | {llm_result['priority']} | 置信度 {llm_result['confidence']:.2f}")

                    # 识别项目
                    project = self.identify_project(content, msg.get('group', ''))

                    return {
                        'type': llm_result['type'],
                        'content': content,
                        'time': msg['time'],
                        'timestamp': msg['timestamp'],
                        'sender': msg.get('sender', ''),
                        'group': msg.get('group', ''),
                        'project': project,
                        'priority': llm_result['priority'],
                        'llm_title': llm_result['title'],
                        'llm_description': llm_result['description'],
                        'llm_tags': llm_result['tags'],
                        'llm_confidence': llm_result['confidence'],
                        'llm_reasoning': llm_result['reasoning']
                    }
                else:
                    logger.debug(f"LLM 置信度不足: {llm_result['confidence']:.2f} < {self.confidence_threshold}")
                    return None

            except Exception as e:
                logger.error(f"LLM 分析失败，降级到规则模式: {e}")
                # 降级到规则模式
                pass

        # 规则模式（降级方案）
        is_bug = any(kw in content for kw in self.bug_keywords)
        is_requirement = any(kw in content for kw in self.requirement_keywords)

        if not (is_bug or is_requirement):
            return None

        # 识别项目
        project = self.identify_project(content, msg.get('group', ''))

        # 确定优先级
        urgent_keywords = ['紧急', '急', '尽快', '马上', '立即', '崩溃', '闪退']
        priority = 'critical' if any(kw in content for kw in urgent_keywords) else (
            'high' if is_bug else 'medium'
        )

        logger.info(f"✓ 规则模式识别需求: {'bug' if is_bug else 'requirement'} | {priority}")

        return {
            'type': 'bug' if is_bug else 'requirement',
            'content': content,
            'time': msg['time'],
            'timestamp': msg['timestamp'],
            'sender': msg.get('sender', ''),
            'group': msg.get('group', ''),
            'project': project,
            'priority': priority
        }

    def collect_requirements(self, hours: int = 24) -> dict:
        """收集最近N小时的需求"""
        now = datetime.now()
        since_ts = int((now - timedelta(hours=hours)).timestamp())

        user_wxids = self.db.get_monitored_users_wxids(self.monitor_users)

        all_requirements = {}
        for user, wxids in user_wxids.items():
            user_messages = []
            for wxid in wxids:
                msgs = self.db.search_user_messages(wxid, since_time=since_ts, limit=500)
                user_messages.extend(msgs)

            if user_messages:
                requirements = []
                for i, msg in enumerate(user_messages):
                    # 提取上下文（前3条消息）
                    context = [m['content'] for m in user_messages[max(0, i-3):i] if m.get('content')]

                    analysis = self.analyze_message(msg, context)
                    if analysis:
                        analysis['user'] = user
                        requirements.append(analysis)

                if requirements:
                    all_requirements[user] = requirements

        return all_requirements

    def generate_kanban_tasks(self, requirements: dict) -> list:
        """生成kanban任务列表"""
        tasks = []

        for user, reqs in requirements.items():
            for req in reqs:
                # 优先使用 LLM 生成的标题和描述
                if 'llm_title' in req and req['llm_title']:
                    title = f"[{user}] {req['llm_title']}"
                    body = f"""## 反馈内容
{req['content']}

## LLM 分析
{req['llm_description']}

**置信度**: {req['llm_confidence']:.2f}
**分析理由**: {req['llm_reasoning']}

## 反馈人
{user} ({req['sender']})

## 反馈时间
{req['time']}

## 反馈群聊
{req['group']}

## 类型
{'🐛 Bug修复' if req['type'] == 'bug' else '✨ 功能需求'}
"""
                    tags = ['用户反馈', '自动创建', 'LLM分析', req['type'], user] + req.get('llm_tags', [])
                else:
                    # 规则模式生成的标题和描述
                    content_preview = req['content'][:40].replace('\n', ' ')
                    title = f"[{user}] {content_preview}"
                    body = f"""## 反馈内容
{req['content']}

## 反馈人
{user} ({req['sender']})

## 反馈时间
{req['time']}

## 反馈群聊
{req['group']}

## 类型
{'🐛 Bug修复' if req['type'] == 'bug' else '✨ 功能需求'}
"""
                    tags = ['用户反馈', '自动创建', req['type'], user]

                tasks.append({
                    'project': req['project'],
                    'title': title,
                    'body': body,
                    'priority': req['priority'],
                    'tags': tags,
                    'metadata': {
                        'source': 'wechat',
                        'user': user,
                        'timestamp': req['timestamp'],
                        'group': req['group'],
                        'llm_analyzed': 'llm_title' in req
                    }
                })

        return tasks

    def save_tasks(self, tasks: list, filename: str = 'pending_kanban_tasks.json'):
        """保存待创建任务"""
        output_file = OUTPUT_DIR / filename
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        return output_file

    def close(self):
        self.db.close()


def main():
    parser = argparse.ArgumentParser(description='智能需求收集器')
    parser.add_argument('--hours', type=int, default=24, help='收集最近N小时的需求（默认24）')
    parser.add_argument('--no-llm', action='store_true', help='禁用 LLM 分析，使用规则模式')
    parser.add_argument('--confidence', type=float, default=0.7, help='LLM 置信度阈值（默认0.7）')
    args = parser.parse_args()

    print('='*60)
    print('智能需求收集器')
    print('='*60)
    print(f'模式: {"规则模式" if args.no_llm else "LLM模式"}')
    print(f'时间范围: 最近 {args.hours} 小时')
    if not args.no_llm:
        print(f'置信度阈值: {args.confidence}')
    print('='*60)

    collector = RequirementCollector(use_llm=not args.no_llm, confidence_threshold=args.confidence)

    # 收集需求
    print(f'\n收集最近{args.hours}小时的需求和反馈...')
    requirements = collector.collect_requirements(hours=args.hours)

    total_count = sum(len(reqs) for reqs in requirements.values())
    print(f'找到 {total_count} 条需求/反馈\n')

    for user, reqs in requirements.items():
        print(f'{user}: {len(reqs)} 条')
        for req in reqs[:3]:  # 只显示前3条
            if 'llm_title' in req:
                print(f'  [{req["type"]}] {req["llm_title"]} (置信度: {req["llm_confidence"]:.2f})')
            else:
                print(f'  [{req["type"]}] {req["content"][:50]}...')

    # 生成kanban任务
    print('\n生成kanban任务...')
    tasks = collector.generate_kanban_tasks(requirements)

    if tasks:
        output_file = collector.save_tasks(tasks)
        print(f'生成 {len(tasks)} 个待创建任务')
        print(f'任务文件: {output_file}')

        # 按项目分组统计
        project_stats = {}
        for task in tasks:
            proj = task['project']
            project_stats[proj] = project_stats.get(proj, 0) + 1

        print('\n按项目分组:')
        for proj, count in project_stats.items():
            print(f'  {proj}: {count} 个任务')

        # 统计 LLM 分析的任务数
        llm_count = sum(1 for task in tasks if task['metadata'].get('llm_analyzed'))
        print(f'\nLLM 分析: {llm_count}/{len(tasks)} 个任务')
    else:
        print('无需创建任务')

    collector.close()
    print('\n完成！')
    print('='*60)


if __name__ == '__main__':
    main()
