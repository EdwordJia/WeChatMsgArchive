"""
微信消息自动化需求收集系统 - 完整流程
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_DIR = Path(__file__).parent


def step1_decrypt_and_sync():
    """步骤1: 解密数据库并同步到索引"""
    print('\n[步骤1] 解密微信数据库并同步到索引')
    print('-' * 60)

    from wechat_monitor import decrypt_db
    from wechat_index_db import incremental_sync

    decrypt_db()
    new_count = incremental_sync()
    print(f'✓ 同步了 {new_count} 条新消息')
    return new_count


def step2_collect_requirements(hours=24):
    """步骤2: 收集需求和反馈"""
    print(f'\n[步骤2] 收集最近{hours}小时的需求和反馈')
    print('-' * 60)

    from auto_requirement_collector import RequirementCollector

    collector = RequirementCollector()
    requirements = collector.collect_requirements(hours=hours)

    total = sum(len(reqs) for reqs in requirements.values())
    print(f'✓ 找到 {total} 条需求/反馈')

    for user, reqs in requirements.items():
        print(f'  {user}: {len(reqs)} 条')

    # 生成任务
    tasks = collector.generate_kanban_tasks(requirements)

    if tasks:
        output_file = collector.save_tasks(tasks)
        print(f'✓ 生成 {len(tasks)} 个待创建任务')
        print(f'  文件: {output_file}')

    collector.close()
    return tasks


def step3_filter_tasks(tasks, days=7, min_priority='medium'):
    """步骤3: 筛选任务（只创建最近N天的高优先级任务）"""
    print(f'\n[步骤3] 筛选任务（最近{days}天，优先级>={min_priority}）')
    print('-' * 60)

    priority_order = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
    min_priority_level = priority_order.get(min_priority, 1)

    now = datetime.now()
    cutoff_time = int((now - timedelta(days=days)).timestamp())

    filtered = []
    for task in tasks:
        task_time = task['metadata']['timestamp']
        task_priority_level = priority_order.get(task['priority'], 0)

        if task_time >= cutoff_time and task_priority_level >= min_priority_level:
            filtered.append(task)

    print(f'✓ 筛选出 {len(filtered)} 个任务（原始: {len(tasks)}）')

    # 按项目统计
    by_project = {}
    for task in filtered:
        proj = task['project']
        by_project[proj] = by_project.get(proj, 0) + 1

    for proj, count in by_project.items():
        print(f'  {proj}: {count} 个')

    return filtered


def step4_create_kanban_tasks_summary(tasks):
    """步骤4: 生成待创建任务摘要（供Claude批量创建）"""
    print(f'\n[步骤4] 生成任务摘要')
    print('-' * 60)

    summary_file = PROJECT_DIR / 'output' / 'tasks_to_create.json'

    # 按项目分组
    by_project = {}
    for task in tasks:
        proj = task['project']
        if proj == 'general':
            proj = 'syc-player'

        if proj not in by_project:
            by_project[proj] = []
        by_project[proj].append(task)

    summary = {
        'total': len(tasks),
        'by_project': {p: len(t) for p, t in by_project.items()},
        'tasks': by_project,
        'generated_at': datetime.now().isoformat()
    }

    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f'✓ 任务摘要已保存: {summary_file}')
    print(f'  总计: {len(tasks)} 个任务')

    return summary_file


def main():
    print('='*60)
    print('微信消息自动化需求收集系统')
    print('='*60)

    # 步骤1: 解密和同步
    new_msg_count = step1_decrypt_and_sync()

    # 步骤2: 收集需求（最近7天）
    tasks = step2_collect_requirements(hours=7*24)

    if not tasks:
        print('\n没有新的需求或反馈')
        return

    # 步骤3: 筛选任务（最近7天，medium及以上优先级）
    filtered_tasks = step3_filter_tasks(tasks, days=7, min_priority='medium')

    if not filtered_tasks:
        print('\n没有符合条件的任务')
        return

    # 步骤4: 生成摘要
    summary_file = step4_create_kanban_tasks_summary(filtered_tasks)

    print('\n' + '='*60)
    print('✓ 自动化流程完成！')
    print('='*60)
    print(f'\n下一步: 使用Claude读取 {summary_file}')
    print('并通过kanban-doc MCP批量创建任务')


if __name__ == '__main__':
    main()
