import json
import subprocess
import sys
from pathlib import Path

BASE = Path(r"D:/develoment_home/project_home/WeChatMsgArchive/.claude")
OCR_SCRIPT = Path(r"D:/develoment_home/project_home/spider-sandbox/output/xhs_depression/ocr_update_batch_safe_resize.py")
IMAGE_ROOT = r"H:/Temp/xhs_depression_images"


DONE_LOG = BASE / "xhs_ocr_done_batches_20260608.txt"


def load_done():
    if DONE_LOG.exists():
        return set(DONE_LOG.read_text(encoding="utf-8").splitlines())
    return set()


def save_done(name):
    with DONE_LOG.open("a", encoding="utf-8") as f:
        f.write(name + "\n")


def run_ocr(batch_path: Path):
    cmd = [
        sys.executable,
        str(OCR_SCRIPT),
        str(batch_path),
    ]
    env = {
        "PYTHONIOENCODING": "utf-8",
        "XHS_IMAGE_ROOT": IMAGE_ROOT,
        "XHS_OCR_MAX_SIDE": "1000",
    }
    print(f"[OCR_START] {batch_path.name}", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True, env={**dict(subprocess.os.environ), **env}, encoding="utf-8", timeout=900)
    # 从stdout最后几行找JSON结果
    lines = [l for l in result.stdout.splitlines() if l.strip().startswith("{")]
    if lines:
        try:
            data = json.loads(lines[-1])
            total = data.get("complete_total", "?")
            remain = data.get("remaining_to_300", "?")
            print(f"[OCR_DONE] {batch_path.name} complete_total={total} remaining={remain}", flush=True)
            return data
        except Exception:
            pass
    print(f"[OCR_DONE] {batch_path.name} (parse fallback)", flush=True)
    return None


def main():
    done = load_done()
    # 收集所有待OCR批次文件，按批次号排序
    batches = []
    for p in BASE.glob("xhs_detail_batch_20260608_*_for_ocr.json"):
        name = p.name
        if name in done:
            continue
        # 提取批次号
        m = name.replace("xhs_detail_batch_20260608_", "").replace("_for_ocr.json", "")
        if m.isdigit():
            batches.append((int(m), p))
    batches.sort()

    print(f"[QUEUE] {len(batches)} batches to OCR", flush=True)
    for idx, (batch_no, path) in enumerate(batches, 1):
        try:
            run_ocr(path)
            save_done(path.name)
            path.unlink()
        except subprocess.TimeoutExpired:
            print(f"[OCR_TIMEOUT] {path.name} skipped", flush=True)
            save_done(path.name + "_timeout")
    print("[ALL_DONE]", flush=True)


if __name__ == "__main__":
    main()
