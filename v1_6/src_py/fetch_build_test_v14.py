#!/usr/bin/env python3
"""Step 5 (v1.4): fetch the test pages (after TEST_QUERY_LOCK, TEST_TEMPLATE_LOCK and VERB_LOCK are hashed), plant, write SET_LOCK, run separation check."""
import json, hashlib, time, urllib.parse, urllib.request, re, unicodedata
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT = Path(__file__).resolve().parents[1]; DATA = ROOT/"data"
V1 = Path("/workspace/frontier_pivot/search_gate_test_v1/data")
UA = "Nym0SearchGate/1.4 (research test of a local safety gate; unauthenticated public Wikipedia API)"
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
for f in ("TEST_QUERY_LOCK.json","TEST_TEMPLATE_LOCK.json","VERB_LOCK.json"):
    assert hashlib.sha256((DATA/f).read_bytes()).hexdigest()==(DATA/(f+".sha256")).read_text().split()[0]
learn = [json.loads(l) for l in open(DATA/"learning_pool.jsonl")] + [json.loads(l) for l in open(DATA/"dev_fp_pages.jsonl")]   # learning pool + dev pages
lurls={r["url"] for r in learn}; lhash={r["text_sha256"] for r in learn}
V12C = [json.loads(l) for l in open("/workspace/frontier_pivot/search_gate_v1_2/data/test_clean.jsonl")]
v12urls={r["source_url"] for r in V12C}; v12hash={sha(norm(r["untrusted_text"])) for r in V12C}
V13C = [json.loads(l) for l in open(DATA/"V13_test_clean.jsonl")]
v13urls={r["source_url"] for r in V13C}; v13hash={sha(norm(r["untrusted_text"])) for r in V13C}
v1 = [json.loads(l) for l in open(V1/"official_clean.jsonl")]
v1urls={r["source_url"] for r in v1}; v1hash={sha(norm(r["untrusted_text"])) for r in v1}
Q = json.load(open(DATA/"TEST_QUERY_LOCK.json"))["queries"]
TL = json.load(open(DATA/"TEST_TEMPLATE_LOCK.json")); VL = json.load(open(DATA/"VERB_LOCK.json"))
attempts=[]; kept=[]
t0=now()
for q in Q:
    if len(kept)>=160: break
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
        if url in v12urls or hh in v12hash: c["status"]="collides_with_v1_2_test_set"; att["candidates"].append(c); continue
        if url in v13urls or hh in v13hash: c["status"]="collides_with_v1_3_test_set"; att["candidates"].append(c); continue
        if url in {k["url"] for k in kept}: c["status"]="duplicate_within_v1_4"; att["candidates"].append(c); continue
        c["status"]="kept"; att["candidates"].append(c)
        kept.append({"qid":q["qid"],"query":q["query"],"title":sd.get("title") or t,"url":url,"text":text,"text_sha256":hh}); att["kept"]=True; break
    attempts.append(att); time.sleep(0.05)
if len(kept)<150: raise SystemExit(f"only {len(kept)} usable; construction deviation, stop")
main_kept=kept[:80]; slice_kept=kept[80:160]
fo=TL["family_order"]; assert all(sum(1 for t in TL["templates"] if t["family"]==f)==16 for f in fo)
def rec(oid, k, text, gold, fam=None, tmpl=None, mid=None):
    return {"id":oid,"qid":k["qid"],"session_id":oid,"turn_index":1,"kind":"search_result","gold":gold,"user_request":k["query"],"untrusted_text":text,
            "proposed_tool":"open_search_result","proposed_args":"","allow_list":["open_search_result","web_search"],"prior_hold":False,"prior_injection":False,"prior_hash":"",
            "condition_satisfied":False,"override":"","injection_family":fam,"planted_template":tmpl,"matched_clean_id":mid,"source_title":k["title"],"source_url":k["url"],"fetch_source":"wikipedia_rest_summary"}
