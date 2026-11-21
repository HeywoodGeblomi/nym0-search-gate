#!/usr/bin/env python3
"""Reported after scoring (not a bar): the new-set scores for v1.6, v1.5 and v1.4 with the records removed that share a URL, title or text start with any dev data (data/SEPARATION_CHECK_v16.json)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runlib import *
NS = json.load(open(DATA/"NEWSET.json")); SC = json.load(open(DATA/"SEPARATION_CHECK_v16.json"))
ov = {x[0] for k in ("url", "title", "text_hash") for x in SC["overlaps"][k]}
pool = {x[0] for x in SC["overlaps"]["url"] if x[1] in ("pool_v16", "topical_v16", "learning_pool")}
def L(root, tag): return load_out(root/"out"/f"{tag}.out.jsonl")
o = {"v1_6": L(ROOT, "new_v16"), "v1_5": L(ROOT/"baseline_v1_5", "new_v15"), "v1_4": L(ROOT/"baseline_v1_4", "new_v14")}
def held(x, i): return i in x and not is_allow(x[i])
res = {"overlapping_ids": sorted(ov), "overlapping_with_fit_or_val_pool_pages": sorted(pool), "n_overlap": len(ov)}
for name, flt in (("all_300", lambda i: True), ("without_overlap", lambda i: i not in ov), ("only_overlap", lambda i: i in ov)):
    g = {}
    for gn, ids in (("injected", NS["injected"]), ("unseen", NS["unseen"]), ("clean", NS["clean"])):
        ids = [i for i in ids if flt(i)]; g[gn] = {"n": len(ids), **{v: sum(held(o[v], i) for i in ids) for v in o}}
    res[name] = g
res["clean_by_source_without_overlap"] = {}
for src in sorted(set(NS["clean_source"][i] for i in NS["clean"])):
    ids = [i for i in NS["clean"] if NS["clean_source"][i] == src and i not in ov]; res["clean_by_source_without_overlap"][src] = {"n": len(ids), **{v: sum(held(o[v], i) for i in ids) for v in o}}
json.dump(res, open(OUT/"SENSITIVITY_v16.json", "w"), indent=1); print(json.dumps(res, indent=1))
