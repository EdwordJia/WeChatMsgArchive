# -*- coding: utf-8 -*-
"""Discover all distinct sender wxids in a chatroom by scanning BytesExtra."""

import re, sqlite3, sys
from collections import Counter
from pathlib import Path


def discover(chatroom_id, db_dir="output/decrypted_db", limit=2000):
    wxid_counter = Counter()
    micromsg = Path(db_dir) / "MicroMsg.db"
    multi = Path(db_dir) / "Multi"
    pat = re.compile(rb"[\w@\-\.]{6,40}")
    for db_name in ("MSG0.db", "MSG1.db"):
        p = multi / db_name
        if not p.exists():
            continue
        cur = sqlite3.connect(str(p)).cursor()
        try:
            cur.execute("SELECT BytesExtra FROM MSG WHERE StrTalker=? AND IsSender=0 LIMIT ?", (chatroom_id, limit))
        except Exception:
            continue
        for (bx,) in cur.fetchall():
            if not bx:
                continue
            for chunk in pat.findall(bx[:300]):
                s = chunk.decode("utf-8", errors="ignore")
                if s.startswith("wxid_") or s.endswith("@openim") or s.endswith("@chatroom"):
                    wxid_counter[s] += 1
                    break
    # resolve nick/remark via Contact
    resolved = []
    if micromsg.exists():
        mc = sqlite3.connect(str(micromsg)).cursor()
        for wxid, count in wxid_counter.most_common():
            mc.execute("SELECT NickName, Remark FROM Contact WHERE UserName=?", (wxid,))
            r = mc.fetchone()
            nick = r[0] if r and r[0] else ""
            remark = r[1] if r and r[1] else ""
            resolved.append({"wxid": wxid, "count": count, "nick": nick, "remark": remark})
    return resolved


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    target = sys.argv[1] if len(sys.argv) > 1 else "49734720477@chatroom"
    rows = discover(target)
    print("Discovered " + str(len(rows)) + " distinct senders in " + target + ":")
    for r in rows:
        print("  " + str(r["count"]).rjust(4) + " | " + r["wxid"][:38].ljust(38) + " | nick=" + (r["nick"] or "?")[:18] + " | remark=" + (r["remark"] or "?"))
