"""
微信用户反馈定时监控脚本
通过 Windows 任务计划程序每30分钟执行一次
功能：解密数据库 -> 追踪用户消息 -> 分析反馈 -> 创建kanban任务
"""
import sqlite3, json, os, sys, ctypes, hashlib, re, uuid
from datetime import datetime, timedelta
from collections import Counter
from multiprocessing import freeze_support
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
freeze_support()

# ============ 配置 ============
MONITOR_USERS = ['三叶草', '编程仝芷硕', 'Estelle', '烨林', '沐光', '密码机']
PROJECT_DIR = Path(r'D:\develoment_home\project_home\WeChatMsgArchive')
OUTPUT_DIR = PROJECT_DIR / 'output' / 'decrypted_db'
KANBAN_TASKS_DIR = Path(r'D:\develoment_home\project_home\money\syc\.kanban\projects\syc-player\tasks')
LOG_DIR = PROJECT_DIR / 'output' / 'cron_logs'
STATE_FILE = PROJECT_DIR / 'output' / 'cron_state.json'
INTERVAL_MINUTES = 30

os.chdir(PROJECT_DIR)
LOG_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] {msg}')


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'last_run': 0, 'known_msg_hashes': []}


def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ============ Step 1: 解密数据库 ============
def decrypt_db():
    log('开始解密数据库...')
    try:
        import psutil, pythoncom
        v3_running = any(p.name() == 'WeChat.exe' for p in psutil.process_iter(['name']))
        if not v3_running:
            log('微信未运行，跳过解密，使用现有数据库')
            return True

        from wxManager.decrypt.common import WeChatInfo, get_version
        from wxManager.decrypt.wx_info_v3 import get_info_wxid, get_wx_dir, get_key, get_exe_bit
        from wxManager.decrypt import decrypt_v3
        from wxManager import Me

        for process in psutil.process_iter(['name', 'exe', 'pid']):
            if process.name() != 'WeChat.exe':
                continue
            wechat_info = WeChatInfo()
            wechat_info.pid = process.pid
            try:
                pythoncom.CoInitialize()
                wechat_info.version = get_version(process.pid)
            except:
                wechat_info.version = '3.9.12.57'

            wechat_base_address = 0
            for module in process.memory_maps(grouped=False):
                if module.path and 'WeChatWin.dll' in module.path:
                    wechat_base_address = int(module.addr, 16)
                    break
            if wechat_base_address == 0:
                continue

            Handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, process.pid)
            wechat_info.wxid = get_info_wxid(Handle)
            wechat_info.wx_dir = get_wx_dir(wechat_info.wxid) if wechat_info.wxid != 'None' else ''
            if not wechat_info.wx_dir:
                continue

            addrLen = get_exe_bit(process.exe()) // 8
            wechat_info.key = get_key(wechat_info.wx_dir, addrLen)

            if wechat_info.key and wechat_info.key != 'None':
                src_dir = os.path.join(wechat_info.wx_dir, 'Msg')
                decrypt_v3.decrypt_db_files(wechat_info.key, src_dir=src_dir, dest_dir=str(OUTPUT_DIR))
                me = Me()
                me.wx_dir = wechat_info.wx_dir
                me.wxid = wechat_info.wxid
                me.name = wechat_info.wxid
                with open(OUTPUT_DIR / 'info.json', 'w', encoding='utf-8') as f:
                    json.dump(me.to_json(), f, ensure_ascii=False, indent=2)
                log('解密完成')
                return True

        log('密钥获取失败，使用现有数据库')
        return True
    except Exception as e:
        log(f'解密失败: {e}，使用现有数据库')
        return True


# ============ Step 2: 搜索用户和提取消息 ============
def parse_bytes_extra(data):
    if not data:
        return None
    try:
        i = 0
        while i < len(data):
            if data[i] == 0x1a:
                i += 1
                if i >= len(data):
                    break
                length = data[i]
                i += 1
                sub = data[i:i+length]
                j = 0
                while j < len(sub):
                    if (sub[j] == 0x08 and j+1 < len(sub) and sub[j+1] == 0x01
                            and j+2 < len(sub) and sub[j+2] == 0x12):
                        j += 3
                        wxid_len = sub[j]
                        j += 1
                        return sub[j:j+wxid_len].decode('utf-8', errors='ignore')
                    j += 1
                i += length
            else:
                i += 1
    except:
        pass
    return None


