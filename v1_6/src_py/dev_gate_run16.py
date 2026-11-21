#!/usr/bin/env python3
"""Dev: run the v1.6 stack (Rust front door, Rust and Python map engines) on a dev sample; compare to the emulator and to the v1.5 baseline. Dev only."""
import sys, json, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runlib import *
from collections import Counter
D = jl(DATA/"dev_v16.jsonl"); rng = random.Random(1616)
sel = [r for r in D if r["group"].split(":")[0] in ("v15_inj", "v15_clean", "v15_unseen", "v15_everyday")]
for g in ("pool_clean", "pool_inj", "topical_clean", "topical_inj", "wp_clean", "wp_inj"):
    xs = [r for r in D if r["group"].split(":")[0] == g and r["split"] == "val"]; rng.shuffle(xs); sel += xs[:150]
recs = [{"id": r["id"], "qid": r["id"], "session_id": r["id"], "turn_index": 1, "kind": "search_result", "gold": "HOLD" if r["label"] else "ALLOW", "user_request": "dev", "untrusted_text": r["text"], "proposed_tool": "open_search_result", "proposed_args": "", "allow_list": ["open_search_result", "web_search"], "prior_hold": False, "prior_injection": False, "prior_hash": "", "condition_satisfied": False, "override": ""} for r in sel]
inp = OUT/"dev_gate_sample.jsonl"; wjl(inp, recs)
W = ROOT/"models"/"classifier_v1_6.json"; W15 = ROOT/"baseline_v1_5"/"models"/"classifier_v1_2.json"; B15 = ROOT/"baseline_v1_5"
res = {}
for tag, root, binp, w, eng in (("v16_rust", ROOT, BIN, W, "rust"), ("v16_py", ROOT, BIN, W, "python"), ("v15", B15, B15/"bin"/"nym0asgate", W15, "rust")):
    with Stack(root, w, "dg_" + tag, clf_args=["--map-engine", eng]) as st:
        outp, logp, sb = OUT/f"dg_{tag}.out.jsonl", OUT/f"dg_{tag}.log", OUT/f"dg_{tag}_sb"
        for p in (outp, logp):
            if p.exists(): p.unlink()
        r = gate(binp, root, "batch", str(inp), "--out", str(outp), "--log", str(logp), "--sandbox", str(sb), "--sock", str(st.ws), "--clf-sock", str(st.cs), "--weights", str(w), "--map-engine", eng)
        if r.returncode: print(tag, "rc", r.returncode, r.stderr[-300:])
    res[tag] = load_out(outp)
a, b, c = res["v16_rust"], res["v16_py"], res["v15"]
dd = [i for i in a if a[i].get("decision") != b[i].get("decision") or a[i].get("layer") != b[i].get("layer")]
print("rust vs python engine decision/layer diffs:", len(dd), dd[:5])
grp = {r["id"]: r["group"].split(":")[0] for r in sel}
t = Counter(); lift = []; new = Counter()
for r in sel:
    i = r["id"]; h16 = not is_allow(a[i]); h15 = not is_allow(c[i])
    t[(grp[i], h15, h16)] += 1
    if h15 and not h16: lift.append((i, grp[i], r["label"], c[i].get("layer")))
for k in sorted(t): print(k, t[k])
print("lifted holds:", len(lift), Counter((g, l) for _, g, l, _ in lift))
print("lifted injected:", [x for x in lift if x[2] == 1])
relax = sum(1 for i in a if a[i].get("relax"))
print("records with relax in out:", relax, "keys:", list(a[next(iter(a))].keys()))
