import csv
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

GROUP_ID = '49584724187@chatroom'
GROUP_NAME = '知识付费应用'
BASE = Path('output/decrypted_db')
OUT = Path('output')
OUT.mkdir(exist_ok=True)


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
                sub = data[i:i + length]
                j = 0
                while j < len(sub):
                    if sub[j] == 0x08 and j + 1 < len(sub) and sub[j + 1] == 0x01 and j + 2 < len(sub) and sub[j + 2] == 0x12:
                        j += 3
                        wxid_len = sub[j]
                        j += 1
                        return sub[j:j + wxid_len].decode('utf-8', errors='ignore')
                    j += 1
                i += length
            else:
                i += 1
    except Exception:
        pass
    return None


def fmt_ts(ts):
    try:
        ts = int(ts)
        if ts > 10_000_000_000:
            ts //= 1000
        return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return '未知'


def clean_text(msg_type, content):
    content = content or ''
    if msg_type == 3:
        m = re.search(r'md5="([0-9a-fA-F]{32})"', content)
        return f'[图片{": " + m.group(1) if m else ""}]'
    if msg_type == 34:
        if '<voicetrans' in content:
            m = re.search(r'transtext="([^"]*)"', content)
            if m:
                return '[语音转文字] ' + m.group(1)
        return '[语音]'
    if msg_type == 43:
        return '[视频]'
    if msg_type == 47:
        return '[表情包]'
    if msg_type == 49:
        title = re.search(r'<title>(.*?)</title>', content, re.S)
        des = re.search(r'<des>(.*?)</des>', content, re.S)
        pieces = []
        if title:
            pieces.append(title.group(1).strip())
        if des:
            pieces.append(des.group(1).strip())
        return '[链接/文件] ' + ' | '.join(pieces) if pieces else '[链接/文件]'
    if msg_type == 10000:
        return content.strip() or '[系统消息]'
    text = re.sub(r'<[^>]+>', '', str(content))
    return text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').strip()


def load_member_map():
    member_map = {}
    info = BASE / 'info.json'
    if info.exists():
        try:
            my_wxid = json.loads(info.read_text(encoding='utf-8')).get('wxid', '')
            if my_wxid:
                member_map[my_wxid] = '我'
        except Exception:
            pass
    micro = sqlite3.connect(BASE / 'MicroMsg.db')
    cur = micro.cursor()
    row = cur.execute('SELECT UserNameList FROM ChatRoom WHERE ChatRoomName=?', (GROUP_ID,)).fetchone()
    if row and row[0]:
        for wxid in row[0].split('^G'):
            if not wxid:
                continue
            c = cur.execute('SELECT NickName, Remark FROM Contact WHERE UserName=?', (wxid,)).fetchone()
            member_map[wxid] = (c[1] or c[0]) if c and (c[1] or c[0]) else wxid
    micro.close()
    return member_map


def msg_type_name(t):
    return {1: '文本', 3: '图片', 34: '语音', 43: '视频', 47: '表情包', 49: '链接/文件', 10000: '系统消息'}.get(t, f'类型{t}')


def collect_messages():
    member_map = load_member_map()
    messages = []
    for db in sorted((BASE / 'Multi').glob('MSG*.db')):
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            '''SELECT Type, IsSender, CreateTime, StrContent, BytesExtra, MsgSvrID, localId
               FROM MSG WHERE StrTalker=? ORDER BY CreateTime''',
            (GROUP_ID,),
        ).fetchall()
        for r in rows:
            sender_wxid = next((k for k, v in member_map.items() if v == '我'), '') if r['IsSender'] else (parse_bytes_extra(r['BytesExtra']) or '')
            sender_name = '我' if r['IsSender'] else member_map.get(sender_wxid, sender_wxid or '未知')
            messages.append({
                'time': fmt_ts(r['CreateTime']),
                'timestamp': r['CreateTime'],
                'sender': sender_name,
                'sender_wxid': sender_wxid,
                'type': msg_type_name(r['Type']),
                'type_code': r['Type'],
                'content': clean_text(r['Type'], r['StrContent']),
                'db': db.name,
                'localId': r['localId'],
                'MsgSvrID': r['MsgSvrID'],
            })
        conn.close()
    messages.sort(key=lambda x: x['timestamp'] or 0)
    return messages, member_map


