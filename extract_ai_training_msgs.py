# -*- coding: utf-8 -*-
import os
import sys
import sqlite3
import re
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"D:\develoment_home\project_home\WeChatMsgArchive"
MULTI = os.path.join(ROOT, "output", "decrypted_db", "Multi")
MICROMSG = os.path.join(ROOT, "output", "decrypted_db", "MicroMsg.db")
OUT_TXT = os.path.join(ROOT, "output", "ai_training_messages.txt")

GROUP = "49734720477@chatroom"
START_TS = int(datetime(2026, 4, 20, 0, 0, 0).timestamp())
TZ = timezone(timedelta(hours=8))

contact_map = {}
display_map = {}

mm = sqlite3.connect(MICROMSG)
mm.row_factory = sqlite3.Row
for row in mm.execute("SELECT UserName, NickName, Remark FROM Contact"):
    contact_map[row["UserName"]] = {
        "nick": (row["NickName"] or "").strip(),
        "remark": (row["Remark"] or "").strip(),
    }

cr = mm.execute(
    "SELECT UserNameList, DisplayNameList FROM ChatRoom WHERE ChatRoomName=?",
    (GROUP,),
).fetchone()
if cr:
    users = (cr["UserNameList"] or "").split("\x07")
    disps = (cr["DisplayNameList"] or "").split("\x07")
    for u, d in zip(users, disps):
        if u and d:
            display_map[u] = d
mm.close()


def resolve_name(wxid):
    parts = []
    d = display_map.get(wxid)
    if d:
        parts.append(d)
    c = contact_map.get(wxid)
    if c:
        primary = c["remark"] or c["nick"]
        if primary and primary not in parts:
            parts.append(primary)
    if not parts:
        return wxid
    return "/".join(parts) + " (" + wxid + ")"


def parse_sender(strcontent, is_sender):
    if is_sender == 1:
        return "ME", strcontent
    if not strcontent:
        return "?", ""
    m = re.match(r"^([^\s:][^\s:]{0,80}?):\n(.*)$", strcontent, re.DOTALL)
    if m:
        return m.group(1), m.group(2)
    if "\n" in strcontent:
        head, _, rest = strcontent.partition("\n")
        head = head.rstrip(":")
        return head, rest
    return "?", strcontent


TYPE_MAP = {
    1: "TEXT",
    3: "IMAGE",
    34: "VOICE",
    43: "VIDEO",
    47: "EMOJI",
    49: "APPMSG",
    10000: "SYSTEM",
}


def type_label(t):
    return TYPE_MAP.get(t, "TYPE" + str(t))


messages = []
for db_name in ("MSG0.db", "MSG1.db"):
    path = os.path.join(MULTI, db_name)
    if not os.path.exists(path):
        continue
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        sql = (
            "SELECT CreateTime, StrContent, Type, IsSender, MsgSvrID "
            "FROM MSG WHERE StrTalker=? AND CreateTime>=? "
            "ORDER BY CreateTime ASC"
        )
        rows = conn.execute(sql, (GROUP, START_TS)).fetchall()
        for r in rows:
            messages.append({
                "ts": r["CreateTime"],
                "type": r["Type"],
                "is_sender": r["IsSender"],
                "content": r["StrContent"] or "",
                "msgsvr": r["MsgSvrID"],
                "src": db_name,
            })
    except sqlite3.Error as e:
        print("[WARN] " + db_name + ": " + str(e))
    finally:
        conn.close()

seen = set()
uniq = []
for m in messages:
    key = m["msgsvr"]
    if key in seen:
        continue
    seen.add(key)
    uniq.append(m)
uniq.sort(key=lambda x: x["ts"])

print("Total raw: " + str(len(messages)) + ", unique: " + str(len(uniq)))

with open(OUT_TXT, "w", encoding="utf-8") as f:
    f.write("# 群消息: 4.21ai训练管理 (" + GROUP + ")\n")
    f.write("# 起始时间: 2026-04-20\n")
    f.write("# 总条数: " + str(len(uniq)) + "\n\n")
    for m in uniq:
        dt = datetime.fromtimestamp(m["ts"], TZ).strftime("%Y-%m-%d %H:%M:%S")
        sender_id, body = parse_sender(m["content"], m["is_sender"])
        if m["is_sender"] == 1:
            who = "我(本人)"
        else:
            who = resolve_name(sender_id)
        tlabel = type_label(m["type"])
        if m["type"] not in (1, 10000):
            body_excerpt = body.replace("\n", " ").strip()[:300]
            f.write("[" + dt + "] [" + tlabel + "] " + who + ": " + body_excerpt + "\n")
        else:
            f.write("[" + dt + "] " + who + ":\n" + body.strip() + "\n")
        f.write("-" * 80 + "\n")

size = os.path.getsize(OUT_TXT)
print("Output: " + OUT_TXT)
print("Size: " + str(size) + " bytes (" + str(round(size / 1024, 1)) + " KB)")
print("Lines saved: " + str(len(uniq)))
