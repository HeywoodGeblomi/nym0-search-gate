#!/usr/bin/env python3
"""Dev-only numbers for the v1.4 map check (reported as dev, not as test)."""
import sys, json, collections, numpy as np
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT/"src_py"))
from map_check import MapCheck
from instruction_check import InstructionCheck
import verbmap_seeds as V
mc = MapCheck(ROOT/"models"/"verb_families_v1_3.json", ROOT/"models")
ic = InstructionCheck(ROOT/"models"/"verb_families_v1_3.json")
f = json.load(open(ROOT/"models"/"verb_families_v1_3.json"))
seeds = {v for vs in V.REGIONS.values() for v in vs}
pos = sorted(w for c, e in f["categories"].items() for w in e["tier1"] if w not in seeds and c != "override_rules")
ben = mc.params["anchors"]
sb = np.array([mc.score_phrase(v, exclude_anchor=v)[0] for v in ben]); sp = np.array([mc.score_phrase(v)[0] for v in pos]); su = np.array([mc.score_phrase(v)[0] for v in V.DEV_UNSEEN_RISKY])
tau = mc.tau
out = {"tau": tau, "model": mc.tag(), "everyday_verbs_leave_one_out": {"n": len(sb), "false_hold_rate": round(float((sb >= tau).mean()), 4)},
       "v13_fanout_nonseed_verbs": {"n": len(sp), "in_region_rate": round(float((sp >= tau).mean()), 4)},
       "dev_unseen_risky_verbs": {"n": len(su), "in_region_rate": round(float((su >= tau).mean()), 4), "missed": [v for v, s in zip(V.DEV_UNSEEN_RISKY, su) if s < tau]}}
pages = []
for fn in ("learning_pool", "dev_fp_pages"):
    rows = [json.loads(l) for l in open(ROOT/"data"/f"{fn}.jsonl")]
    out.setdefault("clean_pages", {})[fn] = {"pages": len(rows), "held_by_map_check": sum(mc.check(r["text"])[0] for r in rows), "held_by_instruction_check_v13": sum(ic.check(r["text"])[0] for r in rows)}
dev = [json.loads(l) for l in open(ROOT/"data"/"dev_set.jsonl")]
fam = {}
for r in dev:
    d = fam.setdefault(r["family"], {"n": 0, "map_alone": 0, "v13_check_alone": 0, "either": 0})
    a, b = mc.check(r["text"])[0], ic.check(r["text"])[0]
    d["n"] += 1; d["map_alone"] += a; d["v13_check_alone"] += b; d["either"] += (a or b)
out["dev_set_by_family"] = fam
def lines(fn):
    r = []
    for l in open(ROOT/"data"/fn):
        l = l.rstrip("\n"); l = l.encode().decode("unicode_escape") if "\\u" in l else l
        if l.strip(): r.append(l)
    return r
for fn in ("dev2_phrasings.txt", "dev_neg2.txt", "dev_override_phrasings.txt"):
    L = lines(fn)
    out[fn] = {"n": len(L), "map_alone_held": sum(mc.check(x)[0] for x in L), "v13_check_held": sum(ic.check(x)[0] for x in L), "either_held": sum(mc.check(x)[0] or ic.check(x)[0] for x in L)}
(ROOT/"out"/"DEV_RESULTS.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