def export(messages, member_map):
    safe = GROUP_ID.replace('@chatroom', '')
    txt = OUT / f'group_{safe}_full.txt'
    csv_path = OUT / f'group_{safe}_full.csv'
    stats = OUT / f'group_{safe}_stats.txt'

    with txt.open('w', encoding='utf-8') as f:
        f.write(f'群名: {GROUP_NAME}\n群ID: {GROUP_ID}\n成员数: {len(member_map)}\n总消息数: {len(messages)}\n')
        if messages:
            f.write(f'时间跨度: {messages[0]["time"]} ~ {messages[-1]["time"]}\n')
        f.write('\n')
        for m in messages:
            f.write(f'[{m["time"]}] {m["sender"]} ({m["type"]})\n{m["content"]}\n\n')

    with csv_path.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['时间', '发送者', '发送者wxid', '消息类型', '内容', '数据库', 'localId', 'MsgSvrID'])
        for m in messages:
            w.writerow([m['time'], m['sender'], m['sender_wxid'], m['type'], m['content'], m['db'], m['localId'], m['MsgSvrID']])

    real = [m for m in messages if m['type_code'] != 10000]
    sender_cnt = Counter(m['sender'] for m in real)
    date_cnt = Counter(m['time'][:10] for m in real)
    type_cnt = Counter(m['type'] for m in messages)

    with stats.open('w', encoding='utf-8') as f:
        f.write(f'=== 群聊分析：{GROUP_NAME} ===\n')
        f.write(f'群ID: {GROUP_ID}\n成员数: {len(member_map)}\n总消息数: {len(messages)}\n')
        if messages:
            f.write(f'时间跨度: {messages[0]["time"]} ~ {messages[-1]["time"]}\n')
        f.write('\n【发言排行】\n')
        for name, cnt in sender_cnt.most_common():
            pct = cnt / max(len(real), 1) * 100
            f.write(f'  {name}: {cnt}条 ({pct:.1f}%)\n')
        f.write('\n【按日期】\n')
        for d in sorted(date_cnt):
            f.write(f'  {d}: {date_cnt[d]}条\n')
        f.write('\n【消息类型】\n')
        for t, c in type_cnt.most_common():
            f.write(f'  {t}: {c}条\n')

    return txt, csv_path, stats


def main():
    messages, member_map = collect_messages()
    txt, csv_path, stats = export(messages, member_map)
    real = [m for m in messages if m['type_code'] != 10000]
    sender_cnt = Counter(m['sender'] for m in real)
    type_cnt = Counter(m['type'] for m in messages)
    print(f'=== 群聊分析：{GROUP_NAME} ===')
    print(f'群ID: {GROUP_ID}')
    print(f'成员数: {len(member_map)}')
    print(f'总消息数: {len(messages)}')
    if messages:
        print(f'时间跨度: {messages[0]["time"]} ~ {messages[-1]["time"]}')
    print('\n【发言排行 Top5】')
    for name, cnt in sender_cnt.most_common(5):
        print(f'  {name}: {cnt}条')
    print('\n【消息类型】')
    print('  ' + ' | '.join(f'{t}: {c}' for t, c in type_cnt.most_common()))
    print('\n【最新20条】')
    for m in messages[-20:]:
        print(f'[{m["time"]}] {m["sender"]} ({m["type"]})')
        text = m['content'] or '[无内容]'
        print('  ' + (text[:240] + '...' if len(text) > 240 else text))
    print('\n已导出:')
    print(f'  {txt}')
    print(f'  {csv_path}')
    print(f'  {stats}')

if __name__ == '__main__':
    main()
