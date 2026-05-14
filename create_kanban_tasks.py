"""
自动创建kanban任务
读取pending_kanban_tasks.json，通过kanban-doc MCP创建任务
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_DIR = Path(__file__).parent
TASKS_FILE = PROJECT_DIR / 'output' / 'pending_kanban_tasks.json'

# 项目映射（将general映射到实际项目）
PROJECT_MAPPING = {
    'general': 'syc-player',  # 默认项目
    'syc-player': 'syc-player',
    'qt-lens': 'qt-lens',
    'wechat-archive': 'wechat-archive'
}


def load_pending_tasks():
    """加载待创建任务"""
    if not TASKS_FILE.exists():
        print(f'任务文件不存在: {TASKS_FILE}')
        return []

    with open(TASKS_FILE, 'r', encoding='utf-8') as f:
        tasks = json.load(f)

    print(f'加载了 {len(tasks)} 个待创建任务')
    return tasks


def group_tasks_by_project(tasks):
    """按项目分组任务"""
    grouped = {}
    for task in tasks:
        project = PROJECT_MAPPING.get(task['project'], 'syc-player')
        if project not in grouped:
            grouped[project] = []
        grouped[project].append(task)
    return grouped


def print_task_summary(grouped_tasks):
    """打印任务摘要"""
    print('\n任务摘要:')
    print('='*60)
    for project, tasks in grouped_tasks.items():
        print(f'\n项目: {project} ({len(tasks)} 个任务)')

        # 按优先级统计
        priority_count = {}
        for task in tasks:
            p = task['priority']
            priority_count[p] = priority_count.get(p, 0) + 1

        for priority, count in sorted(priority_count.items()):
            print(f'  {priority}: {count} 个')

        # 显示前3个任务
        print('\n  示例任务:')
        for i, task in enumerate(tasks[:3], 1):
            print(f'    {i}. [{task["priority"]}] {task["title"]}')


def main():
    print('='*60)
    print('自动创建Kanban任务')
    print('='*60)

    # 加载任务
    tasks = load_pending_tasks()
    if not tasks:
        print('没有待创建的任务')
        return

    # 按项目分组
    grouped_tasks = group_tasks_by_project(tasks)
    print_task_summary(grouped_tasks)

    # 导出供Claude使用
    output = {
        'total': len(tasks),
        'by_project': {
            project: len(tasks_list)
            for project, tasks_list in grouped_tasks.items()
        },
        'tasks': grouped_tasks
    }

    output_file = PROJECT_DIR / 'output' / 'tasks_for_claude.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'\n任务数据已导出: {output_file}')
    print('\n请Claude使用kanban-doc MCP工具创建这些任务')
    print('='*60)


if __name__ == '__main__':
    main()
