import sys, numpy as np
sys.path.insert(0,'.')
from dev_cv_v15 import *
from sklearn.linear_model import LogisticRegression
rv = sorted(risky); evw = list(ev); s14w = sorted({v for vs in s14.values() for v in vs})
Xr = V(rv); Xe = V(evw); Xs = V(s14w)
def oof(C, with_new, k, folds=5, seed=0):
    rng = np.random.RandomState(seed)
    fr = rng.permutation(len(rv)) % folds; fe = rng.permutation(len(evw)) % folds
    pr = np.zeros(len(rv)); pe = np.zeros(len(evw)); mr = np.zeros(len(rv)); me = np.zeros(len(evw))
    for f in range(folds):
        Xtr = np.vstack([Xr[fr != f], Xs, Xe[fe != f]])
        y = np.r_[np.ones((fr != f).sum() + len(s14w)), np.zeros((fe != f).sum())]
        m = LogisticRegression(C=C, max_iter=3000).fit(Xtr, y)
        pr[fr == f] = m.decision_function(Xr[fr == f]); pe[fe == f] = m.decision_function(Xe[fe == f])
        trainv = [v for v, g in zip(rv, fr) if g != f]
        R = regions_for({v: risky[v] for v in trainv}, with_new); Rv = {r: V(vs) for r, vs in R.items()}
        A = Xe[fe != f]
        for X, out, msk in ((Xr, mr, fr == f), (Xe, me, fe == f)):
            Q = X[msk]
            best = np.max([np.sort(Q @ S.T, axis=1)[:, -k:].mean(axis=1) for S in Rv.values()], axis=0)
            ben = np.sort(Q @ A.T, axis=1)[:, -k:].mean(axis=1)
            out[msk] = best - ben
    return pr, pe, mr, me
for with_new in (False, True):
  for k in (2, 3):
    pr, pe, mr, me = oof(1.0, with_new, k)
    res = []
    for budget in (0.03, 0.04):
        best = (0, None)
        for fa in np.linspace(0, budget, 9):
            fb = budget - fa
            tp = np.sort(pe)[::-1][int(fa * len(pe))] if fa > 0 else 99
            tm = np.sort(me)[::-1][int(fb * len(me))] if fb > 0 else 99
            hold_e = (pe > tp) | (me > tm); fp = hold_e.mean()
            if fp > budget + 0.003: continue
            rec = ((pr > tp) | (mr > tm)).mean()
            if rec > best[0]: best = (rec, (round(fa, 4), round(float(tp), 2), round(float(tm), 3), round(fp, 3)))
        res.append((budget, round(best[0], 3), best[1]))
    print("new", with_new, "k", k, res)
