#!/usr/bin/env python3
"""Dev analysis for the v1.4 map check. Dev data only: dev benign verbs (leave-one-out), v1.3 fan-out words (not seeds), dev unseen risky verbs, clean public pages, dev injections."""
import sys, json, numpy as np
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src_py"))
from map_check import MapCheck
import verbmap_seeds as V
mc = MapCheck(ROOT/"models"/"verb_families_v1_3.json", ROOT/"models")
f = json.load(open(ROOT/"models"/"verb_families_v1_3.json"))
seeds = {v for vs in V.REGIONS.values() for v in vs}
pos_tab = sorted(w for c, e in f["categories"].items() for w in e["tier1"] if w not in seeds and c != "override_rules")
ben = mc.params["anchors"]
sb = np.array([mc.score_phrase(v, exclude_anchor=v)[0] for v in ben])
sp = np.array([mc.score_phrase(v)[0] for v in pos_tab])
su = np.array([mc.score_phrase(v)[0] for v in V.DEV_UNSEEN_RISKY])
pages = []
for fn in ("learning_pool.jsonl", "dev_fp_pages.jsonl"):
    for l in open(ROOT/"data"/fn):
        r = json.loads(l); pages.append(r["text"])
pm = []
nc = 0
for t in pages:
    best = -9
    for variants, why in mc.candidates(t):
        nc += 1
        for ph in variants: best = max(best, mc.score_phrase(ph)[0])
    pm.append(best)
pm = np.array(pm)
inj = [json.loads(l) for l in open(ROOT/"data"/"dev_set.jsonl")]
im = []
for r in inj:
    best = -9
    for variants, why in mc.candidates(r["text"]):
        for ph in variants: best = max(best, mc.score_phrase(ph)[0])
    im.append((r["family"], r["gold"], best))
print("pages", len(pages), "candidates in clean pages", nc, "pages with any candidate", int((pm > -9).sum()))
print("%-6s %-9s %-9s %-9s %-10s" % ("tau", "benignFP", "fan_rec", "uns_rec", "pagesheld"))
for tau in np.arange(-0.10, 0.16, 0.01):
    print("%+.2f  %6.3f   %6.3f   %6.3f   %d" % (tau, (sb >= tau).mean(), (sp >= tau).mean(), (su >= tau).mean(), int((pm >= tau).sum())))
fams = sorted({a for a, b, c in im})
for tau in (0.0, 0.02, 0.04, 0.06):
    print("tau", tau, {fa: "%d/%d" % (sum(1 for a, b, c in im if a == fa and c >= tau), sum(1 for a, b, c in im if a == fa)) for fa in fams})
np.save("/tmp/dev_scores.npy", {"sb": sb, "sp": sp, "su": su, "pm": pm}, allow_pickle=True)
