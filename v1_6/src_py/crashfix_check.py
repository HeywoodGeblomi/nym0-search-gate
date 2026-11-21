#!/usr/bin/env python3
"""v1.1 crash-fix check: one full batch on the unchanged official set. Not a keep score."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_official import *
from collections import Counter
OUT.mkdir(exist_ok=True); RUN.mkdir(exist_ok=True)
assert sha_file(DATA/"official_set.jsonl")==OFFICIAL_SET_SHA
sock=RUN/"w.sock"; pid=RUN/"w.pid"; cs=RUN/"c.sock"; cp=RUN/"c.pid"
start_policy(sock,pid,logpath=RUN/"w.log"); start_clf(cs,cp,logpath=RUN/"c.log")
official=load_jsonl(DATA/"official_set.jsonl")
rr=batch(DATA/"official_set.jsonl",OUT/"out.jsonl",OUT/"run.log",OUT/"sb",sock,cs)
outs=load_out(OUT/"out.jsonl") if (OUT/"out.jsonl").exists() else {}
c=Counter(); layers=Counter()
for r in official:
    o=outs.get(r["id"])
    d="missing" if o is None else ("allow" if is_allow(o) else "hold")
    c[(r["gold"],d)]+=1
    if o is not None and d=="hold" and r["gold"].lower()!="hold": layers[o.get("layer")]+=1
res={"returncode":rr.returncode,"panicked":"panicked" in (rr.stderr or "").lower(),
     "decided":len(outs),"total":len(official),"by_gold_decision":{f"{a}/{b}":n for (a,b),n in c.items()},
     "clean_hold_layers":dict(layers),"stderr_tail":(rr.stderr or "")[-300:]}
json.dump(res,open(OUT/"CRASHFIX_CHECK.json","w"),indent=1); print(json.dumps(res,indent=1))
kill_proc(sock,pid,stop_args=["worker","stop"]); kill_proc(cs,cp)
