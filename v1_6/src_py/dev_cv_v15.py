import sys, json, pickle, numpy as np, random
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT/"src_py"))
from map_check import MapCheck, topk_mean
from dev_v15 import pools
mc = MapCheck(ROOT/"models"/"verb_families_v1_3.json", ROOT/"models")
s14, risky, ev, table = pools()
frame = mc.frame
cache = Path("/tmp/vec_v15.pkl")
vecs = pickle.load(open(cache,"rb")) if cache.exists() else {}
def V(words):
    miss = [w for w in words if w not in vecs]
    if miss:
        for w, v in zip(miss, mc.vec(miss)): vecs[w] = v
        pickle.dump(vecs, open(cache,"wb"))
    return np.stack([vecs[w] for w in words])
NEWREG = ["secrets_credentials","system_change","physical_world","post_message"]
def regions_for(seedsets, with_new=True, extra=None):
    R = {r: list(vs) for r, vs in s14.items()}
    for v, rs in seedsets.items():
        for r in rs:
            if r in R: R[r].append(v)
            elif with_new: R.setdefault(r, []).append(v)
            else: pass
    # verbs labelled only with new regions when new regions are off go to nearest-agnostic: skip
    return {r: list(dict.fromkeys(vs)) for r, vs in R.items()}
def scores(X, Rv, A, k, loo_self=None):
    """X: n x d queries; returns margin, best region index"""
    best = np.full(len(X), -9.0); bi = np.zeros(len(X), int)
    names = list(Rv)
    for i, r in enumerate(names):
        S = Rv[r]
        sim = X @ S.T
        if loo_self is not None: sim = np.where(loo_self[r], -9, sim)
        kk = min(k, sim.shape[1]); s = np.sort(sim, axis=1)[:, -kk:].mean(axis=1)
        m = s > best; best[m] = s[m]; bi[m] = i
    sa = X @ A.T
    if loo_self is not None: sa = np.where(np.eye(len(X), dtype=bool) if False else loo_self.get("__anch__", False), -9, sa)
    kk = min(k, A.shape[0]); ben = np.sort(sa, axis=1)[:, -kk:].mean(axis=1)
    return best - ben, bi
def run(with_new, k, folds=5, seed=0, tau_fp=0.04, pools_risky=None):
    rk = pools_risky or risky
    verbs = sorted(rk)
    random.Random(seed).shuffle(verbs)
    A = V(ev)
    full = regions_for({v: rk[v] for v in verbs}, with_new)
    # everyday LOO FP with full seeds: anchors do not contain themselves
    Rv = {r: V(vs) for r, vs in full.items()}
    Xe = A
    eye = np.eye(len(ev), dtype=bool)
    sim_e = Xe @ A.T; sim_e = np.where(eye, -9, sim_e)
    kk = k; ben = np.sort(sim_e, axis=1)[:, -kk:].mean(axis=1)
    best = np.full(len(ev), -9.0)
    for r, S in Rv.items():
        sim = Xe @ S.T
        # an everyday word is never its own seed (disjoint by construction)
        s = np.sort(sim, axis=1)[:, -kk:].mean(axis=1); best = np.maximum(best, s)
    me = best - ben
    return full, Rv, me, A, verbs
def cv_recall(with_new, k, taus, folds=5, seed=0):
    verbs = sorted(risky); random.Random(seed).shuffle(verbs)
    A = V(ev)
    out = {t: 0 for t in taus}; per = {}
    for f in range(folds):
        test = verbs[f::folds]; train = [v for v in verbs if v not in set(test)]
        R = regions_for({v: risky[v] for v in train}, with_new)
        Rv = {r: V(vs) for r, vs in R.items()}
        X = V(test)
        best = np.full(len(test), -9.0)
        for r, S in Rv.items():
            best = np.maximum(best, np.sort(X @ S.T, axis=1)[:, -k:].mean(axis=1))
        ben = np.sort(X @ A.T, axis=1)[:, -k:].mean(axis=1)
        m = best - ben
        for v, mm in zip(test, m): per[v] = mm
        for t in taus: out[t] += int((m >= t).sum())
    return {t: out[t]/len(verbs) for t in taus}, per
if __name__ == "__main__":
    taus = [round(x, 2) for x in np.arange(-0.10, 0.12, 0.01)]
    # v1.4 baseline recall: v1.4 seeds only, on the risky pool
    for with_new in (False, True):
        for k in (2, 3):
            full, Rv, me, A, verbs = run(with_new, k)
            fp = {t: float((me >= t).mean()) for t in taus}
            t_sel = next(t for t in taus if fp[t] <= 0.04)
            rec, per = cv_recall(with_new, k, taus)
            print(f"new_regions={with_new} k={k} regions={len(Rv)} tau_sel={t_sel:+.2f} LOO-FP={fp[t_sel]:.3f} CVrecall@tau={rec[t_sel]:.3f}  (recall@tau-0.02 {rec[taus[taus.index(t_sel)-2]]:.3f})")
    # baseline v1.4: seeds14 only evaluated on pool
    R = {r: list(vs) for r, vs in s14.items()}
    Rv = {r: V(vs) for r, vs in R.items()}; A14 = V(json.load(open(ROOT/"models"/"verbmap_params.json"))["anchors"])
    X = V(sorted(risky)); 
    best = np.max([np.sort(X @ S.T, axis=1)[:, -2:].mean(axis=1) for S in Rv.values()], axis=0)
    ben = np.sort(X @ A14.T, axis=1)[:, -2:].mean(axis=1)
    print("v1.4 as-is on pool recall at tau -0.02:", float(((best-ben) >= -0.02).mean()))
