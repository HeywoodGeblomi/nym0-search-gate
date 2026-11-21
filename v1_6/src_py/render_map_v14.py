#!/usr/bin/env python3
"""Verb meaning map (t-SNE, scikit-learn) and threshold chart for Search Gate v1.4. Illustration only: every gate decision uses the full 384-dimension scores,
never this 2D picture. Run after the official score. Needs numpy, matplotlib, scikit-learn, adjustText (build time only)."""
import sys, json, numpy as np
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT/"src_py"))
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from sklearn.manifold import TSNE
from adjustText import adjust_text
from map_check import MapCheck, topk_mean
import verbmap_seeds as V
mc = MapCheck(ROOT/"models"/"verb_families_v1_3.json", ROOT/"models")
fam = json.load(open(ROOT/"models"/"verb_families_v1_3.json"))
VL = json.load(open(ROOT/"data"/"VERB_LOCK.json"))
SC = json.load(open(ROOT/"out"/"SCORE.json"))
tau = mc.tau
seeds_by_region = {r: list(vs) for r, vs in mc.params["regions"].items()}
seed_set = {v for vs in seeds_by_region.values() for v in vs}
table_words = sorted({w for c, e in fam["categories"].items() for w in e["tier1"] if w not in seed_set})
anchors = mc.params["anchors"]
unseen = [(e["verb"], e["category"]) for e in VL["unseen_risky"]]; everyday = [e["verb"] for e in VL["everyday_imperative"]]
published = ["wire", "archive", "remit", "dispatch", "relay", "liquidate", "ping", "sever", "make a call to", "set aside"]
dev_unseen = list(V.DEV_UNSEEN_RISKY)
# every plotted item, its group
items = []   # (text, group)
for r, vs in seeds_by_region.items():
    for v in vs: items.append((v, "seed"))
for v in table_words: items.append((v, "table"))
for v in anchors: items.append((v, "anchor"))
for v in dev_unseen: items.append((v, "dev_unseen"))
for v, c in unseen: items.append((v, "unseen"))
for v in everyday: items.append((v, "everyday"))
for v in published: items.append((v, "published"))
seen = set(); uniq = []
for t, g in items:
    if t in seen: continue
    seen.add(t); uniq.append((t, g))
items = uniq
texts = [t for t, g in items]; groups = [g for t, g in items]
X = mc.vec(texts)
# full-dimension decision for every plotted item
dec = {}
for t, g in items:
    m, reg, rs, bs = mc.score_phrase(t, exclude_anchor=t if g == "anchor" else None)
    dec[t] = (m, reg)
margin = np.array([dec[t][0] for t in texts]); region = [dec[t][1] for t in texts]; inreg = margin >= tau
import os
PROJ = os.environ.get("NYM0_PROJ", "umap")
if PROJ == "umap":
    import umap
    Y = umap.UMAP(n_components=2, metric="cosine", n_neighbors=18, min_dist=0.9, spread=2.2, random_state=14, n_jobs=1).fit_transform(X)
    PROJ_DOC = "UMAP (umap-learn), cosine metric, n_neighbors 18, min_dist 0.9, spread 2.2, random_state 14"
else:
    Y = TSNE(n_components=2, metric="cosine", perplexity=28, init="pca", learning_rate="auto", random_state=14, max_iter=2000).fit_transform(X)
    PROJ_DOC = "t-SNE (scikit-learn), cosine metric, perplexity 28, PCA init, random_state 14, 2000 iterations"
np.save(ROOT/"out"/"verbmap_xy.npy", Y)
REGCOL = {"send_share": "#1f77b4", "move_money": "#2ca02c", "buy_pay": "#17becf", "delete_destroy": "#d62728", "grant_access": "#9467bd", "execute_run": "#ff7f0e", "contact": "#e377c2", "cancel_override": "#8c564b"}
REGLAB = {"send_share": "send / share", "move_money": "move money", "buy_pay": "buy / pay", "delete_destroy": "delete / destroy", "grant_access": "grant / access", "execute_run": "execute / run", "contact": "contact", "cancel_override": "cancel / override"}
# ---------- shaded regions from the gate's own decisions, smoothed in 2D
pad = 1.2
x0, x1, y0, y1 = Y[:, 0].min() - pad, Y[:, 0].max() + pad, Y[:, 1].min() - pad, Y[:, 1].max() + pad
gx, gy = np.meshgrid(np.linspace(x0, x1, 420), np.linspace(y0, y1, 340))
G = np.stack([gx.ravel(), gy.ravel()], 1)
ext = max(x1 - x0, y1 - y0); bw = 0.032 * ext
def kern(pts): 
    d2 = ((G[:, None, :] - pts[None, :, :]) ** 2).sum(-1); return np.exp(-d2 / (2 * bw * bw)).sum(1)
