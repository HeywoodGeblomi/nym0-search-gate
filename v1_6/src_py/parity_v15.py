#!/usr/bin/env python3
"""Rust / Python parity for the v1.5 map check. Input: a list of orders (each a list of phrase variants). Python reference = MapCheck15 (ONNX Runtime). Rust = nym0asgate mapscore.
Compares the hold decision, the rule and the phrase for every order, and reports the largest score difference and the smallest distance of any score to its threshold.
Usage: parity_v15.py OUT.json [--set NAME FILE ...]; the default orders: every lexicon verb, every dev verb, particle and light-verb phrases, and every order the clause finder finds in the dev files."""
import sys, json, subprocess, itertools
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT/"src_py"))
from map_check15 import MapCheck15
mc = MapCheck15(ROOT/"models"/"verb_families_v1_3.json", ROOT/"models")
BIN = ROOT/"front"/"target"/"release"/"nym0asgate"
def py_decide(variants):
    for ph in variants:
        if ph in mc.seedlist: return {"hold": True, "rule": "list", "phrase": ph, "m14": None, "probe": None}
    b14 = None; bp = None
    for ph in variants:
        x = mc.vec([ph])[0]; m, reg, _, _ = mc.score_phrase(ph); p = mc.probe_score(ph, x)
        if b14 is None or m > b14[0]: b14 = (m, ph)
        if bp is None or p > bp[0]: bp = (p, ph)
    if b14[0] >= mc.tau: return {"hold": True, "rule": "margin", "phrase": b14[1], "m14": b14[0], "probe": bp[0]}
    if bp[0] >= mc.thr: return {"hold": True, "rule": "probe", "phrase": bp[1], "m14": b14[0], "probe": bp[0]}
    return {"hold": False, "rule": "", "phrase": "", "m14": b14[0], "probe": bp[0]}
def rust_decide(orders):
    p = subprocess.run([str(BIN), "mapscore", "--root", str(ROOT)], input="\n".join("|".join(o) for o in orders), capture_output=True, text=True)
    if p.returncode: raise SystemExit("rust failed: " + p.stderr[:500])
    return [json.loads(l) for l in p.stdout.splitlines()]
def compare(name, orders):
    orders = [o for o in orders if o]
    R = rust_decide(orders); mism = []; maxd_m = 0.0; maxd_p = 0.0; mind = 9.0
    for o, r in zip(orders, R):
        py = py_decide(o)
        if "error" in r or py["hold"] != r["hold"] or py["rule"] != r["rule"] or py["phrase"] != r["phrase"]: mism.append({"order": o, "py": py, "rust": r})
        if py["m14"] is not None and "error" not in r:
            maxd_m = max(maxd_m, abs(py["m14"] - r["m14"])); maxd_p = max(maxd_p, abs(py["probe"] - r["probe"]))
            mind = min(mind, abs(py["m14"] - mc.tau), abs(py["probe"] - mc.thr))
    return {"set": name, "orders": len(orders), "held_python": sum(py_decide(o)["hold"] for o in orders) if False else None, "mismatches": len(mism), "mismatch_examples": mism[:10],
            "max_abs_diff_margin": maxd_m, "max_abs_diff_probe": maxd_p, "min_distance_to_threshold": mind, "rust_held": sum(1 for r in R if r.get("hold"))}
def dev_orders():
    out = {}
    lex = sorted(w for w in mc.lex if w.isalpha()); out["lexicon_verbs"] = [[w] for w in lex]
    import verbmap_seeds_v15 as W, benign_v15 as B
    d = json.loads((ROOT/"models"/"verbmap_v15.json").read_text())
    dv = sorted(set(d["everyday"]) | {v for vs in d["regions_widened"].values() for v in vs})
    out["dev_verbs_and_phrases"] = [[w] for w in dv]
    phr = []
    for w in ["set","turn","switch","hand","pass","sign","log","call","make","give","place","pay","file","lodge","put","send","run","take","get","do","issue","perform","check","wipe","clean","write","cut","look"]:
        for part in ["aside","up","down","off","out","over","away","back","in","on","along"]: phr.append([w, w + " " + part])
    for w in ["make","give","take","place","pay","put","issue","file","lodge","perform","run","send","do","get"]:
        for n in ["call","payment","order","transfer","copy","request","note","list","walk","wish","claim","report","start","visit","move","stop"]:
            for pr in ["to","of","for","on","with","at","from","into"]:
                phr.append([w, f"{w} a {n}", f"{w} a {n} {pr}"])
    out["particle_and_light_verb_phrases"] = phr
    fam = ROOT/"models"/"verb_families_v1_3.json"
    texts = []
    for fn in ("dev_set.jsonl",):
        for l in open(ROOT/"data"/fn): r = json.loads(l); texts.append(r["text"])
    for fn in ("learning_pool", "dev_fp_pages"):
        for l in open(ROOT/"data"/f"{fn}.jsonl"): texts.append(json.loads(l)["text"])
    for fn in ("dev2_phrasings.txt", "dev_neg2.txt", "dev_override_phrasings.txt"):
        for l in open(ROOT/"data"/fn):
            l = l.rstrip("\n"); l = l.encode().decode("unicode_escape") if "\\u" in l else l
            if l.strip(): texts.append(l)
    out["orders_found_in_dev_files"] = [v for t in texts for v, why in mc.candidates(t)]
    return out
if __name__ == "__main__":
    res = []
    for name, orders in dev_orders().items(): res.append(compare(name, orders)); print(res[-1]["set"], res[-1]["orders"], "mismatches", res[-1]["mismatches"], "maxdiff", res[-1]["max_abs_diff_margin"], res[-1]["max_abs_diff_probe"], "min dist", res[-1]["min_distance_to_threshold"], flush=True)
    Path(sys.argv[1]).write_text(json.dumps(res, indent=1))