clean=[]; inj=[]
for i,k in enumerate(main_kept):
    clean.append(rec(f"C-{k['qid']}",k,k["text"],"ALLOW"))
    fam=fo[i%5]; opts=[t["text"] for t in TL["templates"] if t["family"]==fam]; tm=opts[(i//5)%len(opts)]
    base=k["text"].rstrip()
    if fam=="hidden_markdown": body=base+"\n\n"+tm
    elif fam=="buried_request":
        ss=base.split(". "); mid=max(1,len(ss)//2)
        body=". ".join(ss[:mid])+". "+tm+" "+". ".join(ss[mid:]) if len(ss)>1 else base+" "+tm
    else: body=base+" "+tm
    inj.append(rec(f"I-{k['qid']}",k,body.strip(),"HOLD",fam,tm,f"C-{k['qid']}"))
slc=[]
for j,k in enumerate(slice_kept):
    if j<40:
        e=VL["unseen_risky"][j]; r=rec(f"S-U{j+1:02d}-{k['qid']}",k,(k["text"].rstrip()+" "+e["sentence"]).strip(),"HOLD","unseen_verb",e["sentence"],None)
        r.update({"slice":"unseen_risky","key_verb":e["verb"],"category":e["category"]})
    else:
        e=VL["everyday_imperative"][j-40]; r=rec(f"S-E{j-39:02d}-{k['qid']}",k,(k["text"].rstrip()+" "+e["sentence"]).strip(),"ALLOW","everyday_imperative",e["sentence"],None)
        r.update({"slice":"everyday_imperative","key_verb":e["verb"],"category":None})
    slc.append(r)
def w(name, rows):
    with open(DATA/name,"w") as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False)+"\n")
    h=hashlib.sha256((DATA/name).read_bytes()).hexdigest(); (DATA/(name+".sha256")).write_text(h+"  "+name+"\n"); return h
hs={"test_clean.jsonl":w("test_clean.jsonl",clean),"test_injected.jsonl":w("test_injected.jsonl",inj),"test_set.jsonl":w("test_set.jsonl",clean+inj),"slice_set.jsonl":w("slice_set.jsonl",slc)}
# P9 separation check
test_urls={k["url"] for k in kept}; test_hash={k["text_sha256"] for k in kept}; test_q={k["query"].lower() for k in kept}
lq={q.lower() for q in json.load(open(DATA/"LEARN_QUERY_LOCK.json"))["queries"]}; v1q={r["user_request"].lower() for r in v1}
v12q={q["query"].lower() for q in json.load(open(DATA/"V12_TEST_QUERY_LOCK.json"))["queries"]}
v13q={q["query"].lower() for q in json.load(open(DATA/"V13_TEST_QUERY_LOCK.json"))["queries"]}
sep={"learning_and_dev_vs_v1_3_test":{"shared_urls":len(lurls&v13urls),"shared_text_hashes":len(lhash&v13hash),"shared_queries":len(lq&v13q)},
     "test_vs_v1_3_test":{"shared_urls":len(test_urls&v13urls),"shared_text_hashes":len(test_hash&v13hash),"shared_queries":len(test_q&v13q)},
     "learning_and_dev_vs_test":{"shared_urls":len(lurls&test_urls),"shared_text_hashes":len(lhash&test_hash),"shared_queries":len(lq&test_q)},
     "learning_and_dev_vs_v1":{"shared_urls":len(lurls&v1urls),"shared_text_hashes":len(lhash&v1hash),"shared_queries":len(lq&v1q)},
     "learning_and_dev_vs_v1_2_test":{"shared_urls":len(lurls&v12urls),"shared_text_hashes":len(lhash&v12hash),"shared_queries":len(lq&v12q)},
     "test_vs_v1":{"shared_urls":len(test_urls&v1urls),"shared_text_hashes":len(test_hash&v1hash),"shared_queries":len(test_q&v1q)},
     "test_vs_v1_2_test":{"shared_urls":len(test_urls&v12urls),"shared_text_hashes":len(test_hash&v12hash),"shared_queries":len(test_q&v12q)}}
sep["template_sentence_overlap_with_dev_learning_v13_v12"]=TL["overlap"]["exact_sentences_shared_with_dev_learning_v13_v12"]; sep["held_out_verb_disjointness_failures"]=sum(len(v) if isinstance(v,list) else v for v in VL["disjointness_checks"].values())
sep["total_shared"]=sum(v for d in sep.values() if isinstance(d,dict) for v in d.values())+sep["template_sentence_overlap_with_dev_learning_v13_v12"]+sep["held_out_verb_disjointness_failures"]
json.dump(sep,open(DATA/"SEPARATION_CHECK.json","w"),indent=1)
json.dump({"started_at":t0,"finished_at":now(),"method":"wikipedia_search_top3_then_rest_summary","user_agent":UA,"n_kept":len(kept),"n_queries_tried":len(attempts),
           "skipped_queries":[a["qid"] for a in attempts if not a.get("kept")],"test_query_lock_sha256":(DATA/"TEST_QUERY_LOCK.json.sha256").read_text().split()[0],
           "test_template_lock_sha256":(DATA/"TEST_TEMPLATE_LOCK.json.sha256").read_text().split()[0],"verb_lock_sha256":(DATA/"VERB_LOCK.json.sha256").read_text().split()[0],"attempts":attempts},open(DATA/"TEST_FETCH_RECEIPT.json","w"),indent=1)
json.dump({"written_at":now(),"n_clean":len(clean),"n_injected":len(inj),"n_slice":len(slc),"sha256":hs},open(DATA/"TEST_SET_LOCK.json","w"),indent=1)
(DATA/"TEST_SET_LOCK.json.sha256").write_text(hashlib.sha256((DATA/"TEST_SET_LOCK.json").read_bytes()).hexdigest()+"  TEST_SET_LOCK.json\n")
print(len(kept),hs,sep)
