#!/usr/bin/env python3
import sys, json, time
from collections import defaultdict, Counter
sys.path.insert(0, "/workspace/frontier_pivot/search_gate_v1_6/src_py")
from dev16_lib import *
D = jl(DATA/"dev_v16.jsonl")
def summarize(e, cfg, waiver, clfpath=None, tag=""):
    rows = {}
    for r in D:
        h, layer, sc = e.hold(r["text"], cfg, clfpath, waiver); rows[r["id"]] = (h, layer)
    return rows
def table(rows, label):
    g = defaultdict(lambda: [0, 0])
    for r in D:
        h, layer = rows[r["id"]]; k = r["group"] if not r["group"].startswith(("pool_clean", "pool_inj", "v15_clean")) else r["group"]
        key = (r["group"].split(":")[0] + ("|" + r["split"] if r["split"] in ("fit", "val") else "")) if r["group"].split(":")[0] in ("pool_clean", "pool_inj", "wp_clean", "wp_inj") else r["group"].split(":")[0] if r["group"].split(":")[0] not in ("old", "oldslice", "dev_set") else r["group"]
        g[key][0] += h; g[key][1] += 1
    return g
if __name__ == "__main__":
    e = Emu(); res = {}
    for name, cfg, w in [("v15", "v15", False), ("all_nowaiver", "all", False), ("all_waiver", "all", True), ("v15_waiver", "v15", True)]:
        t = time.time(); rows = summarize(e, cfg, w); res[name] = rows
        g = table(rows, name); print("==", name, round(time.time() - t, 1))
        for k in sorted(g): print(f"  {k:28s} {g[k][0]:5d}/{g[k][1]:5d} {100*g[k][0]/g[k][1]:5.1f}%")
