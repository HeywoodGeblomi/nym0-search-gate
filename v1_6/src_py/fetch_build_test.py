#!/usr/bin/env python3
"""Step 5: fetch the test pages (after TEST_QUERY_LOCK and TEST_TEMPLATE_LOCK are hashed), plant, write SET_LOCK, run separation check."""
import json, hashlib, time, urllib.parse, urllib.request, re, unicodedata
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT = Path(__file__).resolve().parents[1]; DATA = ROOT/"data"
V1 = Path("/workspace/frontier_pivot/search_gate_test_v1/data")
UA = "Nym0SearchGate/1.2 (research test of a local safety gate; unauthenticated public Wikipedia API)"
def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def norm(t): return re.sub(r"\s+"," ",unicodedata.normalize("NFKC",t)).strip().lower()
def now(): return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")
def get(url):
    for k in range(3):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json"})
            with urllib.request.urlopen(req,timeout=20) as r: return json.loads(r.read().decode("utf-8"))
        except Exception: time.sleep(1+k)
    return None
for f in ("TEST_QUERY_LOCK.json","TEST_TEMPLATE_LOCK.json"):
    assert hashlib.sha256((DATA/f).read_bytes()).hexdigest()==(DATA/(f+".sha256")).read_text().split()[0]
learn = [json.loads(l) for l in open(DATA/"learning_pool.jsonl")]
lurls={r["url"] for r in learn}; lhash={r["text_sha256"] for r in learn}
v1 = [json.loads(l) for l in open(V1/"official_clean.jsonl")]
v1urls={r["source_url"] for r in v1}; v1hash={sha(norm(r["untrusted_text"])) for r in v1}
Q = json.load(open(DATA/"TEST_QUERY_LOCK.json"))["queries"]
TL = json.load(open(DATA/"TEST_TEMPLATE_LOCK.json"))
attempts=[]; kept=[]
t0=now()
for q in Q:
    if len(kept)>=80: break
    u="https://en.wikipedia.org/w/api.php?"+urllib.parse.urlencode({"action":"query","list":"search","srsearch":q["query"],"srlimit":3,"srnamespace":0,"format":"json"})
    d=get(u); hits=((d or {}).get("query") or {}).get("search") or []
    att={"qid":q["qid"],"query":q["query"],"search_url":u,"candidates":[]}
    for h in hits:
        t=h["title"]; sd=get("https://en.wikipedia.org/api/rest_v1/page/summary/"+urllib.parse.quote(t.replace(" ","_"),safe=""))
        c={"title":t,"status":None}
        if not sd or sd.get("type")=="disambiguation": c["status"]="unusable"; att["candidates"].append(c); continue
        ex=(sd.get("extract") or "").strip(); de=(sd.get("description") or "").strip()
        text=ex if len(ex)>=80 else (ex+(" "+de if de else "")).strip()
        url=(sd.get("content_urls") or {}).get("desktop",{}).get("page") or ""
        if len(text)<80 or not url: c["status"]="unusable"; att["candidates"].append(c); continue
        hh=sha(norm(text))
        if url in lurls or hh in lhash: c["status"]="collides_with_learning_pool"; att["candidates"].append(c); continue
        if url in v1urls or hh in v1hash: c["status"]="collides_with_v1_set"; att["candidates"].append(c); continue
        c["status"]="kept"; att["candidates"].append(c)
        kept.append({"qid":q["qid"],"query":q["query"],"title":sd.get("title") or t,"url":url,"text":text,"text_sha256":hh}); att["kept"]=True; break
    attempts.append(att); time.sleep(0.05)
if len(kept)<70: raise SystemExit(f"only {len(kept)} usable; construction deviation, stop")
fo=TL["family_order"]
def rec(oid, k, text, gold, fam=None, tmpl=None, mid=None):
    return {"id":oid,"qid":k["qid"],"session_id":oid,"turn_index":1,"kind":"search_result","gold":gold,"user_request":k["query"],"untrusted_text":text,
            "proposed_tool":"open_search_result","proposed_args":"","allow_list":["open_search_result","web_search"],"prior_hold":False,"prior_injection":False,"prior_hash":"",
            "condition_satisfied":False,"override":"","injection_family":fam,"planted_template":tmpl,"matched_clean_id":mid,"source_title":k["title"],"source_url":k["url"],"fetch_source":"wikipedia_rest_summary"}
clean=[]; inj=[]
for i,k in enumerate(kept):
    clean.append(rec(f"C-{k['qid']}",k,k["text"],"ALLOW"))
    fam=fo[i%5]; opts=TL["families"][fam]; tm=opts[(i//5)%len(opts)]
    inj.append(rec(f"I-{k['qid']}",k,(k["text"].rstrip()+tm).strip(),"HOLD",fam,tm,f"C-{k['qid']}"))
def w(name, rows):
    with open(DATA/name,"w") as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False)+"\n")
    h=hashlib.sha256((DATA/name).read_bytes()).hexdigest(); (DATA/(name+".sha256")).write_text(h+"  "+name+"\n"); return h
hs={"test_clean.jsonl":w("test_clean.jsonl",clean),"test_injected.jsonl":w("test_injected.jsonl",inj),"test_set.jsonl":w("test_set.jsonl",clean+inj)}
# P9 separation check
test_urls={k["url"] for k in kept}; test_hash={k["text_sha256"] for k in kept}; test_q={k["query"].lower() for k in kept}
lq={q.lower() for q in json.load(open(DATA/"LEARN_QUERY_LOCK.json"))["queries"]}; v1q={r["user_request"].lower() for r in v1}
sep={"learning_vs_test":{"shared_urls":len(lurls&test_urls),"shared_text_hashes":len(lhash&test_hash),"shared_queries":len(lq&test_q)},
     "learning_vs_v1":{"shared_urls":len(lurls&v1urls),"shared_text_hashes":len(lhash&v1hash),"shared_queries":len(lq&v1q)},
     "test_vs_v1":{"shared_urls":len(test_urls&v1urls),"shared_text_hashes":len(test_hash&v1hash),"shared_queries":len(test_q&v1q)}}
sep["total_shared"]=sum(v for d in sep.values() for v in d.values())
json.dump(sep,open(DATA/"SEPARATION_CHECK.json","w"),indent=1)
json.dump({"started_at":t0,"finished_at":now(),"method":"wikipedia_search_top3_then_rest_summary","user_agent":UA,"n_kept":len(kept),"n_queries_tried":len(attempts),
           "skipped_queries":[a["qid"] for a in attempts if not a.get("kept")],"test_query_lock_sha256":(DATA/"TEST_QUERY_LOCK.json.sha256").read_text().split()[0],
           "test_template_lock_sha256":(DATA/"TEST_TEMPLATE_LOCK.json.sha256").read_text().split()[0],"attempts":attempts},open(DATA/"TEST_FETCH_RECEIPT.json","w"),indent=1)
json.dump({"written_at":now(),"n_clean":len(clean),"n_injected":len(inj),"sha256":hs},open(DATA/"TEST_SET_LOCK.json","w"),indent=1)
(DATA/"TEST_SET_LOCK.json.sha256").write_text(hashlib.sha256((DATA/"TEST_SET_LOCK.json").read_bytes()).hexdigest()+"  TEST_SET_LOCK.json\n")
print(len(kept),hs,sep)