benign_pts = Y[~inreg & np.array([g in ("anchor", "everyday") for g in groups])]
Sb = kern(benign_pts)
Sreg = {}
for r in REGCOL:
    pts = Y[[i for i in range(len(texts)) if inreg[i] and region[i] == r]]
    if len(pts) >= 2: Sreg[r] = kern(pts)
names = list(Sreg); S = np.stack([Sreg[r] for r in names])
Rtot = S.sum(0); zone = ((Rtot / (Rtot + Sb + 1e-9)) >= 0.5) & (Rtot > 0.35)
arg = S.argmax(0)
fig, ax = plt.subplots(figsize=(22, 15), dpi=150)
fig.patch.set_facecolor("#fbfaf7"); ax.set_facecolor("#fbfaf7")
for k, r in enumerate(names):
    cell = (zone & (arg == k)).astype(float).reshape(gx.shape)
    ax.contourf(gx, gy, cell, levels=[0.5, 1.5], colors=[REGCOL[r]], alpha=0.22, zorder=1)
    ax.contour(gx, gy, cell, levels=[0.5], colors=["white"], linewidths=1.6, zorder=2)
zz = zone.astype(float).reshape(gx.shape)
ax.contour(gx, gy, zz, levels=[0.5], colors=["#222222"], linewidths=2.6, zorder=2.5)
import matplotlib.patheffects as pe
zb = gy.ravel()[zone].min(); rng_y = y1 - y0
anch = []
for k, r in enumerate(names):
    cell = (zone & (arg == k)).reshape(gx.shape)
    if cell.sum() > 40: anch.append((gx[cell].mean(), gy[cell].mean(), r))
anch.sort()
zl, zr = gx.ravel()[zone].min(), gx.ravel()[zone].max()
for n_, (ax_, ay_, r) in enumerate(anch):
    lx = zl + (zr - zl) * (n_ + 0.5) / len(anch)
    ly = zb - (0.05 + 0.06 * (n_ % 2)) * rng_y
    ax.annotate(REGLAB[r].upper(), xy=(ax_, ay_), xytext=(lx, ly), ha="center", va="center", fontsize=15, fontweight="bold", color=REGCOL[r], zorder=10,
                arrowprops=dict(arrowstyle="-", color=REGCOL[r], lw=1.6, alpha=0.75, shrinkA=8, shrinkB=0),
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=REGCOL[r], lw=1.6, alpha=0.95))
# everyday anchors
idx = [i for i, g in enumerate(groups) if g == "anchor"]
ax.scatter(Y[idx, 0], Y[idx, 1], s=14, c="#b9b6ae", alpha=0.75, linewidths=0, zorder=3)
# v1.3 fan-out table words
idx = [i for i, g in enumerate(groups) if g == "table"]
ax.scatter(Y[idx, 0], Y[idx, 1], s=26, c=[REGCOL.get(region[i], "#777") if inreg[i] else "#ffffff" for i in idx], edgecolors=[REGCOL.get(region[i], "#777") for i in idx], linewidths=0.9, alpha=0.85, zorder=4)
# seeds
idx = [i for i, g in enumerate(groups) if g == "seed"]
seed_region = {v: r for r, vs in seeds_by_region.items() for v in vs}
ax.scatter(Y[idx, 0], Y[idx, 1], s=70, c=[REGCOL[seed_region[texts[i]]] for i in idx], edgecolors="white", linewidths=1.0, zorder=5)
# held-out test verbs
idx = [i for i, g in enumerate(groups) if g == "unseen"]
ax.scatter(Y[idx, 0], Y[idx, 1], s=95, marker="D", c=[REGCOL[dict(unseen)[texts[i]]] if inreg[i] else "#ffffff" for i in idx], edgecolors=[REGCOL[dict(unseen)[texts[i]]] for i in idx], linewidths=1.8, zorder=6)
idx = [i for i, g in enumerate(groups) if g == "everyday"]
ax.scatter(Y[idx, 0], Y[idx, 1], s=70, marker="s", c="#3a7d44", edgecolors="white", linewidths=0.8, zorder=6, alpha=0.9)
# published v1.3 misses
idx = [i for i, g in enumerate(groups) if g == "published"]
ax.scatter(Y[idx, 0], Y[idx, 1], s=420, marker="*", c=["#111111" if inreg[i] else "#ffffff" for i in idx], edgecolors="#111111", linewidths=1.8, zorder=8)
# labels
texts_lab = []
def lab(i, color, fs, weight="normal", bbox=False):
    t = ax.text(Y[i, 0], Y[i, 1], texts[i], fontsize=fs, color=color, fontweight=weight, zorder=9,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.65) if bbox else None)
    texts_lab.append(t)
