#!/usr/bin/env python3
"""Step 3b: build learning/validation sets from the locked learning pool, fit, choose threshold on validation only, freeze."""
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
CL1 = Path("/workspace/frontier_pivot/classifier_layer_v1/data")
SEED = 120201
rng = random.Random(SEED)
def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jl(p): return [json.loads(l) for l in open(p) if l.strip()]
pool = jl(DATA/"learning_pool.jsonl")
T = json.load(open(DATA/"LEARN_TEMPLATES.json"))["families"]
fams = list(T)
def plant(text, i):
    f = fams[i % len(fams)]; t = rng.choice(T[f])
    sep = "" if t.startswith(("<","[")) else " "
    return text.rstrip() + " " + t if sep else text.rstrip() + " " + t, f
val_pages = [r for r in pool if int(hashlib.sha256(r["url"].encode()).hexdigest(), 16) % 100 < 16]
fit_pages = [r for r in pool if r not in val_pages]
rows = []  # (text, label, kind)
for k, r in enumerate(fit_pages):
    rows.append((r["text"], 0, "real_clean"))
    if rng.random() < 0.7:
        t, f = plant(r["text"], k); rows.append((t, 1, "real_planted"))
for r in jl(CL1/"learn.jsonl"):
    rows.append((span_text(r), int(r["label"]), "synthetic"))
vrows = []
for k, r in enumerate(val_pages):
    vrows.append((r["text"], 0, "real_clean"))
    t, f = plant(r["text"], k); vrows.append((t, 1, "real_planted"))
for r in jl(CL1/"val.jsonl"):
    vrows.append((span_text(r), int(r["label"]), "synthetic"))
Xtr = [t for t,_,_ in rows]; ytr = np.array([l for _,l,_ in rows])
Xva = [t for t,_,_ in vrows]; yva = np.array([l for _,l,_ in vrows]); kva = np.array([k for _,_,k in vrows])
word = TfidfVectorizer(ngram_range=(1,2), min_df=2, lowercase=True, token_pattern=r"(?u)\b\w+\b", max_features=8000, norm="l2", use_idf=True, smooth_idf=True, sublinear_tf=False)
char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5), min_df=2, lowercase=True, max_features=8000, norm="l2", use_idf=True, smooth_idf=True, sublinear_tf=False)
union = FeatureUnion([("word", word), ("char", char)])
M = union.fit_transform(Xtr)
clf = LogisticRegression(penalty="l2", C=1.0, class_weight="balanced", solver="liblinear", max_iter=200, random_state=SEED).fit(M, ytr)
proba = clf.predict_proba(union.transform(Xva))[:, 1]
def m(thr):
    pred = proba >= thr
    real_neg = (kva == "real_clean"); pos = (yva == 1)
    return {"threshold": thr,
            "real_clean_false_hold_rate": float(pred[real_neg].mean()),
            "synthetic_neg_false_hold_rate": float(pred[(kva == "synthetic") & (yva == 0)].mean()),
            "recall_all_pos": float(pred[pos].mean()),
            "recall_real_planted": float(pred[kva == "real_planted"].mean()),
            "recall_synthetic_pos": float(pred[(kva == "synthetic") & pos].mean())}
cands = [m(i/100) for i in range(50, 96)]
ok = [c for c in cands if c["real_clean_false_hold_rate"] <= 0.03]
dev = None
if ok:
    ok.sort(key=lambda c: (c["recall_all_pos"], c["threshold"]), reverse=True); ch = ok[0]
else:
    ch = m(0.95); dev = "no threshold met the 3.00% real-clean false-hold cap; locked 0.95 per prereg"
def exp(v): return {"ngram_range": list(v.ngram_range), "analyzer": v.analyzer, "min_df": v.min_df, "max_features": v.max_features,
                    "vocab": {k: int(x) for k, x in v.vocabulary_.items()}, "idf": [float(x) for x in v.idf_], "lowercase": True, "norm": "l2", "smooth_idf": True, "sublinear_tf": False}
coef = clf.coef_.ravel().astype(float)
now = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")
gold = []
for t in Xtr[:5] + Xtr[-5:] + Xva[:5] + [r["text"] for r in val_pages[:10]]:
    gold.append({"text": t, "sklearn_score": float(clf.predict_proba(union.transform([t]))[0, 1])})
art = {"version": "classifier_v1_2", "model_class": "logistic_regression_l2_tfidf", "seed": SEED, "frozen_at": now, "timezone": "America/New_York",
       "n_features": int(coef.shape[0]), "word": exp(union.transformer_list[0][1]), "char": exp(union.transformer_list[1][1]),
       "coef": [float(x) for x in coef], "intercept": float(clf.intercept_[0]), "threshold": float(ch["threshold"]), "validation_choice": ch,
       "validation_candidates_kept": len(ok), "construction_deviation": dev,
       "learn_size": {"n": len(rows), "real_clean_neg": int(sum(1 for r in rows if r[2]=="real_clean")), "real_planted_pos": int(sum(1 for r in rows if r[2]=="real_planted")),
                      "synthetic_pos": int(sum(1 for r in rows if r[2]=="synthetic" and r[1]==1)), "synthetic_neg": int(sum(1 for r in rows if r[2]=="synthetic" and r[1]==0))},
       "val_size": {"n": len(vrows), "real_pages": len(val_pages)},
       "note": "Learned on real clean public wiki text plus synthetic injections (synthetic rows and learning-template sentences planted on real pages). Threshold chosen on validation only. No test page, InjecAgent row, human label or sealed data was opened.",
       "sklearn_gold": gold}
path = MODELS/"classifier_v1_2.json"; path.write_text(json.dumps(art) + "\n")
inf = Classifier.load(path); mx = 0.0
for g in gold: mx = max(mx, abs(inf.score(g["text"]) - g["sklearn_score"]))
assert mx < 1e-8, mx
rec = {"frozen_at": now, "learn_size": art["learn_size"], "val_size": art["val_size"], "threshold": art["threshold"], "validation": ch, "candidates_kept": len(ok),
       "construction_deviation": dev, "numpy_sklearn_max_abs_delta": mx, "artifact_sha256": sha_file(path), "learning_pool_sha256": sha_file(DATA/"learning_pool.jsonl"),
       "val_page_ids": [r["id"] for r in val_pages]}
(MODELS/"FIT_RECORD_v1_2.json").write_text(json.dumps(rec, indent=1) + "\n")
(MODELS/"classifier_v1_2.json.sha256").write_text(rec["artifact_sha256"] + "  classifier_v1_2.json\n")
print(json.dumps({k: v for k, v in rec.items() if k != "val_page_ids"}, indent=1))
