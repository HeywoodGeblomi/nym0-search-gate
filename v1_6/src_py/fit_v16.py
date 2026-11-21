#!/usr/bin/env python3
"""Refit the classifier (candidate C2/C3 for v1.6): v1.2 recipe plus the new command-heavy harmless pool as clean pages and planted injections on those pages.
Dev only until frozen. Fit pages only; validation pages (30 percent by URL hash) are used for the threshold and an out-of-sample report."""
import json, hashlib, random, sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion
from sklearn.linear_model import LogisticRegression
ROOT = Path(__file__).resolve().parents[1]; DATA = ROOT/"data"; MODELS = ROOT/"models"
sys.path.insert(0, str(ROOT/"src_py"))
from classifier_infer import Classifier, span_text
import inj_gen_v16 as G
from dev16_lib import split_of
CL1 = Path("/workspace/frontier_pivot/classifier_layer_v1/data")
SEED = 160601; rng = random.Random(SEED)
def jl(p): return [json.loads(l) for l in open(p) if l.strip()]
T = json.load(open(DATA/"LEARN_TEMPLATES.json"))["families"]; fams = list(T)
def plant_v12(text, i):
    f = fams[i % len(fams)]; t = rng.choice(T[f]); return text.rstrip() + " " + t
pages = []   # (text, url)
for r in jl(DATA/"learning_pool.jsonl"): pages.append((r["text"], r["url"], "wp"))
for r in jl(DATA/"dev_fp_pages.jsonl"): pages.append((r["text"], r["url"], "wp"))
for r in jl(DATA/"pool_v16.jsonl"): pages.append((r["text"], r["url"], "pool:" + r["source"]))
for r in jl(DATA/"topical_v16.jsonl"): pages.append((r["text"], r["url"], "topical"))
rows, vrows = [], []
for k, (t, u, src) in enumerate(pages):
    sp = split_of(u); tgt = rows if sp == "fit" else vrows
    tgt.append((t, 0, "real_clean:" + src))
    if rng.random() < 0.8 or sp == "val":
        pt = plant_v12(t, k) if rng.random() < 0.4 else G.plant(t, rng)[0]
        tgt.append((pt, 1, "real_planted"))
for r in jl(CL1/"learn.jsonl"): rows.append((span_text(r), int(r["label"]), "synthetic"))
for r in jl(CL1/"val.jsonl"): vrows.append((span_text(r), int(r["label"]), "synthetic"))
Xtr = [t for t, _, _ in rows]; ytr = np.array([l for _, l, _ in rows])
Xva = [t for t, _, _ in vrows]; yva = np.array([l for _, l, _ in vrows]); kva = np.array([k for _, _, k in vrows])
word = TfidfVectorizer(ngram_range=(1, 2), min_df=2, lowercase=True, token_pattern=r"(?u)\b\w+\b", max_features=8000, norm="l2", use_idf=True, smooth_idf=True, sublinear_tf=False)
char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, lowercase=True, max_features=8000, norm="l2", use_idf=True, smooth_idf=True, sublinear_tf=False)
union = FeatureUnion([("word", word), ("char", char)]); M = union.fit_transform(Xtr)
clf = LogisticRegression(penalty="l2", C=1.0, class_weight="balanced", solver="liblinear", max_iter=300, random_state=SEED).fit(M, ytr)
proba = clf.predict_proba(union.transform(Xva))[:, 1]
real_neg = np.array([k.startswith("real_clean") for k in kva]); pos = yva == 1
def m(thr):
    pred = proba >= thr
    return {"threshold": thr, "real_clean_false_hold_rate": float(pred[real_neg].mean()), "synthetic_neg_false_hold_rate": float(pred[(kva == "synthetic") & (yva == 0)].mean()),
            "recall_all_pos": float(pred[pos].mean()), "recall_real_planted": float(pred[kva == "real_planted"].mean()), "recall_synthetic_pos": float(pred[(kva == "synthetic") & pos].mean())}
cands = [m(i / 100) for i in range(50, 96)]
ok = [c for c in cands if c["real_clean_false_hold_rate"] <= 0.03]
if ok: ok.sort(key=lambda c: (c["recall_all_pos"], c["threshold"]), reverse=True); ch = ok[0]; dev = None
else: ch = m(0.95); dev = "no threshold met the 3.00% real-clean false-hold cap; locked 0.95"
bysrc = {}
for s in sorted({k for k in kva if k.startswith("real_clean")}):
    msk = kva == s; bysrc[s] = {"n": int(msk.sum()), "false_hold_at_chosen": float((proba[msk] >= ch["threshold"]).mean())}
def exp(v): return {"ngram_range": list(v.ngram_range), "analyzer": v.analyzer, "min_df": v.min_df, "max_features": v.max_features, "vocab": {k: int(x) for k, x in v.vocabulary_.items()}, "idf": [float(x) for x in v.idf_], "lowercase": True, "norm": "l2", "smooth_idf": True, "sublinear_tf": False}
coef = clf.coef_.ravel().astype(float)
now = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")
gold = [{"text": t, "sklearn_score": float(clf.predict_proba(union.transform([t]))[0, 1])} for t in Xtr[:5] + Xtr[-5:] + Xva[:5]]
art = {"version": "classifier_v1_6", "model_class": "logistic_regression_l2_tfidf", "seed": SEED, "frozen_at": now, "timezone": "America/New_York", "n_features": int(coef.shape[0]), "word": exp(union.transformer_list[0][1]), "char": exp(union.transformer_list[1][1]),
       "coef": [float(x) for x in coef], "intercept": float(clf.intercept_[0]), "threshold": float(ch["threshold"]), "validation_choice": ch, "validation_by_source": bysrc, "construction_deviation": dev,
       "learn_size": {"n": len(rows), "real_clean_neg": int(sum(1 for r in rows if r[2].startswith("real_clean"))), "real_planted_pos": int(sum(1 for r in rows if r[2] == "real_planted"))}, "val_size": {"n": len(vrows)},
       "note": "Learned on real clean public wiki text (Wikipedia, Wikibooks, Wikivoyage, Wikisource), synthetic injections planted on those pages and the v1.2 synthetic rows. Threshold chosen on validation pages only. No test page, InjecAgent row, human label or sealed data used."}
path = MODELS/"classifier_v1_6.json"; path.write_text(json.dumps(art) + "\n")
inf = Classifier.load(path); mx = max(abs(inf.score(g["text"]) - g["sklearn_score"]) for g in gold); assert mx < 1e-8, mx
print(json.dumps({"learn": art["learn_size"], "val": art["val_size"], "chosen": ch, "by_source": bysrc, "kept": len(ok)}, indent=1))