for i, g in enumerate(groups):
    if g == "seed": lab(i, REGCOL[seed_region[texts[i]]], 7.6, "bold")
    elif g == "unseen": lab(i, REGCOL[dict(unseen)[texts[i]]], 7.4, "normal")
    elif g == "everyday": lab(i, "#2f6b3a", 7.2)
    elif g == "published": lab(i, "#000000", 11.5, "bold", True)
rng = np.random.RandomState(3)
for i in rng.choice([i for i, g in enumerate(groups) if g == "anchor"], 22, replace=False): lab(i, "#8d8a82", 6.8)
adjust_text(texts_lab, ax=ax, expand=(1.15, 1.25), arrowprops=dict(arrowstyle="-", color="#999", lw=0.4, alpha=0.6), max_move=(12, 12), iter_lim=500)
ax.set_xticks([]); ax.set_yticks([])
for s in ax.spines.values(): s.set_visible(False)
ax.set_xlim(x0, x1); ax.set_ylim(y0 - 0.30 * (y1 - y0), y1)
ax.set_title("Nym-0 Search Gate v1.4: the verb meaning map", fontsize=24, fontweight="bold", loc="left", pad=30, color="#1a1a1a")
ax.text(0, 1.012, "Each dot is a command verb placed by meaning (frozen all-MiniLM-L6-v2, "+PROJ.upper().replace('TSNE','t-SNE')+"). The dark outline is the risky zone: where the gate holds an order that uses the verb. Colors show the nearest of the eight regions. Illustration only: the gate decides in all 384 dimensions.", transform=ax.transAxes, fontsize=11.2, color="#444", va="bottom")
h = [Patch(fc=REGCOL[r], ec=REGCOL[r], alpha=0.35, label=REGLAB[r]) for r in REGCOL]
h += [Line2D([], [], marker="o", ls="", mfc="#777", mec="white", ms=9, label="seed verb (sets the region)"),
      Line2D([], [], marker="o", ls="", mfc="white", mec="#777", ms=7, label="v1.3 fan-out word (open: outside every region)"),
      Line2D([], [], marker="o", ls="", mfc="#b9b6ae", mec="none", ms=6, label="everyday verb (dev anchor)"),
      Line2D([], [], marker="D", ls="", mfc="#777", mec="#777", ms=8, label="held-out unseen risky verb: inside (filled)"),
      Line2D([], [], marker="D", ls="", mfc="white", mec="#777", mew=1.8, ms=8, label="held-out unseen risky verb: outside (open)"),
      Line2D([], [], marker="s", ls="", mfc="#3a7d44", mec="white", ms=8, label="held-out everyday verb"),
      Line2D([], [], marker="*", ls="", mfc="#111", mec="#111", ms=15, label="v1.3 published miss: inside (filled)"),
      Line2D([], [], marker="*", ls="", mfc="white", mec="#111", mew=1.6, ms=15, label="v1.3 published miss: outside (open)")]
leg = ax.legend(handles=h, loc="lower left", bbox_to_anchor=(0.0, 0.0), fontsize=9.6, frameon=True, framealpha=0.94, ncol=2, title="Risky regions and marks", title_fontsize=10.5)
leg.get_frame().set_edgecolor("#ddd")
pubin = sum(1 for t in published if dec[t][0] >= tau)
ax.text(1.0, -0.012, f"Heywood Geblomi (Walter Howard)   |   threshold margin >= {tau:+.2f} (fixed on dev data)   |   {pubin} of 10 published v1.3 misses fall inside a region", transform=ax.transAxes, ha="right", va="top", fontsize=10.5, color="#555")
fig.savefig(ROOT/"nym0_search_gate_v1_4_verb_map.png", bbox_inches="tight", facecolor=fig.get_facecolor()); plt.close(fig)
json.dump({"projection": PROJ_DOC, "n_points": len(texts), "tau": tau,
           "published_inside": {t: bool(dec[t][0] >= tau) for t in published}, "published_margin": {t: round(dec[t][0], 4) for t in published}},
          open(ROOT/"out"/"verb_map_info.json", "w"), indent=1)
# ---------- threshold chart: margin of every verb against the threshold line
groups_def = [("everyday dev anchors", "anchor", "#9a978f"), ("v1.3 fan-out words\n(not seeds)", "table", "#4c78a8"), ("dev unseen risky", "dev_unseen", "#f58518"),
              ("held-out unseen risky (test)", "unseen", "#e45756"), ("held-out everyday (test)", "everyday", "#3a7d44"), ("v1.3 published misses", "published", "#111111")]
