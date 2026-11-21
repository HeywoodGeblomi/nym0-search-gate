#!/usr/bin/env python3
"""Step 3a: fetch the real clean public learning pool (unauthenticated Wikipedia-family REST/search)."""
import json, hashlib, time, urllib.parse, urllib.request, re, unicodedata
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT = Path(__file__).resolve().parents[1]; DATA = ROOT/"data"
V1 = Path("/workspace/frontier_pivot/search_gate_test_v1/data")
UA = "Nym0SearchGate/1.2 (research learning pool; unauthenticated public wiki APIs; contact: none)"
def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def norm(t): return re.sub(r"\s+"," ",unicodedata.normalize("NFKC",t)).strip().lower()
def get(url, tries=3):
    for k in range(tries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=20) as r: return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            err=e; time.sleep(1+k)
    return None
def summ(d):
    if not d or d.get("type")=="disambiguation": return None
    ex=(d.get("extract") or "").strip(); de=(d.get("description") or "").strip()
    text=ex if len(ex)>=80 else (ex+(" "+de if de else "")).strip()
    url=(d.get("content_urls") or {}).get("desktop",{}).get("page") or ""
    if len(text)<80 or not url: return None
    return {"title":d.get("title"),"url":url,"text":text}
# exclusion set: v1 official set
v1urls=set(); v1hash=set()
for l in open(V1/"official_clean.jsonl"):
    r=json.loads(l); v1urls.add(r["source_url"]); v1hash.add(sha(norm(r["untrusted_text"])))
v1q={json.loads(l)["user_request"].lower() for l in open(V1/"official_clean.jsonl")}
lq=json.load(open(DATA/"LEARN_QUERY_LOCK.json"))["queries"]
assert not (v1q & {q.lower() for q in lq}), "learning queries overlap v1 queries"
pool=[]; seenu=set(v1urls); seenh=set(v1hash); drops={"dup_or_v1":0,"unusable":0}
def add(rec, src, q=None):
    if rec is None: drops["unusable"]+=1; return
    h=sha(norm(rec["text"]))
    if rec["url"] in seenu or h in seenh: drops["dup_or_v1"]+=1; return
    seenu.add(rec["url"]); seenh.add(h)
    pool.append({"id":f"L{len(pool):04d}","source":src,"query":q,"title":rec["title"],"url":rec["url"],"text":rec["text"],"text_sha256":h})
t0=time.time()
for q in lq:
    u="https://en.wikipedia.org/w/api.php?"+urllib.parse.urlencode({"action":"query","list":"search","srsearch":q,"srlimit":3,"srnamespace":0,"format":"json"})
    d=get(u); hits=((d or {}).get("query") or {}).get("search") or []
    for h in hits:
        t=h["title"].replace(" ","_")
        add(summ(get("https://en.wikipedia.org/api/rest_v1/page/summary/"+urllib.parse.quote(t,safe=""))),"en_wikipedia_search",q)
    time.sleep(0.05)
print("search done",len(pool),time.time()-t0,flush=True)
for src,host,n in (("en_wikipedia_random","en.wikipedia.org",260),("simple_wikipedia_random","simple.wikipedia.org",120),("wikivoyage_random","en.wikivoyage.org",100)):
    got=0; tries=0
    while got<n and tries<n*3:
        tries+=1; before=len(pool)
        add(summ(get(f"https://{host}/api/rest_v1/page/random/summary")),src)
        got+=len(pool)-before; time.sleep(0.03)
    print(src,got,flush=True)
now=datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")
with open(DATA/"learning_pool.jsonl","w") as f:
    for r in pool: f.write(json.dumps(r,ensure_ascii=False)+"\n")
h=hashlib.sha256((DATA/"learning_pool.jsonl").read_bytes()).hexdigest()
json.dump({"fetched_at":now,"n":len(pool),"by_source":{s:sum(1 for r in pool if r["source"]==s) for s in {r["source"] for r in pool}},"drops":drops,"sha256":h,"user_agent":UA,"learn_query_lock_sha256":open(DATA/"LEARN_QUERY_LOCK.json.sha256").read().split()[0]},open(DATA/"LEARNING_POOL_LOCK.json","w"),indent=1)
(DATA/"learning_pool.jsonl.sha256").write_text(h+"  learning_pool.jsonl\n"); print(len(pool),h,drops)
