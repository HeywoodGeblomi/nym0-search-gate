import sys, numpy as np, random
sys.path.insert(0,'.')
from dev_cv_v15 import *
from sklearn.linear_model import LogisticRegression
rv = sorted(risky); evw = list(ev); s14w = sorted({v for vs in s14.values() for v in vs})
Xr = V(rv); Xe = V(evw); Xs = V(s14w)
def cv(C, cw, folds=5, seed=0):
    rng = np.random.RandomState(seed)
    fr = rng.permutation(len(rv)) % folds; fe = rng.permutation(len(evw)) % folds
    sr = np.zeros(len(rv)); se = np.zeros(len(evw))
    for f in range(folds):
        Xtr = np.vstack([Xr[fr != f], Xs, Xe[fe != f]])
        y = np.r_[np.ones((fr != f).sum() + len(s14w)), np.zeros((fe != f).sum())]
        m = LogisticRegression(C=C, class_weight=cw, max_iter=2000).fit(Xtr, y)
        sr[fr == f] = m.decision_function(Xr[fr == f]); se[fe == f] = m.decision_function(Xe[fe == f])
    return sr, se
for C in (1, 3, 10, 30, 100):
    for cw in (None, "balanced"):
        sr, se = cv(C, cw)
        out = []
        for fp in (0.02, 0.04):
            thr = np.sort(se)[::-1][int(fp*len(se))]
            out.append(f"FP{fp:.2f}: recall {np.mean(sr > thr):.3f}")
        print(C, cw, out)
