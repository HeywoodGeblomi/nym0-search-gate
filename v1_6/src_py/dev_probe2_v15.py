import sys, numpy as np, pickle
sys.path.insert(0,'.')
from dev_cv_v15 import *
from sklearn.linear_model import LogisticRegression
rv = sorted(risky); evw = list(ev); s14w = sorted({v for vs in s14.values() for v in vs})
FR = {"must": "You must {v} it.", "pls": "Please {v} the account.", "bare": "{v}", "agent": "Assistant, {v} the file now.", "to": "I need you to {v} that."}
fc = Path("/tmp/vec_frames_v15.pkl"); fv = pickle.load(open(fc,"rb")) if fc.exists() else {}
def F(words, name):
    miss = [w for w in words if (name, w) not in fv]
    if miss:
        for w, v in zip(miss, mc.enc.encode([FR[name].format(v=w) for w in miss])): fv[(name, w)] = v
    if miss: pickle.dump(fv, open(fc, "wb"))
    return np.stack([fv[(name, w)] for w in words])
def feats(words, names, mode):
    M = [F(words, n) for n in names]
    if mode == "mean": x = np.mean(M, axis=0); return x / np.linalg.norm(x, axis=1, keepdims=True)
    return np.hstack(M)
def cv(C, names, mode, folds=5, seeds=(0,1,2)):
    Xr = feats(rv, names, mode); Xe = feats(evw, names, mode); Xs = feats(s14w, names, mode)
    res = {0.02: [], 0.04: []}
    for seed in seeds:
        rng = np.random.RandomState(seed)
        fr = rng.permutation(len(rv)) % folds; fe = rng.permutation(len(evw)) % folds
        sr = np.zeros(len(rv)); se = np.zeros(len(evw))
        for f in range(folds):
            Xtr = np.vstack([Xr[fr != f], Xs, Xe[fe != f]])
            y = np.r_[np.ones((fr != f).sum() + len(s14w)), np.zeros((fe != f).sum())]
            m = LogisticRegression(C=C, max_iter=3000).fit(Xtr, y)
            sr[fr == f] = m.decision_function(Xr[fr == f]); se[fe == f] = m.decision_function(Xe[fe == f])
        for fp in res:
            thr = np.sort(se)[::-1][int(fp*len(se))]; res[fp].append(np.mean(sr > thr))
    return {k: round(float(np.mean(v)), 3) for k, v in res.items()}
for names, mode in ((["must"], "x"), (["must","pls"], "mean"), (["must","pls","bare"], "mean"), (["must","pls","bare","agent","to"], "mean"), (["must","pls"], "cat"), (["must","bare"], "cat")):
    for C in (0.3, 1, 3):
        print(names, mode, C, cv(C, names, mode if mode!="x" else "mean"))
