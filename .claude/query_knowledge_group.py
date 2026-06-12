import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

DB_DIR = Path('output/decrypted_db')
KEYWORD = '知识付费'


def ts_to_dt(ts):
    if not ts:
        return ''
    try:
        ts = int(ts)
        if ts > 10_000_000_000:
            ts //= 1000
        return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return str(ts)


def clean_text(text):
    if text is None:
        return ''
    text = str(text)
    if '<voicetrans' in text:
        m = re.search(r'transtext="([^"]*)"', text)
        if m:
            return '[语音转文字] ' + m.group(1)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('\r', '\n')
    return text.strip()


def tables(conn):
    return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]


def cols(conn, table):
    return [r[1] for r in conn.execute(f'PRAGMA table_info({table})')]


def find_rooms():
    micro = DB_DIR / 'MicroMsg.db'
    found = {}
    conn = sqlite3.connect(micro)
    conn.row_factory = sqlite3.Row
    try:
        for table in tables(conn):
            c = set(cols(conn, table))
            if 'UserName' in c and ('NickName' in c or 'Remark' in c):
                nick = 'NickName' if 'NickName' in c else "''"
                remark = 'Remark' if 'Remark' in c else "''"
                sql = f"SELECT UserName, {nick} AS NickName, {remark} AS Remark FROM {table} WHERE NickName LIKE ? OR Remark LIKE ? OR UserName LIKE ?"
                try:
                    for row in conn.execute(sql, (f'%{KEYWORD}%', f'%{KEYWORD}%', f'%{KEYWORD}%')):
                        rid = row['UserName']
                        name = row['NickName'] or row['Remark'] or ''
                        if rid and '@chatroom' in rid:
                            found[rid] = (name, table)
                except sqlite3.DatabaseError:
                    continue
    finally:
        conn.close()
    return [(rid, name, source) for rid, (name, source) in found.items()]


def candidate_msg_tables(conn):
    result = []
    for table in tables(conn):
        c = set(cols(conn, table))
        talker = next((x for x in ['StrTalker', 'Talker', 'Username'] if x in c), None)
        time_col = next((x for x in ['CreateTime', 'createTime', 'Timestamp', 'Time'] if x in c), None)
        content = next((x for x in ['StrContent', 'Content', 'content'] if x in c), None)
        if talker and time_col and content:
            is_sender = 'IsSender' if 'IsSender' in c else None
            result.append((table, talker, time_col, content, is_sender))
    return result


def query_by_room(room_id, limit_per_table=200):
    rows = []
    for db in sorted(DB_DIR.glob('MSG*.db')):
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        try:
            for table, talker_col, time_col, content_col, is_sender_col in candidate_msg_tables(conn):
                select_sender = f', {is_sender_col} AS IsSender' if is_sender_col else ', 0 AS IsSender'
                sql = f"SELECT {time_col} AS CreateTime, {content_col} AS Content {select_sender} FROM {table} WHERE {talker_col}=? ORDER BY {time_col} DESC LIMIT ?"
                try:
                    for r in conn.execute(sql, (room_id, limit_per_table)):
                        rows.append((r['CreateTime'], db.name, table, r['IsSender'], r['Content']))
                except sqlite3.DatabaseError:
                    continue
        finally:
            conn.close()
    rows.sort(key=lambda x: x[0] or 0, reverse=True)
    return rows


def search_keyword_in_messages(limit=80):
    rows = []
    for db in sorted(DB_DIR.glob('MSG*.db')):
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        try:
            for table, talker_col, time_col, content_col, is_sender_col in candidate_msg_tables(conn):
                select_sender = f', {is_sender_col} AS IsSender' if is_sender_col else ', 0 AS IsSender'
                sql = f"SELECT {time_col} AS CreateTime, {talker_col} AS Talker, {content_col} AS Content {select_sender} FROM {table} WHERE {content_col} LIKE ? ORDER BY {time_col} DESC LIMIT ?"
                try:
                    for r in conn.execute(sql, (f'%{KEYWORD}%', limit)):
                        rows.append((r['CreateTime'], db.name, table, r['Talker'], r['IsSender'], r['Content']))
                except sqlite3.DatabaseError:
                    continue
        finally:
            conn.close()
    rows.sort(key=lambda x: x[0] or 0, reverse=True)
    return rows[:limit]


def print_msgs(msgs, limit=60):
    for ct, db, table, is_sender, content in msgs[:limit]:
        who = '我' if int(is_sender or 0) == 1 else '对方'
        text = clean_text(content) or '[无内容]'
        if len(text) > 500:
            text = text[:500] + '...'
        print(f'[{ts_to_dt(ct)}] {who} ({db}/{table})')
        print(f'  {text}')


def main():
    rooms = find_rooms()
    print(f'匹配群聊: {len(rooms)}')
    for i, (rid, name, source) in enumerate(rooms, 1):
        print(f'{i}. {name} | {rid} | source={source}')

    for rid, name, source in rooms:
        print('\n' + '=' * 90)
        print(f'群: {name} ({rid})')
        msgs = query_by_room(rid)
        print(f'消息数: {len(msgs)}')
        print_msgs(msgs, 80)

    print('\n' + '=' * 90)
    print('消息内容中包含关键词的记录:')
    kw = search_keyword_in_messages()
    for ct, db, table, talker, is_sender, content in kw:
        who = '我' if int(is_sender or 0) == 1 else '对方'
        print(f'[{ts_to_dt(ct)}] {who} talker={talker} ({db}/{table})')
        print(f'  {clean_text(content)[:500]}')

if __name__ == '__main__':
    main()
