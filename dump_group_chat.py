import sqlite3
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

CHATROOM = '54026338684@chatroom'

mm = sqlite3.connect('output/decrypted_db/MicroMsg.db')
mc = mm.cursor()
mc.execute('SELECT UserNameList FROM ChatRoom WHERE ChatRoomName = ?', (CHATROOM,))
row = mc.fetchone()
members = row[0].split('^G') if row else []
nicknames = {}
for m in members:
    mc.execute('SELECT NickName, Remark FROM Contact WHERE UserName = ?', (m,))
    r = mc.fetchone()
    if r:
        nicknames[m] = r[1] if r[1] else r[0]
mm.close()

print('=== Group Members ===')
for k, v in nicknames.items():
    print('  ' + k + ' = ' + (v or ''))
print()

import re
def parse_sender(be):
    if not be:
        return None
    try:
      s = bytes(be).decode('utf-8', errors='ignore')
      m = re.search(r'wxid_[a-zA-Z0-9_]+', s)
        return m.group(0) if m else None
    except:
        return None

c = sqlite3.connect('output/decrypted_db/Multi/MSG1.db')
cur = c.cursor()
cur.execute('SELECT CreateTime, StrContent, Type, IsSender, BytesExtra FROM MSG WHERE StrTalker = ? ORDER BY CreateTime DESC LIMIT 200', (CHATROOM,))
rows = cur.fetchall()
c.close()

print('=== Latest %d messages (chronological) ===' % len(rows))
print()

for ct, content, mtype, is_sender, be in reversed(rows):
    ts = datetime.fromtimestamp(ct).strftime('%Y-%m-%d %H:%M:%S')
    if is_sender == 1:
        sender = nicknames.get('wxid_ucag2pjrmhm822', '我')
    else:
        wxid = parse_sender(be)
        sender = nicknames.get(wxid, wxid or '?')
    if mtype == 1:
        print('[' + ts + '] ' + sender + ': ' + (content or ''))
    elif mtype == 10000:
        print('[' + ts + '] [系统] ' + (content or ''))
    elif mtype == 3:
        print('[' + ts + '] ' + sender + ': [图片]')
    elif mtype == 49:
        print('[' + ts + '] ' + sender + ': [链接/文件]')
    elif mtype == 47:
        print('[' + ts + '] ' + sender + ': [表情]')
    elif mtype == 43:
        print('[' + ts + '] ' + sender + ': [视频]')
    elif mtype == 34:
        print('[' + ts + '] ' + sender + ': [语音]')
    else:
        print('[' + ts + '] ' + sender + ': [类型' + str(mtype) + ']')
