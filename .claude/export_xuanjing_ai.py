import html
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOM = '48113421788@chatroom'
BASE = Path('output/decrypted_db')
OUT = Path('output/xuanjing_ai_messages.md')


def decode_compress(blob):
    if not blob:
        return ''
    data = blob[2:] if len(blob) > 2 else blob
    result = []
    i = 0
    while i < len(data):
        b = data[i]
        if b == 0:
            i += 1
            continue
        if b < 0x80:
            n = 1
        elif b < 0xC0:
            i += 1
            continue
        elif b < 0xE0:
            n = 2
        elif b < 0xF0:
            n = 3
        else:
            n = 4
        chunk = data[i:i+n]
        if len(chunk) == n and 0 not in chunk[1:]:
            try:
                result.append(chunk.decode('utf-8'))
            except UnicodeDecodeError:
                pass
        i += n
    return ''.join(result)


def clean(s):
    if not s:
        return ''
    s = html.unescape(s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def extract_sender(content, is_sender):
    if is_sender:
        return 'ME', content or ''
    if content and ':\n' in content[:120]:
        sender, _, body = content.partition(':\n')
        return sender, body
    return 'GROUP', content or ''


def title_from_xml(text):
    if not text:
        return ''
    for tag in ['title', 'des', 'url', 'appname']:
        m = re.search(fr'<{tag}>(.*?)</{tag}>', text, re.S)
        if m:
            val = clean(re.sub(r'<.*?>', '', m.group(1)))
            if val:
                return f'{tag}: {val}'
    urls = re.findall(r'https?://[^\s<>"\']+', text)
    return ' | '.join(urls[:3])

rows = []
for db in sorted((BASE / 'Multi').glob('MSG*.db')):
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute('''
        SELECT localId, MsgSvrID, Type, SubType, IsSender, CreateTime,
               StrContent, DisplayContent, CompressContent, BytesExtra
        FROM MSG
        WHERE StrTalker=?
        ORDER BY CreateTime ASC
    ''', (ROOM,))
    for row in cur.fetchall():
        local_id, msg_id, typ, sub, is_sender, ts, content, display, comp, bx = row
        sender, body = extract_sender(content or '', is_sender)
        comp_text = decode_compress(comp)
        summary = clean(body) or clean(display) or title_from_xml(comp_text) or title_from_xml(content or '')
        urls = []
        for source in [body or '', display or '', comp_text, content or '']:
            urls.extend(re.findall(r'https?://[^\s<>"\']+', source))
        rows.append({
            'db': db.name,
            'local_id': local_id,
            'msg_id': msg_id,
            'time': datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S'),
            'type': typ,
            'subtype': sub,
            'sender': sender,
            'summary': summary,
            'compress': clean(comp_text),
            'urls': list(dict.fromkeys(urls))[:5],
            'bytes_extra_len': len(bx) if bx else 0,
        })
    conn.close()

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open('w', encoding='utf-8') as f:
    f.write(f'# 炫镜Ai群聊导出\n\n群ID：{ROOM}\n\n消息数：{len(rows)}\n\n')
    for r in rows:
        f.write(f"## {r['time']} | {r['sender']} | Type={r['type']}/{r['subtype']} | {r['db']}#{r['local_id']}\n\n")
        if r['summary']:
            f.write(r['summary'][:3000] + '\n\n')
        if r['urls']:
            f.write('URLs:\n')
            for u in r['urls']:
                f.write(f'- {u}\n')
            f.write('\n')
        if r['compress'] and r['compress'] != r['summary']:
            f.write('<details><summary>CompressContent</summary>\n\n')
            f.write(r['compress'][:5000] + '\n\n</details>\n\n')

print(OUT)
print('messages', len(rows))
for r in rows[-15:]:
    print(r['time'], r['sender'], f"{r['type']}/{r['subtype']}", r['summary'][:120])
