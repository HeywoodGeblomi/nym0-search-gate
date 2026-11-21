#!/usr/bin/env python3
"""Dev harness for v1.5 (dev data only). Builds the pools, caches vectors, runs cross-validation of seed widening and picks tau by the PREREG rule."""
import sys, json, pickle, itertools, numpy as np
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT/"src_py"))
from map_check import MapCheck, topk_mean
import verbmap_seeds_v15 as W, benign_v15 as B, verbmap_seeds as V14
OBJ_WORDS = {"unlock the door","open the valve","add user","give access","pull the plug on","get in touch with","pay for","opt out of","get rid of","reach out","call up","message back"}
def clean(vs): return [v for v in dict.fromkeys(vs) if v not in OBJ_WORDS]

def pools():
    seeds14 = W.V14_REGIONS
    s14 = {v for vs in seeds14.values() for v in vs}
    risky = {}   # verb -> region(s)
    for d in (W.PUBLISHED_V14, W.NEW_RISKY):
        for r, vs in d.items():
            for v in clean(vs):
                if v not in s14: risky.setdefault(v, set()).add(r)
    from wn_aug_v15 import build as wn_build
    wa = wn_build()
    for v in W.WN_PICK:
        if v not in s14 and v in wa:
            for r in wa[v]: risky.setdefault(v, set()).add(r)
    for v in W.V14_SLICE_UNSEEN + W.DEV_UNSEEN_RISKY:
        if v not in s14 and v not in risky: risky[v] = {"send_share"}  # fallback label, only if unlisted
    fam = json.load(open(ROOT/"models"/"verb_families_v1_3.json"))
    table = {w for c, e in fam["categories"].items() for k in ("tier1", "tier2") for w in e.get(k, [])}
    wn = json.load(open("/tmp/wn_everyday_cand.json"))
    from nltk.corpus import wordnet as wnet
    doms = ['verb.body','verb.consumption','verb.emotion','verb.motion','verb.perception','verb.weather','verb.creation','verb.cognition']
    cnt = {}
    for ss in wnet.all_synsets('v'):
        if ss.lexname() not in doms: continue
        for l in ss.lemmas():
            n = l.name()
            if n in set(wn) and ss in wnet.synsets(n, 'v')[:2]: cnt[n] = cnt.get(n, 0) + l.count()
    wn_ev = [w for w, k in sorted(cnt.items()) if k >= 3 and w not in B.WN_REMOVE]
    ev = []
    allrisk = set(risky) | s14 | set(W.V14_SLICE_UNSEEN)
    for w in list(MapCheck_anchors14()) + V14.dev_benign(table) + B.HAND_BENIGN + wn_ev + W.V14_SLICE_EVERYDAY:
        if w not in allrisk and w not in ev: ev.append(w)
    return seeds14, risky, ev, table

_a14 = None
def MapCheck_anchors14():
    return json.load(open(ROOT/"models"/"verbmap_params.json"))["anchors"]

if __name__ == "__main__":
    s14, risky, ev, table = pools()
    print("risky pool", len(risky), "everyday", len(ev))
