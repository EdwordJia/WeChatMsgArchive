import json
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(r"D:/develoment_home/project_home/WeChatMsgArchive/.claude")
DATA_PATH = Path(r"D:/develoment_home/project_home/spider-sandbox/output/xhs_depression/notes_api_intercepted.json")
OCR_SCRIPT = Path(r"D:/develoment_home/project_home/spider-sandbox/output/xhs_depression/ocr_update_batch_aistudio_api.py")


def nonempty(v):
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip()) and v.strip().upper() not in {"NA", "N/A", "NONE", "NULL", "[]"}
    if isinstance(v, list):
        return bool(v) and any(nonempty(x) for x in v)
    return True


def real_ocr(v):
    return nonempty(v) and bool(str(v).replace("【图片文字】", "").strip())


def strict_count():
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    total = 0
    for v in raw.values():
        if not isinstance(v, dict):
            continue
        if str(v.get("type", "")).lower() != "video" and nonempty(v.get("imageLocalPaths")) and real_ocr(v.get("ocrText")):
            total += 1
    return total


def main():
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "XHS_IMAGE_ROOT": "H:/Temp/xhs_depression_images",
        "XHS_OCR_MAX_SIDE": "700",
    }
    print(json.dumps({"start_strict": strict_count(), "target": 300}, ensure_ascii=False), flush=True)
    for batch_no in range(72, 87):
        before = strict_count()
        if before >= 300:
            print(json.dumps({"done": True, "strict_complete": before, "remaining": 0}, ensure_ascii=False), flush=True)
            return
        path = BASE / f"xhs_detail_batch_20260608_{batch_no}_for_ocr.json"
        if not path.exists():
            print(json.dumps({"batch": batch_no, "status": "missing", "strict_complete": before}, ensure_ascii=False), flush=True)
            continue
        print(json.dumps({"batch": batch_no, "status": "start", "strict_before": before}, ensure_ascii=False), flush=True)
        try:
            result = subprocess.run(
                [sys.executable, str(OCR_SCRIPT), str(path)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                timeout=900,
            )
            after = strict_count()
            lines = (result.stdout or "").splitlines()
            print(json.dumps({
                "batch": batch_no,
                "status": "done",
                "returncode": result.returncode,
                "strict_complete": after,
                "remaining": max(0, 300 - after),
                "tail": "\n".join(lines[-20:])[-1200:],
            }, ensure_ascii=False), flush=True)
        except subprocess.TimeoutExpired:
            after = strict_count()
            print(json.dumps({"batch": batch_no, "status": "timeout", "strict_complete": after, "remaining": max(0, 300 - after)}, ensure_ascii=False), flush=True)
    final = strict_count()
    print(json.dumps({"final_strict": final, "remaining": max(0, 300 - final)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
