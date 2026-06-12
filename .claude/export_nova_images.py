import hashlib
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
chatroom = '49384016077@chatroom'
wx_dir = r'E:/腾讯电脑管家文件搬家/微信聊天文件搬家/Users/WeChat Files/wxid_ucag2pjrmhm822'
out = Path('output/nova_feedback_images')
out.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect('output/decrypted_db/Multi/MSG2.db')
conn.text_factory = lambda x: x.decode('utf-8', 'ignore') if isinstance(x, bytes) else x
rows = conn.execute('''
    SELECT localId, CreateTime, StrContent, BytesExtra
    FROM MSG
    WHERE StrTalker = ? AND Type = 3
    ORDER BY CreateTime ASC
''', (chatroom,)).fetchall()
conn.close()

print('image rows', len(rows))
attach_hash = hashlib.md5(chatroom.encode()).hexdigest()
print('attach_hash', attach_hash)

for localid, ts, content, bytesextra in rows:
    dt = datetime.fromtimestamp(ts).strftime('%Y%m%d_%H%M%S')
    md5_match = re.search(r'md5="([^"]+)"', content or '')
    md5 = md5_match.group(1) if md5_match else ''
    print('\n', localid, dt, md5)
    candidates = []

    if bytesextra:
        b = bytesextra if isinstance(bytesextra, bytes) else bytes(bytesextra)
        for m in re.finditer(rb'[A-Za-z0-9_\\/\.\-:]{8,}', b):
            s = m.group(0).decode('utf-8', 'ignore')
            if 'FileStorage' in s or 'MsgAttach' in s or 'Image' in s or 'Thumb' in s:
                print('  bytesExtra path?', s)

    base = Path(wx_dir) / 'FileStorage' / 'MsgAttach' / attach_hash
    if base.exists():
        for p in base.rglob('*'):
            if not p.is_file():
                continue
            name = p.name.lower()
            if md5 and (md5.lower() in name or name.startswith(md5[:8].lower())):
                candidates.append(p)
            elif p.stat().st_mtime >= datetime(2026, 6, 1, 0, 0).timestamp():
                candidates.append(p)
    print('  candidates', len(candidates))
    for i, p in enumerate(candidates[:20]):
        print('   ', p, p.stat().st_size)
        dst = out / f'{dt}_{localid}_{i}_{p.name}'
        try:
            shutil.copy2(p, dst)
        except Exception as e:
            print('copy err', e)
