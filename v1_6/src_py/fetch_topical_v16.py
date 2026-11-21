#!/usr/bin/env python3
"""Dev-only topical Wikipedia pages (banking, payments, email, security, files, accounts, smart home, robotics...) as hard clean examples for v1.6.
Public MediaWiki API. Deduplicated against the pool and earlier sets. Never test data."""
import json, re, time, random, hashlib, urllib.parse, urllib.request, unicodedata
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; DATA = ROOT/"data"
UA = "Nym0SearchGate/1.6 (research dev pool; public MediaWiki API; contact: none)"
def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def norm(t): return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", t)).strip().lower()
def api(params):
    u = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(dict(params, format="json"))
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30) as r: return json.load(r)
        except Exception: time.sleep(1.5 + k)
seen_u, seen_h = set(), set()
for p in ["new_all.jsonl", "learning_pool.jsonl", "dev_fp_pages.jsonl", "test_set.jsonl", "pool_v16.jsonl"]:
    for l in open(DATA/p):
        r = json.loads(l); seen_u.add(r.get("source_url") or r.get("url")); seen_h.add(sha(norm(r.get("untrusted_text") or r.get("text"))[:300]))
CATS = ["Banking", "Payment systems", "Electronic funds transfer", "Online banking", "Personal finance", "Credit cards", "Money laundering", "Fraud", "Email", "Instant messaging", "Social media", "Computer security", "Cryptography", "Authentication", "Passwords", "Computer access control", "Data security", "Data management", "Backup", "Computer file systems", "Cloud computing", "Computer networking", "Web security exploits", "Malware", "Home automation", "Internet of things", "Robotics", "Industrial robots", "Security alarms", "Physical security", "Smart home hubs", "Software engineering", "Version control", "Computer programming", "Operating system security", "E-commerce", "Online shopping", "Subscription services", "Domain name system", "Telecommunications", "Mobile payments", "Cryptocurrencies", "Accounting", "Insurance", "Investment", "Taxation", "Customer relationship management", "Calendar", "Information technology management", "Cooking techniques", "Kitchen utensils", "Baking", "Food preparation", "Board games", "Card games", "Hiking", "Travel", "First aid", "Home repair", "Woodworking", "Gardening"]
rng = random.Random(1607); out = []
for cat in CATS:
    cont = {}; got = 0
    for _ in range(3):
        d = api(dict(action="query", generator="categorymembers", gcmtitle="Category:" + cat, gcmlimit=20, gcmnamespace=0, prop="extracts|info", exintro=1, explaintext=1, exlimit=20, inprop="url", **cont))
        if not d or "query" not in d: break
        for p in d["query"]["pages"].values():
            t = re.sub(r"\s+", " ", p.get("extract") or "").strip(); u = p.get("fullurl", "")
            if len(t) < 200 or not u: continue
            if len(t) > 950: cut = t[:950]; i = cut.rfind(". "); t = cut[:i + 1] if i > 300 else cut
            h = sha(norm(t)[:300])
            if u in seen_u or h in seen_h: continue
            seen_u.add(u); seen_h.add(h); got += 1
            out.append({"id": f"T16-{len(out):04d}", "source": "wp_topical:" + cat, "title": p.get("title"), "url": u, "text": t, "text_sha256": sha(norm(t))})
        if "continue" in d: cont = d["continue"]
        else: break
        time.sleep(0.05)
    print(cat, got, flush=True)
(DATA/"topical_v16.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
print("total", len(out), hashlib.sha256((DATA/"topical_v16.jsonl").read_bytes()).hexdigest())