def search_and_extract(timestamp_since):
    micro_db = str(OUTPUT_DIR / 'MicroMsg.db')
    msg_db = str(OUTPUT_DIR / 'Multi' / 'MSG0.db')

    if not os.path.exists(micro_db) or not os.path.exists(msg_db):
        log('数据库文件不存在')
        return {}

    conn_micro = sqlite3.connect(micro_db)
    cur_micro = conn_micro.cursor()

    # 搜索用户
    all_wxid_to_user = {}
    all_groups = {}
    for keyword in MONITOR_USERS:
        cur_micro.execute(
            'SELECT UserName, NickName, Remark FROM Contact WHERE NickName LIKE ? OR Remark LIKE ?',
            (f'%{keyword}%', f'%{keyword}%')
        )
        targets = cur_micro.fetchall()
        if targets:
            for wxid, nick, remark in targets:
                all_wxid_to_user[wxid] = keyword
            log(f'✓ {keyword}: {len(targets)}个匹配')
        else:
            log(f'✗ {keyword}: 未找到')

    # 查找群聊
    for wxid in list(all_wxid_to_user.keys()):
        cur_micro.execute('SELECT ChatRoomName FROM ChatRoom WHERE UserNameList LIKE ?', (f'%{wxid}%',))
        for (room_id,) in cur_micro.fetchall():
            if room_id not in all_groups:
                cur_micro.execute('SELECT strNickName FROM Session WHERE strUsrName=?', (room_id,))
                row = cur_micro.fetchone()
                all_groups[room_id] = row[0] if row else room_id
    conn_micro.close()

    # 提取消息
    conn_msg = sqlite3.connect(msg_db)
    cur_msg = conn_msg.cursor()
    type_map = {1: '文本', 3: '图片', 34: '语音', 43: '视频', 47: '表情包', 10000: '系统消息', 49: '链接/文件'}
    recent_by_user = {}

    cur_msg.execute(
        'SELECT Type, IsSender, CreateTime, StrContent, BytesExtra, StrTalker FROM MSG WHERE CreateTime > ? ORDER BY CreateTime DESC',
        (timestamp_since,)
    )
    for msg_type, is_sender, ts, content, bytes_extra, talker in cur_msg.fetchall():
        sender_wxid = parse_bytes_extra(bytes_extra) if not is_sender else ''
        if sender_wxid not in all_wxid_to_user:
            continue
        user = all_wxid_to_user[sender_wxid]
        ts_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        type_name = type_map.get(msg_type, f'类型{msg_type}')
        text = content if msg_type == 1 else f'[{type_name}]'
        group_name = all_groups.get(talker, talker)

        if user not in recent_by_user:
            recent_by_user[user] = []
        recent_by_user[user].append({
            'time': ts_str, 'type': type_name, 'content': text,
            'group': group_name, 'timestamp': ts
        })
    conn_msg.close()
    return recent_by_user


# ============ Step 3: 分析反馈并创建任务 ============
BUG_KEYWORDS = [
    'bug', 'BUG', '问题', '报错', '失败', '崩溃', '闪退', '卡死',
    '没有用', '不行', '无效', '异常', '错误', '不对', '失效',
    '没有反应', '没反应', '对接不上', '没对接', '不能用', '用不了',
    '修复', '修改', '优化', '刷新问题', '逻辑错'
]


