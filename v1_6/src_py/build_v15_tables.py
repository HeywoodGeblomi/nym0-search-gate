#!/usr/bin/env python3
"""Build the v1.5 map tables from dev data only: WordNet gloss vectors for every lexicon verb, the linear probe on [verb vector, gloss vector],
its threshold from out-of-fold dev scores, and the widened region lists. Writes models/verb_gloss_f32.bin, models/verb_gloss_index.txt, models/verbmap_v15.json."""
import sys, json, hashlib, numpy as np
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT/"src_py"))
from nltk.corpus import wordnet as wn
from sklearn.linear_model import LogisticRegression
from dev_cv_v15 import mc, risky, ev, s14, V
from gloss_v15 import gloss_texts
LIST_EXCLUDE = set("""drive board tow steer pilot empty blank drop strike tip spread hand brief signal approach flag rate tag comment review mention raise lower adjust swap toggle source pipe evaluate eval perform commence boot release issue supply route time kick off start up spin up power on set up turn on turn off carry out""".split()) | {"kick off","start up","spin up","power on","set up","turn on","turn off","carry out"}
LEX = sorted(set(open(ROOT/"models"/"verb_lexicon_all.txt").read().split()))
def gloss_table():
    texts = []; spans = []
    for w in LEX:
        t = gloss_texts(w); spans.append((len(texts), len(texts) + len(t))); texts += t
    E = mc.enc.encode(texts) if texts else np.zeros((0, 384))
    G = np.zeros((len(LEX), 384))
    for i, (a, b) in enumerate(spans):
        if b > a:
            g = E[a:b].mean(axis=0); G[i] = g / np.linalg.norm(g)
    return G
if __name__ == "__main__":
    G = gloss_table().astype(np.float32)
    (ROOT/"models"/"verb_gloss_f32.bin").write_bytes(G.tobytes())
    (ROOT/"models"/"verb_gloss_index.txt").write_text("\n".join(LEX) + "\n")
    idx = {w: i for i, w in enumerate(LEX)}
    def GV(words): return np.stack([G[idx[w.split()[0]]].astype(np.float64) if w.split()[0] in idx else np.zeros(384) for w in words])
    rv = sorted(risky); evw = list(ev); s14w = sorted({v for vs in s14.values() for v in vs})
    def feat(ws): return np.hstack([V(ws), GV(ws)])
    Xr, Xe, Xs = feat(rv), feat(evw), feat(s14w)
    C = 1.0
    oofe, oofr = [], []
    thrs = []
    for seed in range(5):
        rng = np.random.RandomState(seed); fr = rng.permutation(len(rv)) % 5; fe = rng.permutation(len(evw)) % 5
        sr = np.zeros(len(rv)); se = np.zeros(len(evw))
        for f in range(5):
            m = LogisticRegression(C=C, max_iter=5000).fit(np.vstack([Xr[fr != f], Xs, Xe[fe != f]]), np.r_[np.ones((fr != f).sum() + len(s14w)), np.zeros((fe != f).sum())])
            sr[fr == f] = m.decision_function(Xr[fr == f]); se[fe == f] = m.decision_function(Xe[fe == f])
        oofe.append(se); oofr.append(sr)
    # threshold: lowest value on a 0.05 grid such that the mean out-of-fold false-hold rate on everyday verbs is at most 4 percent
    grid = np.round(np.arange(-2, 4.01, 0.05), 2)
    fpg = {t: float(np.mean([(se >= t).mean() for se in oofe])) for t in grid}
    thr = next(t for t in grid if fpg[t] <= 0.04)
    rec = float(np.mean([(sr >= thr).mean() for sr in oofr]))
    m = LogisticRegression(C=C, max_iter=5000).fit(np.vstack([Xr, Xs, Xe]), np.r_[np.ones(len(rv) + len(s14w)), np.zeros(len(evw))])
    w = m.coef_[0]; b = float(m.intercept_[0])
    out = {"version": "v1.5", "frame": mc.frame, "probe": {"C": C, "weights_verb": [float(x) for x in w[:384]], "weights_gloss": [float(x) for x in w[384:]], "bias": b, "thr": float(thr),
           "gloss_senses": 2, "gloss_text": "{w}: {definition}", "gloss_table": "verb_gloss_f32.bin", "gloss_index": "verb_gloss_index.txt"},
           "rule": "HOLD if v1.4 margin >= tau (unchanged, verbmap_params.json) OR probe score (w_v . verb_vec + w_g . gloss_vec + bias) >= thr, any variant of any found order",
           "dev": {"n_risky": len(rv), "n_seed14": len(s14w), "n_everyday": len(evw), "oof_everyday_false_hold_rate_at_thr": fpg[thr], "oof_risky_recall_at_thr": rec, "thr_rule": "lowest value on a 0.05 grid with mean out-of-fold false hold rate on everyday verbs <= 0.04 (5 seeds x 5 folds)"},
           "regions_widened": {r: sorted(set(vs)) for r, vs in __import__("dev_cv_v15").regions_for({v: risky[v] for v in rv}, True).items()}, "everyday": evw,
           "seedlist": sorted((set(rv) | set(s14w)) - LIST_EXCLUDE), "seedlist_excluded_as_ambiguous": sorted(LIST_EXCLUDE & (set(rv) | set(s14w)))}
    (ROOT/"models"/"verbmap_v15.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out["dev"], indent=1), "thr", thr)
