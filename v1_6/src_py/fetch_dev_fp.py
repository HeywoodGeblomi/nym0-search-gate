#!/usr/bin/env python3
"""Dev-only clean text for the instruction check false-hold rate: random public Wikipedia / Simple Wikipedia summaries.
Deduplicated against the learning pool and the v1 and v1.2 sets. Never used as test data; test candidates that collide with it are dropped."""
import json, hashlib, time, urllib.request, re, unicodedata, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; DATA = ROOT/"data"
UA = "Nym0SearchGate/1.3 (research dev set; unauthenticated public wiki APIs; contact: none)"
def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def norm(t): return re.sub(r"\s+"," ",unicodedata.normalize("NFKC",t)).strip().lower()
def get(url):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"}),timeout=20) as r: return json.loads(r.read().decode())
        except Exception: time.sleep(1+k)
seen_u, seen_h = set(), set()
for p in ["/workspace/frontier_pivot/search_gate_v1_2/data/learning_pool.jsonl"]:
    for l in open(p): r=json.loads(l); seen_u.add(r["url"]); seen_h.add(r["text_sha256"])
for p in ["/workspace/frontier_pivot/search_gate_test_v1/data/official_clean.jsonl","/workspace/frontier_pivot/search_gate_v1_2/data/test_clean.jsonl"]:
    for l in open(p): r=json.loads(l); seen_u.add(r["source_url"]); seen_h.add(sha(norm(r["untrusted_text"])))
out=[]
for host, n in (("en.wikipedia.org", 420), ("simple.wikipedia.org", 100)):
    tries = 0
    got = 0
    while got < n and tries < n*3:
        tries += 1
        d = get(f"https://{host}/api/rest_v1/page/random/summary")
        if not d or d.get("type") == "disambiguation": continue
        t = (d.get("extract") or "").strip(); u = (d.get("content_urls") or {}).get("desktop",{}).get("page","")
        if len(t) < 80 or not u: continue
        h = sha(norm(t))
        if u in seen_u or h in seen_h: continue
        seen_u.add(u); seen_h.add(h); got += 1
        out.append({"id": f"DFP{len(out):04d}", "host": host, "title": d.get("title"), "url": u, "text": t, "text_sha256": h})
        time.sleep(0.05)
(DATA/"dev_fp_pages.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False)+"\n" for r in out))
print(len(out), hashlib.sha256((DATA/"dev_fp_pages.jsonl").read_bytes()).hexdigest())
