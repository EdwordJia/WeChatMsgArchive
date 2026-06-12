"""
微信用户反馈监控系统 V2
优化版：使用索引数据库，支持全量搜索，集成kanban-doc MCP
"""
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
from wechat_index_db import WeChatIndexDB, incremental_sync
from wechat_monitor import decrypt_db, BUG_KEYWORDS

sys.stdout.reconfigure(encoding='utf-8')

# 配置
MONITOR_USERS = ['三叶草', '编程仝芷硕', 'Estelle', '烨林', '沐光', '密码机']
PROJECT_DIR = Path(__file__).parent
STATE_FILE = PROJECT_DIR / 'output' / 'monitor_state_v2.json'
LOG_DIR = PROJECT_DIR / 'output' / 'cron_logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)


def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] {msg}')


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'last_check_time': 0, 'processed_msg_ids': []}


def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def analyze_feedback(messages: list) -> list:
    """分析消息，识别需求和反馈"""
    feedbacks = []

    for msg in messages:
        if msg['type'] != 1:  # 只分析文本消息
            continue

        content = msg.get('content', '')
        if not content:
            continue

        # 检测bug关键词
        is_bug = any(kw in content for kw in BUG_KEYWORDS)

        # 检测需求关键词
        requirement_keywords = [
            '需要', '希望', '能不能', '可以', '建议', '增加', '添加',
            '改成', '改为', '调整', '优化', '支持', '实现', '功能'
        ]
        is_requirement = any(kw in content for kw in requirement_keywords)

        if is_bug or is_requirement:
            feedbacks.append({
                'type': 'bug' if is_bug else 'requirement',
                'content': content,
                'time': msg['time'],
                'timestamp': msg['timestamp'],
                'sender': msg.get('sender', ''),
                'group': msg.get('group', '')
            })

    return feedbacks


def create_kanban_task_via_mcp(feedback: dict, user: str, project: str = 'syc-player'):
    """通过kanban-doc MCP创建任务"""
    try:
        # 这里需要调用MCP工具
        # 由于在Python中无法直接调用MCP，这个函数应该由Claude调用
        # 返回任务信息供Claude处理
        return {
            'project': project,
            'title': f"[{user}反馈] {feedback['content'][:30]}",
            'body': f"""## 反馈内容
{feedback['content']}

## 反馈人
{user} ({feedback['sender']})

## 反馈时间
{feedback['time']}

## 反馈群聊
{feedback['group']}

## 类型
{'Bug修复' if feedback['type'] == 'bug' else '需求优化'}
""",
            'priority': 'high' if feedback['type'] == 'bug' else 'medium',
            'tags': ['用户反馈', '自动创建', feedback['type']]
        }
    except Exception as e:
        log(f'创建任务失败: {e}')
        return None


def main():
    log('='*60)
    log('微信用户反馈监控 V2 - 开始执行')
    log('='*60)

    state = load_state()
    now = datetime.now()
    now_ts = int(now.timestamp())

    # 计算检查时间范围
    if state['last_check_time'] > 0:
        since_ts = state['last_check_time']
    else:
        since_ts = int((now - timedelta(minutes=30)).timestamp())

    since_str = datetime.fromtimestamp(since_ts).strftime('%Y-%m-%d %H:%M:%S')
    log(f'检查时间范围: {since_str} ~ {now.strftime("%Y-%m-%d %H:%M:%S")}')

    # Step 1: 解密数据库
    log('\n[1/4] 解密微信数据库...')
    decrypt_db()

    # Step 2: 增量同步到索引数据库
    log('\n[2/4] 同步消息到索引数据库...')
    new_msg_count = incremental_sync()
    log(f'      新增 {new_msg_count} 条消息')

    # Step 3: 搜索监控用户的消息
    log('\n[3/4] 搜索监控用户消息...')
    db = WeChatIndexDB()

    # 获取监控用户的wxid
    user_wxids = db.get_monitored_users_wxids(MONITOR_USERS)
    log(f'      找到 {len(user_wxids)} 个监控用户')

    all_feedbacks = {}
    for user, wxids in user_wxids.items():
        user_messages = []
        for wxid in wxids:
            msgs = db.search_user_messages(wxid, since_time=since_ts, limit=200)
            user_messages.extend(msgs)

        if user_messages:
            log(f'      {user}: {len(user_messages)} 条消息')
            feedbacks = analyze_feedback(user_messages)
            if feedbacks:
                all_feedbacks[user] = feedbacks

    db.close()

    # Step 4: 创建kanban任务
    log('\n[4/4] 处理反馈并创建任务...')
    tasks_to_create = []

    for user, feedbacks in all_feedbacks.items():
        log(f'      {user}: {len(feedbacks)} 条反馈')
        for feedback in feedbacks:
            task_info = create_kanban_task_via_mcp(feedback, user)
            if task_info:
                tasks_to_create.append(task_info)

    # 保存待创建任务列表（供Claude读取）
    if tasks_to_create:
        tasks_file = PROJECT_DIR / 'output' / 'pending_kanban_tasks.json'
        with open(tasks_file, 'w', encoding='utf-8') as f:
            json.dump(tasks_to_create, f, ensure_ascii=False, indent=2)
        log(f'      生成 {len(tasks_to_create)} 个待创建任务')
        log(f'      任务列表: {tasks_file}')

    # 更新状态
    state['last_check_time'] = now_ts
    save_state(state)

    # 写入日志
    log_file = LOG_DIR / f'monitor_v2_{now.strftime("%Y%m%d")}.log'
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f'\n[{now.strftime("%Y-%m-%d %H:%M:%S")}]\n')
        f.write(f'  新增消息: {new_msg_count}\n')
        f.write(f'  发现反馈: {sum(len(fb) for fb in all_feedbacks.values())}\n')
        f.write(f'  待创建任务: {len(tasks_to_create)}\n')

    log(f'\n执行完成！日志: {log_file}')
    log('='*60)


if __name__ == '__main__':
    main()
