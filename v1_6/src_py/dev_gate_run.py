#!/usr/bin/env python3
"""Dev run of the full v1.3 gate (Rust front + worker + classifier + instruction check) on the dev set. Dev only."""
import json, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runlib import *
def rec(r):
    return {"id": r["id"], "qid": r["id"], "session_id": r["id"], "turn_index": 1, "kind": "search_result", "gold": r["gold"], "user_request": "dev query",
            "untrusted_text": r["text"], "proposed_tool": "open_search_result", "proposed_args": "", "allow_list": ["open_search_result", "web_search"],
            "prior_hold": False, "prior_injection": False, "prior_hash": "", "condition_satisfied": False, "override": ""}
rows = jl(DATA/"dev_set.jsonl")
extra = []
fp = DATA/"dev_fp_pages.jsonl"
if fp.exists():
    for r in jl(fp): extra.append({"id": r["id"], "family": "dev_fp_page", "gold": "ALLOW", "text": r["text"]})
allr = rows + extra
inp = OUT/"dev_records.jsonl"; wjl(inp, [rec(r) for r in allr])
with Stack(ROOT, ROOT/"models"/"classifier_v1_2.json", "dev") as st:
    r, outp, logp, sb = st.batch(inp, "dev")
outs = load_out(outp)
c = collections.Counter()
for r in allr:
    o = outs[r["id"]]; d = "allow" if is_allow(o) else "hold"
    c[(r["family"], d, o.get("layer") if d == "hold" else "")] += 1
for k in sorted(c): print(k, c[k])