def analyze_messages(recent_by_user):
    """分析消息，识别bug反馈"""
    bugs_found = []
    for user, msgs in recent_by_user.items():
        text_msgs = [m for m in msgs if m['type'] == '文本' and m['content']]
        if not text_msgs:
            continue

        bug_msgs = []
        for msg in text_msgs:
            content = msg['content']
            if any(kw in content for kw in BUG_KEYWORDS):
                bug_msgs.append(msg)

        if bug_msgs:
            summary = '\n'.join([f"[{m['time']}] {m['content'][:100]}" for m in bug_msgs])
            bugs_found.append({
                'user': user,
                'messages': bug_msgs,
                'summary': summary,
                'group': bug_msgs[0]['group'],
                'time_range': f"{bug_msgs[-1]['time']} ~ {bug_msgs[0]['time']}"
            })
    return bugs_found


def slugify(text):
    """中文转拼音简写用于文件名"""
    text = re.sub(r'[^\w\u4e00-\u9fff]', '-', text)
    text = re.sub(r'-+', '-', text).strip('-')
    return text[:50]


def create_kanban_task(bug_info):
    """创建 kanban 任务文件"""
    task_id = uuid.uuid4().hex[:4]
    title = f"[反馈] {bug_info['user']}: {bug_info['messages'][0]['content'][:30]}"
    slug = slugify(title)
    filename = f"{task_id}-{slug}.md"
    filepath = KANBAN_TASKS_DIR / filename

    now_iso = datetime.utcnow().isoformat() + '+00:00'
    content = f"""---
id: {task_id}
title: "{title}"
status: todo
priority: high
tags:
- bug
- 用户反馈
- 自动创建
created_at: {now_iso}
updated_at: {now_iso}
---

## 问题描述
{bug_info['summary']}

## 反馈人
{bug_info['user']}

## 反馈群聊
{bug_info['group']}

## 反馈时间
{bug_info['time_range']}

## 完整消息记录
"""
    for msg in bug_info['messages']:
        content += f"- [{msg['time']}] {msg['content'][:200]}\n"

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    log(f'已创建任务: {filename}')
    return filename


# ============ 主流程 ============
def main():
    log('='*50)
    log('微信用户反馈监控 - 开始执行')
    log('='*50)

    state = load_state()
    now = datetime.now()
    now_ts = int(now.timestamp())

    # 使用上次运行时间或30分钟前
    if state['last_run'] > 0:
        since_ts = state['last_run']
    else:
        since_ts = int((now - timedelta(minutes=INTERVAL_MINUTES)).timestamp())

    since_str = datetime.fromtimestamp(since_ts).strftime('%Y-%m-%d %H:%M:%S')
    log(f'分析时间范围: {since_str} ~ {now.strftime("%Y-%m-%d %H:%M:%S")}')

    # Step 1: 解密
    decrypt_db()

    # Step 2: 搜索和提取
    recent_by_user = search_and_extract(since_ts)

    total = sum(len(msgs) for msgs in recent_by_user.values())
    log(f'\n新增消息总计: {total} 条')
    for user in MONITOR_USERS:
        count = len(recent_by_user.get(user, []))
        if count > 0:
            log(f'  {user}: {count} 条')

    # Step 3: 分析反馈
    bugs_found = []
    if total > 0:
        bugs_found = analyze_messages(recent_by_user)
        if bugs_found:
            log(f'\n发现 {len(bugs_found)} 个bug反馈:')
            for bug in bugs_found:
                log(f'  - {bug["user"]}: {bug["messages"][0]["content"][:50]}')
                create_kanban_task(bug)
        else:
            log('无bug相关反馈')

    # 保存状态
    state['last_run'] = now_ts
    save_state(state)

    # 写入日志文件
    log_file = LOG_DIR / f'monitor_{now.strftime("%Y%m%d")}.log'
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f'\n[{now.strftime("%Y-%m-%d %H:%M:%S")}] 消息:{total} Bug:{len(bugs_found)}\n')
        for user in MONITOR_USERS:
            count = len(recent_by_user.get(user, []))
            if count > 0:
                f.write(f'  {user}: {count}条\n')
                for msg in recent_by_user[user]:
                    if msg['type'] == '文本':
                        f.write(f'    [{msg["time"]}] {msg["content"][:100]}\n')

    log(f'\n执行完成，日志: {log_file}')


if __name__ == '__main__':
    main()
