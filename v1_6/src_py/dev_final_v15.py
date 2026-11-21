#!/usr/bin/env python3
"""Dev estimate for the frozen v1.5 map check: 5-fold cross-validation (5 seeds) over dev risky and everyday verbs with the final settings. A verb is never in the data that scored it.
Reports recall on dev risky verbs and false hold rate on dev everyday verbs for: v1.4 rule alone, probe alone, and the OR (the v1.5 decision without the seed list, which cannot be cross-validated)."""
import sys, json, numpy as np
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT/"src_py"))
from sklearn.linear_model import LogisticRegression
from dev_cv_v15 import mc, risky, ev, s14, V
from map_check15 import MapCheck15
m5 = MapCheck15(ROOT/"models"/"verb_families_v1_3.json", ROOT/"models")
P = json.load(open(ROOT/"models"/"verbmap_v15.json"))["probe"]; thr = P["thr"]
FZ = json.load(open(ROOT/'models'/'verbmap_v15.json'))   # the frozen dev lists actually used for the probe
s14w = sorted({v for vs in s14.values() for v in vs}); rv = sorted({v for vs in FZ['regions_widened'].values() for v in vs} - set(s14w)); evw = list(FZ['everyday'])
G = lambda ws: np.stack([m5.G[m5.gidx[w.split()[0]]] if w.split()[0] in m5.gidx else np.zeros(384) for w in ws])
feat = lambda ws: np.hstack([V(ws), G(ws)])
Xr, Xe, Xs = feat(rv), feat(evw), feat(s14w)
M14r = np.array([mc.score_phrase(w, exclude_anchor=w)[0] for w in rv]); M14e = np.array([mc.score_phrase(w, exclude_anchor=w)[0] for w in evw])
rows = []
for seed in range(5):
    rng = np.random.RandomState(seed); fr = rng.permutation(len(rv)) % 5; fe = rng.permutation(len(evw)) % 5
    sr = np.zeros(len(rv)); se = np.zeros(len(evw))
    for f in range(5):
        m = LogisticRegression(C=1.0, max_iter=5000).fit(np.vstack([Xr[fr != f], Xs, Xe[fe != f]]), np.r_[np.ones((fr != f).sum() + len(s14w)), np.zeros((fe != f).sum())])
        sr[fr == f] = m.decision_function(Xr[fr == f]); se[fe == f] = m.decision_function(Xe[fe == f])
    rows.append(((M14r >= m5.tau).mean(), (M14e >= m5.tau).mean(), (sr >= thr).mean(), (se >= thr).mean(), ((sr >= thr) | (M14r >= m5.tau)).mean(), ((se >= thr) | (M14e >= m5.tau)).mean()))
a = np.mean(rows, axis=0)
out = {"n_risky": len(rv), "n_everyday": len(evw), "v14_rule_alone": {"recall": a[0], "false_hold": a[1]}, "probe_alone": {"recall": a[2], "false_hold": a[3]}, "v15_map_without_seedlist": {"recall": a[4], "false_hold": a[5]},
       "note": "cross-validated on dev verbs only; the seed list (422 verbs) is in-sample for those verbs and cannot be estimated this way; real held-out recall is measured only on the independent test set"}
Path(ROOT/"out"/"DEV_SUMMARY_v15.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