fig, (axa, axb) = plt.subplots(1, 2, figsize=(17, 8.2), dpi=170, gridspec_kw={"width_ratios": [1.55, 1]})
fig.patch.set_facecolor("#fbfaf7")
for a in (axa, axb): a.set_facecolor("#fbfaf7")
rng = np.random.RandomState(1)
ymin, ymax = margin.min() - 0.03, margin.max() + 0.04
axa.axhspan(tau, ymax, color="#e45756", alpha=0.07, zorder=0); axa.axhspan(ymin, tau, color="#4c78a8", alpha=0.05, zorder=0)
for k, (name, g, col) in enumerate(groups_def):
    ii = [i for i, gg in enumerate(groups) if gg == g]; m = margin[ii]
    xs = k + (rng.rand(len(ii)) - 0.5) * 0.55
    mk = "*" if g == "published" else "o"
    axa.scatter(xs, m, s=(260 if g == "published" else 26), c=col, alpha=0.8, marker=mk, edgecolors="white", linewidths=0.4, zorder=3)
    axa.hlines(np.median(m), k - 0.3, k + 0.3, colors="#222", lw=2.0, zorder=4)
    axa.text(k, ymin + 0.004, f"{int((m >= tau).sum())} of {len(m)} above", ha="center", va="bottom", fontsize=9.4, color="#222", fontweight="bold")
    if g == "published":
        order = sorted(zip(ii, xs), key=lambda p: -margin[p[0]]); ylab = []
        for n_, (i, xx) in enumerate(order):
            yl = margin[i] if not ylab else min(margin[i], ylab[-1] - 0.03); ylab.append(yl)
            axa.annotate(texts[i], (xx, margin[i]), xytext=(k + 0.62, yl), textcoords="data", fontsize=8.8, color="#111", va="center",
                         arrowprops=dict(arrowstyle="-", color="#888", lw=0.6, shrinkA=0, shrinkB=6))
axa.axhline(tau, color="#c0392b", lw=2.4, zorder=5)
axa.text(-0.55, ymax - 0.02, f"HOLD zone: margin at or above {tau:+.2f} (red line). Below the line the verb is allowed.", ha="left", va="top", color="#c0392b", fontsize=11, fontweight="bold")
axa.set_xticks(range(len(groups_def))); axa.set_xticklabels([n.replace(" (", "\n(") for n, _, _ in groups_def], fontsize=9.4)
axa.set_ylabel("margin = similarity to nearest risky region minus similarity to everyday verbs", fontsize=10.2)
axa.set_ylim(ymin, ymax); axa.set_xlim(-0.6, len(groups_def) + 0.15)
for s in ("top", "right"): axa.spines[s].set_visible(False)
axa.set_title("Where each verb sits against the threshold (full 384-dimension score)", fontsize=13, loc="left", fontweight="bold")
# panel b: threshold sweep on dev data
sb = np.array([dec[t][0] for t, g in items if g == "anchor"]); sp = np.array([dec[t][0] for t, g in items if g == "table"]); su = np.array([dec[t][0] for t, g in items if g == "dev_unseen"])
ts = np.linspace(-0.15, 0.2, 141)
axb.plot(ts, [(sb >= t).mean() * 100 for t in ts], color="#9a978f", lw=2.6, label="false holds: everyday verbs (dev, leave-one-out)")
axb.plot(ts, [(sp >= t).mean() * 100 for t in ts], color="#4c78a8", lw=2.6, label="in region: v1.3 fan-out words (dev)")
axb.plot(ts, [(su >= t).mean() * 100 for t in ts], color="#f58518", lw=2.6, label="in region: dev unseen risky verbs")
axb.axvline(tau, color="#c0392b", lw=2.4); axb.text(tau + 0.004, 96, f"chosen on dev: {tau:+.2f}", color="#c0392b", fontsize=10.5, fontweight="bold", va="top")
axb.set_xlabel("threshold on the margin", fontsize=10.5); axb.set_ylabel("percent of verbs", fontsize=10.5); axb.set_ylim(0, 100); axb.set_xlim(-0.15, 0.2)
axb.legend(fontsize=9, loc="center right", frameon=False)
for s in ("top", "right"): axb.spines[s].set_visible(False)
axb.set_title("How the dev data set the threshold", fontsize=13, loc="left", fontweight="bold")
fig.suptitle("Nym-0 Search Gate v1.4: threshold chart", fontsize=21, fontweight="bold", x=0.012, ha="left", y=1.0)
fig.text(0.012, 0.005, "Heywood Geblomi (Walter Howard)", fontsize=10, color="#555")
fig.tight_layout(rect=(0, 0.02, 1, 0.95))
fig.savefig(ROOT/"nym0_search_gate_v1_4_threshold_chart.png", bbox_inches="tight", facecolor=fig.get_facecolor()); plt.close(fig)
print("ok", pubin)
