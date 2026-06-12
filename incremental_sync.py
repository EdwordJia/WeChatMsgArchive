#!/usr/bin/env python3
"""增量同步解密后的 MSG*.db 到索引数据库（不依赖 wxManager/yara）"""
import sqlite3
import re
import sys
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

INDEX_DB = 'output/wechat_index.db'
DECRYPT_DIR = Path('output/decrypted_db/Multi')

def get_max_create_time():
    """获取索引数据库最新消息时间"""
    try:
        db = sqlite3.connect(INDEX_DB)
        c = db.cursor()
        c.execute('SELECT MAX(create_time) FROM messages')
        result = c.fetchone()[0]
        db.close()
        return result or 0
    except Exception as e:
        print(f"读取索引数据库失败: {e}")
        return 0

def parse_sender_wxid(raw, is_sender, bx):
    """解析发送者 wxid（简化版）"""
    if is_sender == 1:
        return ""
    body = raw or ""
    sep = ":" + chr(10)
    wxid = ""
    if sep in body[:120]:
        head, _, rest = body.partition(sep)
        if head.startswith("wxid_") or len(head) <= 32:
            wxid = head
    if not wxid and bx:
        try:
            chunks = re.findall(rb"[\w@\-\.]{6,40}", bx[:300])
            for c in chunks:
                s = c.decode("utf-8", errors="ignore")
                if s.startswith("wxid_") or s.endswith("@openim") or s.endswith("@chatroom"):
                    wxid = s
                    break
        except Exception:
            pass
    return wxid

def sync_db(db_path, cutoff, total_inserted):
    """同步单个数据库"""
    inserted = 0
    try:
        db = sqlite3.connect(str(db_path))
        c = db.cursor()
        # 检查 MSG 表是否存在
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='MSG'")
        if not c.fetchone():
            db.close()
            return 0

        c.execute(
            "SELECT CreateTime, StrContent, StrTalker, Type, IsSender, BytesExtra FROM MSG WHERE CreateTime > ?",
            (cutoff,)
        )
        rows = c.fetchall()
        db.close()

        if not rows:
            return 0

        # 批量插入索引数据库
        index_db = sqlite3.connect(INDEX_DB)
        ic = index_db.cursor()

        now = int(datetime.now().timestamp())
        for ct, raw, talker, mt, snd, bx in rows:
            sender_wxid = parse_sender_wxid(raw, snd, bx)
            content = raw or ""
            # 去掉发送者前缀
            sep = ":" + chr(10)
            if snd == 0 and sep in content[:120]:
                head, _, rest = content.partition(sep)
                if head.startswith("wxid_") or len(head) <= 32:
                    content = rest

            ic.execute(
                """INSERT INTO messages (local_id, talker, sender_wxid, msg_type, content, create_time, is_sender, source_db, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (0, talker or "", sender_wxid, mt or 0, content, ct, snd or 0, db_path.name, now)
            )
            inserted += 1

        index_db.commit()
        index_db.close()
        return inserted

    except Exception as e:
        print(f"  同步失败 {db_path.name}: {e}")
        return 0

def main():
    cutoff = get_max_create_time()
    print(f"索引数据库最新时间: {datetime.fromtimestamp(cutoff).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"开始增量同步...\n")

    # 优先使用 _merged.db，避免重复同步原始DB
    all_files = {p.name: p for p in DECRYPT_DIR.glob("MSG*.db")}
    selected = {}
    for name, path in all_files.items():
        base = name.replace("_merged", "").replace("_all", "").replace("_final", "")
        if base not in selected or "_merged" in name:
            selected[base] = path

    db_files = sorted(selected.values(), key=lambda p: p.name)
    total = 0
    for db_path in db_files:
        count = sync_db(db_path, cutoff, total)
        if count > 0:
            print(f"  {db_path.name}: +{count} 条")
            total += count

    print(f"\n同步完成，共新增 {total} 条消息")

    # 更新统计
    try:
        db = sqlite3.connect(INDEX_DB)
        c = db.cursor()
        c.execute('SELECT COUNT(*) FROM messages')
        count = c.fetchone()[0]
        c.execute('SELECT MAX(create_time) FROM messages')
        max_time = c.fetchone()[0]
        db.close()
        print(f"索引总条数: {count}")
        print(f"最新消息时间: {datetime.fromtimestamp(max_time).strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"统计失败: {e}")

if __name__ == "__main__":
    main()
