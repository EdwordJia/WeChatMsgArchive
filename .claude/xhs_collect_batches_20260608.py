import asyncio
import json
import random
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright

CDP_URL = "http://127.0.0.1:9222"
OUT_DIR = Path(r"D:/develoment_home/project_home/WeChatMsgArchive/.claude")
KEYWORDS = ["抑郁症表现", "抑郁症症状", "抑郁躯体化", "抑郁症科普", "抑郁的信号", "抑郁症自救"]
TARGET_ITEMS = int(sys.argv[1]) if len(sys.argv) > 1 else 60
START_BATCH = int(sys.argv[2]) if len(sys.argv) > 2 else 51


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def write_batch(batch_no, items):
    path = OUT_DIR / f"xhs_detail_batch_20260608_{batch_no}_for_ocr.json"
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


async def collect_links(page, seen):
    return await page.evaluate(
        """
        (seenList) => {
          const seen = new Set(seenList);
          const out = [];
          const localSeen = new Set();
          for (const a of document.querySelectorAll('a[href*="/search_result/"]')) {
            const href = a.href;
            const m = href.match(/\/search_result\/([0-9a-f]{24})/);
            if (!m) continue;
            const noteId = m[1];
            if (seen.has(noteId) || localSeen.has(noteId)) continue;
            localSeen.add(noteId);
            const rect = a.getBoundingClientRect();
            out.push({noteId, href, text: (a.innerText || a.textContent || '').trim().slice(0, 120), top: rect.top});
          }
          return out;
        }
        """,
        list(seen),
    )


async def extract_detail(page, expected):
    return await page.evaluate(
        """
        (expectedNoteId) => {
          const state = window.__INITIAL_STATE__;
          const map = state?.note?.noteDetailMap || state?.note?.noteDetailMapV2 || {};
          const entry = map[expectedNoteId] || Object.values(map).find(x => x?.note?.noteId === expectedNoteId || x?.noteId === expectedNoteId);
          const note = entry?.note || entry || {};
          const text = selector => document.querySelector(selector)?.textContent?.trim() || '';
          const title = note.title || text('#detail-title') || text('.title') || document.title.replace(/ - 小红书$/, '');
          const desc = note.desc || note.description || text('#detail-desc') || text('.desc') || text('.note-content') || '';
          const urls = [];
          const add = (u) => {
            if (typeof u === 'string' && /^https?:\/\//.test(u) && !u.includes('nd_prv') && !u.includes('_prv') && !u.includes('sns-avatar') && !urls.includes(u)) urls.push(u);
          };
          const walk = (v) => {
            if (!v) return;
            if (typeof v === 'string') { add(v); return; }
            if (Array.isArray(v)) { v.forEach(walk); return; }
            if (typeof v === 'object') Object.values(v).forEach(walk);
          };
          walk(note.imageList || note.imagesList || note.image_list || note.images);
          if (!urls.length) {
            const bad = /(avatar|icon|logo|emoji|sprite|favicon|comment|user|profile|nd_prv|_prv)/i;
            for (const img of document.querySelectorAll('img')) {
              const src = img.currentSrc || img.src || '';
              if (!src || !src.includes('xhscdn.com') || bad.test(src)) continue;
              const rect = img.getBoundingClientRect();
              const w = Math.max(img.naturalWidth || 0, rect.width || 0);
              const h = Math.max(img.naturalHeight || 0, rect.height || 0);
              if (w >= 220 && h >= 220) add(src);
            }
          }
          return {
            noteId: note.noteId || expectedNoteId,
            title,
            desc,
            type: note.type || '',
            imageUrls: urls,
            imageCount: urls.length,
            url: location.href,
            bodyText: document.body.innerText.slice(0, 500)
          };
        }
        """,
        expected,
    )


