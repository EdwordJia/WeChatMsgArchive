import sqlite3, sys
from pathlib import Path
from datetime import datetime
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

DB_DIR = Path('output/decrypted_db')
INDEX = Path('output/wechat_index.db')
KEYWORDS = ['知识付费', '知识', '付费']

def dt(ts):
    try:
        ts=int(ts)
        if ts>10_000_000_000: ts//=1000
        return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return str(ts)

def tables(conn):
    return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]

def cols(conn,t):
    return [r[1] for r in conn.execute(f'PRAGMA table_info({t})')]

def scan_index():
    print('== index db ==')
    if not INDEX.exists():
        print('missing', INDEX)
        return
    conn=sqlite3.connect(INDEX); conn.row_factory=sqlite3.Row
    try:
        for t in tables(conn):
            c=cols(conn,t)
            print('table',t,c[:20])
            text_cols=[x for x in c if any(k in x.lower() for k in ['name','talker','room','content','sender','remark'])]
            if not text_cols: continue
            where=' OR '.join([f"{x} LIKE ?" for x in text_cols])
            params=[]
            for _ in text_cols: params.append('%知识%')
            try:
                rows=conn.execute(f"SELECT * FROM {t} WHERE {where} LIMIT 20", params).fetchall()
            except Exception as e:
                continue
            for r in rows:
                print(dict(r))
    finally:
        conn.close()

def scan_contact_all():
    print('\n== contacts/chatrooms keyword ==')
    micro=DB_DIR/'MicroMsg.db'
    conn=sqlite3.connect(micro); conn.row_factory=sqlite3.Row
    try:
        for t in tables(conn):
            c=cols(conn,t)
            text_cols=[x for x in c if x.lower() in ['username','nickname','remark','alias','chatroomname','usernamelist']]
            if not text_cols: continue
            where=' OR '.join([f"{x} LIKE ?" for x in text_cols])
            params=['%知识%' for _ in text_cols]
            try:
                rows=conn.execute(f"SELECT * FROM {t} WHERE {where} LIMIT 30", params).fetchall()
            except Exception:
                continue
            for r in rows:
                d=dict(r)
                print('table',t,{k:d.get(k) for k in text_cols if k in d})
    finally:
        conn.close()

def active_chatrooms():
    print('\n== active chatrooms latest ==')
    latest={}
    for db in sorted(DB_DIR.glob('MSG*.db')):
        conn=sqlite3.connect(db); conn.row_factory=sqlite3.Row
        try:
            for t in tables(conn):
                c=cols(conn,t)
                if not {'StrTalker','CreateTime'} <= set(c): continue
                content='StrContent' if 'StrContent' in c else ('Content' if 'Content' in c else None)
                if not content: continue
                try:
                    rows=conn.execute(f"SELECT StrTalker, MAX(CreateTime) mt, COUNT(*) cnt FROM {t} WHERE StrTalker LIKE '%@chatroom' GROUP BY StrTalker ORDER BY mt DESC LIMIT 80").fetchall()
                except Exception:
                    continue
                for r in rows:
                    rid=r['StrTalker']; mt=r['mt']; cnt=r['cnt']
                    if rid not in latest or mt>latest[rid][0]: latest[rid]=(mt,cnt,db.name,t)
        finally:
            conn.close()
    for rid,(mt,cnt,db,t) in sorted(latest.items(), key=lambda kv:kv[1][0], reverse=True)[:80]:
        print(dt(mt), rid, cnt, db, t)

scan_index()
scan_contact_all()
active_chatrooms()
