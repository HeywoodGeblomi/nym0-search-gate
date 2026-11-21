#!/usr/bin/env python3
"""Dev report for v1.5: map check alone and with the v1.3 instruction check, per dev family, plus the dev phrasing files. Dev data only."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT/"src_py"))
from map_check import MapCheck
from map_check15 import MapCheck15
from instruction_check import InstructionCheck
import importlib
fam = ROOT/"models"/"verb_families_v1_3.json"
m4 = MapCheck(fam, ROOT/"models"); m5 = MapCheck15(fam, ROOT/"models"); ic = InstructionCheck(fam)
def lines(fn):
    r = []
    for l in open(ROOT/"data"/fn):
        l = l.rstrip("\n"); l = l.encode().decode("unicode_escape") if "\\u" in l else l
        if l.strip(): r.append(l)
    return r
out = {}
dev = [json.loads(l) for l in open(ROOT/"data"/"dev_set.jsonl")]
fa = {}
for r in dev:
    d = fa.setdefault(r["family"], {"n": 0, "gold": r["gold"], "v14_map": 0, "v15_map": 0, "v13_check": 0, "v14_either": 0, "v15_either": 0})
    a, b, c = m4.check(r["text"])[0], m5.check(r["text"])[0], ic.check(r["text"])[0]
    d["n"] += 1; d["v14_map"] += a; d["v15_map"] += b; d["v13_check"] += c; d["v14_either"] += (a or c); d["v15_either"] += (b or c)
out["dev_set_by_family"] = fa
for fn in ("dev2_phrasings.txt", "dev_neg2.txt", "dev_override_phrasings.txt"):
    L = lines(fn)
    out[fn] = {"n": len(L), "v14_map": sum(m4.check(x)[0] for x in L), "v15_map": sum(m5.check(x)[0] for x in L), "v13_check": sum(ic.check(x)[0] for x in L),
               "v14_either": sum(m4.check(x)[0] or ic.check(x)[0] for x in L), "v15_either": sum(m5.check(x)[0] or ic.check(x)[0] for x in L)}
for fn in ("learning_pool", "dev_fp_pages"):
    rows = [json.loads(l) for l in open(ROOT/"data"/f"{fn}.jsonl")]
    out.setdefault("clean_pages", {})[fn] = {"pages": len(rows), "v14_map_held": sum(m4.check(r["text"])[0] for r in rows), "v15_map_held": sum(m5.check(r["text"])[0] for r in rows)}
print(json.dumps(out, indent=1))
(ROOT/"out"/"DEV_RESULTS_v15.json").write_text(json.dumps(out, indent=1))
