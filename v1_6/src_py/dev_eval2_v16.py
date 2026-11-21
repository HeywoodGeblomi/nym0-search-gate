#!/usr/bin/env python3
"""Dev comparison of the fixed configurations C0..C3 plus single-fix ablations. Writes out/DEV_CONFIGS_v16.json."""
import sys, json, time
sys.path.insert(0, "/workspace/frontier_pivot/search_gate_v1_6/src_py")
from dev16_lib import *
from classifier_infer import span_text
from collections import defaultdict
D = jl(DATA/"dev_v16.jsonl"); e = Emu()
ABC = jl("/workspace/frontier_pivot/toolcall_gate_v1/data/official_ABC.jsonl")
V15ABC = {r["id"]: r for r in jl("/workspace/frontier_pivot/search_gate_v1_5/out/abc_v15.out.jsonl")}
OLDC = str(MODELS/"classifier_v1_2.json"); NEWC = str(MODELS/"classifier_v1_6.json")
def gkey(r):
    g = r["group"].split(":")[0]
    return g + ("|" + r["split"]) if g in ("pool_clean", "pool_inj", "wp_clean", "wp_inj") else r["group"] if g in ("old", "oldslice") else g
def run(name, cfg, clfp, waiver, abc=True):
    t = time.time(); held = {}
    for r in D: held[r["id"]] = e.hold(r["text"], cfg, clfp, waiver)[0]
    g = defaultdict(lambda: [0, 0])
    for r in D: k = gkey(r); g[k][0] += held[r["id"]]; g[k][1] += 1
    # pool clean by source
    src = defaultdict(lambda: [0, 0])
    for r in D:
        if r["group"].startswith("pool_clean") and r["split"] == "fit": s = r["group"].split(":")[1]; src[s][0] += held[r["id"]]; src[s][1] += 1
    out = {"groups": {k: v for k, v in g.items()}, "pool_clean_fit_by_source": dict(src)}
    if abc:
        lifted = {"A": 0, "B": 0}; c_fh = 0; n = {"A": 0, "B": 0, "C": 0}
        for r in ABC:
            txt = span_text(r); h = e.hold(txt, cfg, clfp, waiver)[0]; k = r["kind"]; n[k] += 1
            v = V15ABC[r["id"]]
            if k == "C": c_fh += h
            elif v.get("layer") in ("classifier", "instruction_check", "meaning_map") and not h: lifted[k] += 1
        out["injecagent_guard"] = {"lifted_A": lifted["A"], "lifted_B": lifted["B"], "C_new_holds_from_workers": c_fh}
    out["_held"] = held
    print("==", name, round(time.time() - t, 1), flush=True)
    for k in sorted(g): print(f"   {k:22s} {g[k][0]:5d}/{g[k][1]:5d} {100*g[k][0]/g[k][1]:5.1f}%")
    print("   pool_clean_fit by source:", {s: f"{a}/{b}" for s, (a, b) in src.items()})
    if abc: print("   injecagent guard:", out["injecagent_guard"], flush=True)
    return out
if __name__ == "__main__":
    R = {}
    plan = [("v15", "v15", OLDC, False), ("C0_fixes", "all", OLDC, False), ("C1_fixes_waiver", "all", OLDC, True), ("C2_fixes_newclf", "all", NEWC, False), ("C3_fixes_waiver_newclf", "all", NEWC, True)]
    for name, cfg, c, w in plan: R[name] = run(name, cfg, c, w)
    json.dump({k: {kk: vv for kk, vv in v.items() if kk != "_held"} for k, v in R.items()}, open(ROOT/"out"/"DEV_CONFIGS_v16.json", "w"), indent=1)
    import pickle; pickle.dump({k: v["_held"] for k, v in R.items()}, open("/tmp/dev_held.pkl", "wb"))
