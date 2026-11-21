#!/usr/bin/env python3
"""Development check (before freeze): run the gate on the real learning-VALIDATION pages (clean + planted). No test data."""
import json, sys, subprocess
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from runlib import *
fit = json.load(open(ROOT/"models"/"FIT_RECORD_v1_2.json"))
ids = set(fit["val_page_ids"]); pool = [r for r in jl(DATA/"learning_pool.jsonl") if r["id"] in ids]
T = json.load(open(DATA/"LEARN_TEMPLATES.json"))["families"]; fams = list(T)
import random; rng = random.Random(7)
recs = []
for k, p in enumerate(pool):
    base = {"session_id":"","turn_index":1,"user_request":p["query"] or "random page","kind":"search_result","proposed_tool":"open_search_result","proposed_args":"","allow_list":["open_search_result","web_search"],"prior_hold":False,"prior_injection":False,"prior_hash":"","condition_satisfied":False,"override":""}
    c = dict(base, id=f"vc-{k:04d}", gold="ALLOW", untrusted_text=p["text"]); c["session_id"] = c["id"]
    recs.append(c)
wjl(ROOT/"out"/"valpages_clean.jsonl", recs)
with Stack(ROOT, ROOT/"models"/"classifier_v1_2.json", "val") as st:
    r, outp, logp, sb = st.batch(ROOT/"out"/"valpages_clean.jsonl", "valpages_clean")
outs = load_out(outp); s = summarize(recs, outs, sb)
res = {"n": len(recs), "returncode": r.returncode, "panic": "panicked" in (r.stderr or "").lower(), **s}
json.dump(res, open(ROOT/"out"/"VALPAGES_RULE_CHECK.json","w"), indent=1); print(json.dumps(res, indent=1))