async def main():
    main_data = read_json(r"D:/develoment_home/project_home/spider-sandbox/output/xhs_depression/notes_api_intercepted.json", {})
    seen = set(main_data.keys()) if isinstance(main_data, dict) else set()
    done_path = OUT_DIR / "xhs_collected_noteids_20260608.json"
    seen.update(read_json(done_path, []))
    collected = []
    batch = []
    batch_no = START_BATCH

    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0]
    page = ctx.pages[-1] if ctx.pages else await ctx.new_page()
    keyword_idx = 0
    try:
        while len(collected) < TARGET_ITEMS:
            if "xiaohongshu.com/search_result" not in page.url:
                kw = KEYWORDS[keyword_idx % len(KEYWORDS)]
                await page.goto(f"https://www.xiaohongshu.com/search_result/?keyword={kw}&source=web_search_result_notes&type=1", wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(random.randint(3000, 5500))
            body = await page.evaluate("() => document.body.innerText.slice(0, 1000)")
            if "登录后查看搜索结果" in body or "验证码" in body or "安全验证" in body:
                print(json.dumps({"stop": "risk_or_login", "text": body[:120]}, ensure_ascii=False), flush=True)
                break
            links = await collect_links(page, seen)
            if not links:
                await page.evaluate("window.scrollBy(0, 1000 + Math.floor(Math.random()*500))")
                await page.wait_for_timeout(random.randint(2500, 4500))
                links = await collect_links(page, seen)
            if not links:
                keyword_idx += 1
                if keyword_idx % len(KEYWORDS) == 0:
                    await page.wait_for_timeout(random.randint(8000, 14000))
                kw = KEYWORDS[keyword_idx % len(KEYWORDS)]
                await page.goto(f"https://www.xiaohongshu.com/search_result/?keyword={kw}&source=web_search_result_notes&type=1", wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(random.randint(3500, 6500))
                continue
            take = links[: min(8, len(links))]
            for link in take:
                if len(collected) >= TARGET_ITEMS:
                    break
                nid = link["noteId"]
                if nid in seen:
                    continue
                seen.add(nid)
                try:
                    print(f"[OPEN] {nid} collected={len(collected)}/{TARGET_ITEMS} batch={batch_no}", flush=True)
                    await page.goto(link["href"], wait_until="domcontentloaded", timeout=60000)
                    await page.wait_for_timeout(random.randint(3500, 7000))
                    item = await extract_detail(page, nid)
                    body = item.get("bodyText") or ""
                    t = str(item.get("type") or "").lower()
                    if "验证码" in body or "安全验证" in body or "登录后" in body[:80]:
                        print(json.dumps({"stop": "detail_risk_or_login", "noteId": nid, "text": body[:120]}, ensure_ascii=False), flush=True)
                        write_batch(batch_no, batch) if batch else None
                        done_path.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8")
                        return
                    if t == "video" or not item.get("imageUrls"):
                        print(f"[SKIP] {nid} type={t} images={len(item.get('imageUrls') or [])}", flush=True)
                    else:
                        item.pop("bodyText", None)
                        batch.append(item)
                        collected.append(item)
                        print(f"[KEEP] {nid} images={item['imageCount']} collected={len(collected)}", flush=True)
                        if len(batch) >= 5:
                            path = write_batch(batch_no, batch)
                            print(f"[BATCH] {path} items={len(batch)}", flush=True)
                            batch_no += 1
                            batch = []
                    if random.random() < 0.35:
                        await page.wait_for_timeout(random.randint(3000, 7000))
                except Exception as exc:
                    print(f"[ERR] {nid} {str(exc)[:120]}", flush=True)
                await page.wait_for_timeout(random.randint(2500, 5500))
            kw = KEYWORDS[keyword_idx % len(KEYWORDS)]
            await page.goto(f"https://www.xiaohongshu.com/search_result/?keyword={kw}&source=web_search_result_notes&type=1", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(random.randint(3000, 5500))
            await page.evaluate("window.scrollBy(0, 1500 + Math.floor(Math.random()*1000))")
            await page.wait_for_timeout(random.randint(2500, 4500))
        if batch:
            path = write_batch(batch_no, batch)
            print(f"[BATCH] {path} items={len(batch)}", flush=True)
        done_path.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"collected": len(collected), "nextBatch": batch_no + (1 if batch else 0)}, ensure_ascii=False), flush=True)
    finally:
        await pw.stop()


asyncio.run(main())
