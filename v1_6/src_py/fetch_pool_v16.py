#!/usr/bin/env python3
"""Dev-only pool of public command-heavy harmless pages for v1.6 (Wikibooks Cookbook, Wikibooks how-tos and game rules, Wikivoyage, Wikisource manuals).
Public MediaWiki APIs only. Deduplicated against every earlier set. Never test data."""
import json, re, time, random, hashlib, urllib.parse, urllib.request, unicodedata, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; DATA = ROOT/"data"
UA = "Nym0SearchGate/1.6 (research dev pool; public MediaWiki APIs; contact: none)"
rng = random.Random(1606)
def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def norm(t): return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", t)).strip().lower()
def api(host, params, tries=3):
    u = f"https://{host}/w/api.php?" + urllib.parse.urlencode(dict(params, format="json"))
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=30) as r: return json.load(r)
        except Exception: time.sleep(1.5 + k)
    return None
seen_url, seen_h, seen_title = set(), set(), set()
def addseen(url=None, text=None, title=None):
    if url: seen_url.add(url)
    if text: seen_h.add(sha(norm(text)[:300]))
    if title: seen_title.add(title.lower())
for p in ["new_all.jsonl", "learning_pool.jsonl", "dev_fp_pages.jsonl", "test_set.jsonl", "V13_test_set.jsonl"]:
    for l in open(DATA/p):
        r = json.loads(l); addseen(r.get("source_url") or r.get("url"), r.get("untrusted_text") or r.get("text"), r.get("source_title") or r.get("title"))
for p in ["/workspace/frontier_pivot/search_gate_v1_2/data/test_set.jsonl", "/workspace/frontier_pivot/search_gate_test_v1/data/official_set.jsonl"]:
    for l in open(p):
        r = json.loads(l); addseen(r.get("source_url"), r.get("untrusted_text"), r.get("source_title"))
out = []
def add(source, title, url, text):
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 200: return False
    if len(text) > 950:
        cut = text[:950]; i = cut.rfind(". "); text = cut[:i + 1] if i > 300 else cut
    h = sha(norm(text)[:300])
    if url in seen_url or h in seen_h or title.lower() in seen_title: return False
    addseen(url, text, title)
    out.append({"id": f"P16-{len(out):04d}", "source": source, "title": title, "url": url, "text": text, "text_sha256": sha(norm(text))})
    return True
def extract(host, title):
    d = api(host, dict(action="query", prop="extracts|info", explaintext=1, redirects=1, inprop="url", titles=title))
    if not d: return None, None, None
    p = list(d["query"]["pages"].values())[0]
    return p.get("title"), p.get("fullurl"), p.get("extract") or ""
def section(ex, names):
    m = re.search(r"==\s*(?:%s)\s*==\s*(.+)" % names, ex, re.S | re.I)
    if not m: return None
    return re.split(r"\n==", m.group(1))[0].strip()
def log(*a): print(*a, flush=True)
# 1. Cookbook recipes (namespace 102, random and category), "Procedure." extract like real search snippets
titles = []
for _ in range(14):
    d = api("en.wikibooks.org", dict(action="query", list="random", rnnamespace=102, rnlimit=500))
    if d: titles += [m["title"] for m in d["query"]["random"]]
titles = list(dict.fromkeys(t for t in titles if t.startswith("Cookbook:") and "/" not in t)); rng.shuffle(titles)
log("cookbook titles", len(titles))
n = 0
for t in titles:
    if n >= 520: break
    ti, url, ex = extract("en.wikibooks.org", t)
    if not ex: continue
    s = section(ex, "Procedure|Instructions|Directions|Method|Preparation|Steps")
    if not s: continue
    s = " ".join(l.strip() for l in s.split("\n") if l.strip())
    if add("wikibooks_cookbook", ti, url, "Procedure. " + s): n += 1
    time.sleep(0.03)
log("cookbook", n)
# 2. Wikibooks how-tos and game rules by search
queries = {"wb_howto": ["how to step by step", "tutorial instructions", "install and configure steps", "repair guide", "assemble instructions", "first aid steps", "knitting patterns instructions", "gardening how to", "car maintenance steps", "bicycle repair", "woodworking instructions", "cleaning guide", "camping guide", "sewing instructions", "setup guide", "troubleshooting steps", "computer how to", "cooking techniques", "exercise routine instructions", "drawing tutorial"],
           "wb_game_rules": ["rules of the game how to play", "card game rules", "board game rules", "how to play chess", "dice game rules", "playing the game setup turns", "tabletop game how to play"]}
for src, qs in queries.items():
    n = 0
    for q in qs:
        for off in (0, 20):
            d = api("en.wikibooks.org", dict(action="query", list="search", srsearch=q, srnamespace=0, srlimit=20, sroffset=off))
            if not d: continue
            for m in d["query"]["search"]:
                ti, url, ex = extract("en.wikibooks.org", m["title"])
                if not ex or len(ex) < 400: continue
                body = " ".join(l.strip() for l in ex.split("\n") if l.strip() and not l.startswith("="))
                # first window that has an imperative-looking start somewhere is not required; take a window from the middle of the intro to avoid pure titles
                if add(src, ti, url, body[:1100]): n += 1
                time.sleep(0.03)
    log(src, n)
# 3. Wikivoyage guides
n = 0; wv = []
for _ in range(6):
    d = api("en.wikivoyage.org", dict(action="query", list="random", rnnamespace=0, rnlimit=500))
    if d: wv += [m["title"] for m in d["query"]["random"]]
wv = list(dict.fromkeys(wv)); rng.shuffle(wv)
for t in wv:
    if n >= 260: break
    ti, url, ex = extract("en.wikivoyage.org", t)
    if not ex: continue
    s = section(ex, "Get around|Stay safe|Get in|Respect|Cope|Eat|Buy|Do|Drink|Stay healthy")
    if not s: continue
    s = " ".join(l.strip() for l in s.split("\n") if l.strip())
    if add("wikivoyage", ti, url, s): n += 1
    time.sleep(0.03)
log("wikivoyage", n)
# 4. Wikisource public-domain manuals and handbooks
n = 0; ws_titles = []
for q in ["manual of instructions", "handbook directions how to", "the housekeeper's guide", "camp cookery directions", "rules of the game", "field manual", "instructions for use", "boy scouts handbook", "domestic recipes directions", "first aid manual"]:
    d = api("en.wikisource.org", dict(action="query", list="search", srsearch=q, srnamespace=0, srlimit=30))
    if d: ws_titles += [m["title"] for m in d["query"]["search"]]
ws_titles = list(dict.fromkeys(ws_titles)); rng.shuffle(ws_titles)
for t in ws_titles:
    if n >= 80: break
    ti, url, ex = extract("en.wikisource.org", t)
    if not ex or len(ex) < 500: continue
    body = " ".join(l.strip() for l in ex.split("\n") if l.strip() and not l.startswith("="))
    if add("wikisource_manual", ti, url, body[:1100]): n += 1
    time.sleep(0.03)
log("wikisource", n)
(DATA/"pool_v16.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
log("total", len(out), hashlib.sha256((DATA/"pool_v16.jsonl").read_bytes()).hexdigest())
