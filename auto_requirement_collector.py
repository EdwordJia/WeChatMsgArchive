"""
智能需求收集器
从微信消息中自动识别需求和反馈，创建kanban任务
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
from wechat_index_db import WeChatIndexDB

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_DIR = Path(__file__).parent
OUTPUT_DIR = PROJECT_DIR / 'output'
OUTPUT_DIR.mkdir(exist_ok=True)


class RequirementCollector:
    """需求收集器"""

    def __init__(self):
        self.db = WeChatIndexDB()
        self.monitor_users = ['三叶草', '编程仝芷硕', 'Estelle', '烨林', '沐光', '密码机']

        # 需求关键词
        self.requirement_keywords = [
            '需要', '希望', '能不能', '可以', '建议', '增加', '添加',
            '改成', '改为', '调整', '优化', '支持', '实现', '功能',
            '要不', '最好', '应该', '如果能', '想要'
        ]

        # Bug关键词
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

    def analyze_message(self, msg: dict) -> dict:
        """分析单条消息"""
        content = msg.get('content', '')
        if not content or len(content) < 5:
            return None

        # 检测类型
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
                for msg in user_messages:
                    analysis = self.analyze_message(msg)
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
                # 生成任务标题
                content_preview = req['content'][:40].replace('\n', ' ')
                title = f"[{user}] {content_preview}"

                # 生成任务描述
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

                tasks.append({
                    'project': req['project'],
                    'title': title,
                    'body': body,
                    'priority': req['priority'],
                    'tags': ['用户反馈', '自动创建', req['type'], user],
                    'metadata': {
                        'source': 'wechat',
                        'user': user,
                        'timestamp': req['timestamp'],
                        'group': req['group']
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
    print('='*60)
    print('智能需求收集器')
    print('='*60)

    collector = RequirementCollector()

    # 收集最近24小时的需求
    print('\n收集最近24小时的需求和反馈...')
    requirements = collector.collect_requirements(hours=24)

    total_count = sum(len(reqs) for reqs in requirements.values())
    print(f'找到 {total_count} 条需求/反馈\n')

    for user, reqs in requirements.items():
        print(f'{user}: {len(reqs)} 条')
        for req in reqs[:3]:  # 只显示前3条
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
    else:
        print('无需创建任务')

    collector.close()
    print('\n完成！')
    print('='*60)


if __name__ == '__main__':
    main()
