import sys, numpy as np, pickle
sys.path.insert(0,'.')
from dev_cv_v15 import *
from nltk.corpus import wordnet as wn
from sklearn.linear_model import LogisticRegression
rv = sorted(risky); evw = list(ev); s14w = sorted({v for vs in s14.values() for v in vs})
gc = Path("/tmp/gloss_v15.pkl"); G = pickle.load(open(gc,"rb")) if gc.exists() else {}
def gloss(w, n=2):
    ss = wn.synsets(w.split()[0] if " " not in w else w.replace(" ","_"), 'v')[:n]
    if not ss and " " in w: ss = wn.synsets(w.split()[0], 'v')[:n]
    return [f"{w}: {s.definition()}" for s in ss]
def GV(words, n):
    out = []
    for w in words:
        key = (w, n)
        if key not in G:
            t = gloss(w, n)
            G[key] = np.mean(mc.enc.encode(t), axis=0) if t else np.zeros(384)
            nn = np.linalg.norm(G[key]); G[key] = G[key] / nn if nn > 0 else G[key]
        out.append(G[key])
    pickle.dump(G, open(gc,"wb")); return np.stack(out)
def cv(C, n, mode, folds=5, seeds=(0,1,2)):
    def feat(ws):
        a = V(ws)
        if mode == "verb": return a
        g = GV(ws, n)
        return np.hstack([a, g]) if mode == "cat" else g
    Xr, Xe, Xs = feat(rv), feat(evw), feat(s14w)
    res = {0.02: [], 0.04: []}
    for seed in seeds:
        rng = np.random.RandomState(seed)
        fr = rng.permutation(len(rv)) % folds; fe = rng.permutation(len(evw)) % folds
        sr = np.zeros(len(rv)); se = np.zeros(len(evw))
        for f in range(folds):
            Xtr = np.vstack([Xr[fr != f], Xs, Xe[fe != f]]); y = np.r_[np.ones((fr != f).sum() + len(s14w)), np.zeros((fe != f).sum())]
            m = LogisticRegression(C=C, max_iter=3000).fit(Xtr, y)
            sr[fr == f] = m.decision_function(Xr[fr == f]); se[fe == f] = m.decision_function(Xe[fe == f])
        for fp in res:
            thr = np.sort(se)[::-1][int(fp*len(se))]; res[fp].append(np.mean(sr > thr))
    return {k: round(float(np.mean(v)), 3) for k, v in res.items()}
for mode, n in (("verb", 1), ("gloss", 1), ("gloss", 2), ("cat", 1), ("cat", 2)):
    for C in (1, 3):
        print(mode, n, C, cv(C, n, mode), flush=True)
