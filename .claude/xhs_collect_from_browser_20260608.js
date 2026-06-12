async () => {
  const batchNo = Number(localStorage.getItem('xhs_auto_batch_no_20260608') || '51');
  const batchKey = `xhs_detail_batch_20260608_${batchNo}`;
  const doneKey = 'xhs_done_note_ids_20260608';
  const skippedKey = 'xhs_skipped_note_ids_20260608';
  const done = new Set(JSON.parse(localStorage.getItem(doneKey) || '[]'));
  const skipped = new Set(JSON.parse(localStorage.getItem(skippedKey) || '[]'));
  const current = JSON.parse(localStorage.getItem(batchKey) || '[]');
  for (const item of current) done.add(item.noteId);

  const collectLinks = () => {
    const out = [];
    const seen = new Set();
    for (const a of document.querySelectorAll('a[href*="/search_result/"]')) {
      const href = a.href;
      const m = href.match(/\/search_result\/([0-9a-f]{24})/);
      if (!m) continue;
      const noteId = m[1];
      if (seen.has(noteId) || done.has(noteId) || skipped.has(noteId)) continue;
      seen.add(noteId);
      out.push({noteId, href, text: (a.innerText || a.textContent || '').trim().slice(0, 120)});
    }
    return out;
  };

  const before = collectLinks();
  for (let i = 0; i < 6; i++) {
    window.scrollBy(0, 900 + Math.floor(Math.random() * 500));
    await new Promise(r => setTimeout(r, 1200 + Math.floor(Math.random() * 900)));
  }
  const links = collectLinks();
  return {batchNo, batchKey, before: before.length, after: links.length, links: links.slice(0, 30)};
}