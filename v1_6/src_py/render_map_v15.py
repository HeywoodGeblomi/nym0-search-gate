#!/usr/bin/env python3
"""Widened verb meaning map for Search Gate v1.5 (UMAP, illustration only: the gate decides in all 384 dimensions plus the gloss features).
Each dot is placed by meaning. Fill = the gate's meaning-map decision for that verb (list, margin rule or learned probe). Run after scoring."""
import sys, json, numpy as np
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT/"src_py"))
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.patheffects as pe
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from adjustText import adjust_text
import umap
from map_check15 import MapCheck15
mc = MapCheck15(ROOT/"models"/"verb_families_v1_3.json", ROOT/"models")
V = json.load(open(ROOT/"models"/"verbmap_v15.json")); P14 = json.load(open(ROOT/"models"/"verbmap_params.json"))
NS = json.load(open(ROOT/"data"/"NEWSET.json")); new = {json.loads(l)["id"]: json.loads(l) for l in open(ROOT/"data"/"new_all.jsonl")}
reg15 = {r: list(vs) for r, vs in V["regions_widened"].items()}
seed14 = {v for vs in P14["regions"].values() for v in vs}
everyday = list(V["everyday"]); rng = np.random.RandomState(14)
everyday_plot = [everyday[i] for i in rng.choice(len(everyday), 420, replace=False)]
region_of = {v: r for r, vs in reg15.items() for v in vs}
unseen = [(new[i]["key_verb"], new[i]["category"]) for i in NS["unseen"]]; eve_new = [new[i]["key_verb"] for i in NS["everyday"]]
items = []; seen = set()
def add(t, g):
    if t not in seen: seen.add(t); items.append((t, g))
for r, vs in reg15.items():
    for v in vs: add(v, "seed14" if v in seed14 else "widened")
for v in everyday_plot: add(v, "everyday")
for v, c in unseen: add(v, "unseen")
for v in eve_new: add(v, "everyday_new")
texts = [t for t, g in items]; groups = [g for t, g in items]
X = mc.vec(texts)
dec = [mc.decide([t])[:3] for t in texts]            # (hold, rule, region)
held = np.array([d[0] for d in dec]); rule = [d[1] for d in dec]
# colour region: the nearest widened-region verb by cosine
mem = [i for i, t in enumerate(texts) if t in region_of]; M = X[mem]
reg = []
for i, t in enumerate(texts):
    if t in region_of: reg.append(region_of[t])
    else:
        s = M @ X[i]; s2 = s.copy()
        reg.append(region_of[texts[mem[int(np.argmax(s2))]]])
Y = umap.UMAP(n_components=2, metric="cosine", n_neighbors=18, min_dist=0.9, spread=2.2, random_state=15, n_jobs=1).fit_transform(X)
np.save(ROOT/"out"/"verbmap_v15_xy.npy", Y)
REGS = list(reg15)
cm = plt.get_cmap("tab20"); REGCOL = {r: cm(i * 2 % 20 + (0 if i < 10 else 1)) for i, r in enumerate(REGS)}
REGCOL = dict(zip(REGS, ["#1f77b4", "#2ca02c", "#17becf", "#d62728", "#9467bd", "#ff7f0e", "#e377c2", "#8c564b", "#bcbd22", "#7f7f7f", "#aec7e8", "#c49c94"]))
REGCOL["post_message"] = "#0b5394"; REGCOL["secrets_credentials"] = "#b8860b"
REGLAB = {r: r.replace("_", " / ") if r in ("send_share", "move_money", "buy_pay", "delete_destroy", "grant_access", "execute_run", "cancel_override") else r.replace("_", " ") for r in REGS}
REGLAB["send_share"] = "send / share"; REGLAB["move_money"] = "move money"; REGLAB["buy_pay"] = "buy / pay"; REGLAB["delete_destroy"] = "delete / destroy"; REGLAB["grant_access"] = "grant / access"; REGLAB["execute_run"] = "execute / run"; REGLAB["cancel_override"] = "cancel / override"
pad = 1.2; x0, x1, y0, y1 = Y[:, 0].min() - pad, Y[:, 0].max() + pad, Y[:, 1].min() - pad, Y[:, 1].max() + pad
gx, gy = np.meshgrid(np.linspace(x0, x1, 420), np.linspace(y0, y1, 340)); G = np.stack([gx.ravel(), gy.ravel()], 1)
ext = max(x1 - x0, y1 - y0); bw = 0.03 * ext
def kern(pts):
    d2 = ((G[:, None, :] - pts[None, :, :]) ** 2).sum(-1); return np.exp(-d2 / (2 * bw * bw)).sum(1)
learn = np.array([g in ("seed14", "widened", "everyday") for g in groups])   # the points the map was built from
Sb = kern(Y[learn & ~held]); Sreg = {}
for r in REGS:
    ii = [i for i in range(len(texts)) if learn[i] and held[i] and reg[i] == r]
    if len(ii) >= 2: Sreg[r] = kern(Y[ii])
names = list(Sreg); S = np.stack([Sreg[r] for r in names]); Rt = S.sum(0)
zone = ((Rt / (Rt + Sb + 1e-9)) >= 0.5) & (Rt > 0.35); arg = S.argmax(0)
fig, ax = plt.subplots(figsize=(24, 16), dpi=150); fig.patch.set_facecolor("#fbfaf7"); ax.set_facecolor("#fbfaf7")
for k, r in enumerate(names):
    cell = (zone & (arg == k)).astype(float).reshape(gx.shape)
    ax.contourf(gx, gy, cell, levels=[0.5, 1.5], colors=[REGCOL[r]], alpha=0.22, zorder=1)
    ax.contour(gx, gy, cell, levels=[0.5], colors=["white"], linewidths=1.4, zorder=2)
ax.contour(gx, gy, zone.astype(float).reshape(gx.shape), levels=[0.5], colors=["#222"], linewidths=2.6, zorder=2.5)
zb = gy.ravel()[zone].min(); rng_y = y1 - y0; zl, zr = gx.ravel()[zone].min(), gx.ravel()[zone].max()
anch = []
for k, r in enumerate(names):
    cell = (zone & (arg == k)).reshape(gx.shape)
    if cell.sum() > 40: anch.append((gx[cell].mean(), gy[cell].mean(), r))
anch.sort()
for n_, (ax_, ay_, r) in enumerate(anch):
    lx = zl + (zr - zl) * (n_ + 0.5) / len(anch); ly = zb - (0.05 + 0.055 * (n_ % 2)) * rng_y
    ax.annotate(REGLAB[r].upper(), xy=(ax_, ay_), xytext=(lx, ly), ha="center", va="center", fontsize=13, fontweight="bold", color=REGCOL[r], zorder=10,
                arrowprops=dict(arrowstyle="-", color=REGCOL[r], lw=1.5, alpha=0.7, shrinkA=8, shrinkB=0), bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=REGCOL[r], lw=1.5, alpha=0.95))
col = lambda i: REGCOL[reg[i]]
def sc(g, **kw):
    ii = [i for i, gg in enumerate(groups) if gg == g]
    return ii
ii = sc("everyday"); ax.scatter(Y[ii, 0], Y[ii, 1], s=16, c=["#d9534f" if held[i] else "#b9b6ae" for i in ii], alpha=0.8, linewidths=0, zorder=3)
ii = sc("widened"); ax.scatter(Y[ii, 0], Y[ii, 1], s=34, c=[col(i) for i in ii], edgecolors="white", linewidths=0.6, alpha=0.95, zorder=4)
ii = sc("seed14"); ax.scatter(Y[ii, 0], Y[ii, 1], s=95, c=[col(i) for i in ii], edgecolors="white", linewidths=1.2, zorder=5)
ii = sc("unseen"); ax.scatter(Y[ii, 0], Y[ii, 1], s=110, marker="D", c=[col(i) if held[i] else "#ffffff" for i in ii], edgecolors=[col(i) for i in ii], linewidths=1.8, zorder=6)
ii = sc("everyday_new"); ax.scatter(Y[ii, 0], Y[ii, 1], s=80, marker="s", c=["#d9534f" if held[i] else "#3a7d44" for i in ii], edgecolors="white", linewidths=0.8, zorder=6)
labs = []
for i, g in enumerate(groups):
    if g == "seed14": labs.append(ax.text(Y[i, 0], Y[i, 1], texts[i], fontsize=7.6, color=col(i), fontweight="bold", zorder=9))
    elif g == "unseen": labs.append(ax.text(Y[i, 0], Y[i, 1], texts[i], fontsize=7.4, color=col(i), zorder=9))
    elif g == "everyday_new": labs.append(ax.text(Y[i, 0], Y[i, 1], texts[i], fontsize=7.2, color="#2f6b3a" if not held[i] else "#a33", zorder=9))
for i in np.random.RandomState(5).choice([i for i, g in enumerate(groups) if g == "widened"], 70, replace=False): labs.append(ax.text(Y[i, 0], Y[i, 1], texts[i], fontsize=6.6, color=col(i), alpha=0.85, zorder=9))
adjust_text(labs, ax=ax, expand=(1.15, 1.25), arrowprops=dict(arrowstyle="-", color="#999", lw=0.4, alpha=0.6), max_move=(12, 12), iter_lim=500)
ax.set_xticks([]); ax.set_yticks([]); [s.set_visible(False) for s in ax.spines.values()]
ax.set_xlim(x0, x1); ax.set_ylim(y0 - 0.30 * (y1 - y0), y1)
ax.set_title("Nym-0 Search Gate v1.5: the widened verb meaning map", fontsize=24, fontweight="bold", loc="left", pad=62, color="#1a1a1a")
ax.text(0, 1.012, "Each dot is a command verb placed by meaning (frozen all-MiniLM-L6-v2, UMAP). The dark outline is where the map layer holds an order that uses the verb:\nthe 422-verb list, the v1.4 margin rule, or the learned probe. Twelve regions now (v1.4 had eight). Illustration only:\nthe gate decides in the full 384 dimensions.", transform=ax.transAxes, fontsize=11, color="#444", va="bottom", wrap=True)
nU = int(sum(held[i] for i in sc("unseen"))); nE = int(sum(held[i] for i in sc("everyday_new"))); nEv = int(sum(held[i] for i in sc("everyday")))
h = [Patch(fc=REGCOL[r], ec=REGCOL[r], alpha=0.35, label=REGLAB[r]) for r in REGS]
h += [Line2D([], [], marker="o", ls="", mfc="#777", mec="white", ms=11, label="v1.4 seed verb"), Line2D([], [], marker="o", ls="", mfc="#777", mec="white", ms=7, label="widened risky verb (v1.5, dev data)"),
      Line2D([], [], marker="o", ls="", mfc="#b9b6ae", mec="none", ms=6, label="everyday verb the map allows"), Line2D([], [], marker="o", ls="", mfc="#d9534f", mec="none", ms=6, label="everyday verb the map holds (false hold)"),
      Line2D([], [], marker="D", ls="", mfc="#777", mec="#777", ms=8, label="new-set unseen risky verb: map holds (filled)"), Line2D([], [], marker="D", ls="", mfc="white", mec="#777", mew=1.8, ms=8, label="new-set unseen risky verb: map misses (open)"),
      Line2D([], [], marker="s", ls="", mfc="#3a7d44", mec="white", ms=8, label="new-set everyday phrase: map allows"), Line2D([], [], marker="s", ls="", mfc="#d9534f", mec="white", ms=8, label="new-set everyday phrase: map holds")]
leg = ax.legend(handles=h, loc="lower left", fontsize=9.2, frameon=True, framealpha=0.94, ncol=3, title="Regions and marks", title_fontsize=10.5); leg.get_frame().set_edgecolor("#ddd")
ax.text(1.0, -0.012, f"Heywood Geblomi (Walter Howard)   |   margin >= -0.02 or probe >= {mc.thr:+.2f} or on the 422-verb list   |   new unseen verbs the map holds: {nU} of 60 (map layer alone)   |   new everyday phrases held: {nE} of 60", transform=ax.transAxes, ha="right", va="top", fontsize=10.2, color="#555")
fig.savefig(ROOT/"nym0_search_gate_v1_5_verb_map.png", bbox_inches="tight", facecolor=fig.get_facecolor()); plt.close(fig)
json.dump({"n_points": len(texts), "unseen_held_map_layer_only": nU, "everyday_new_held_map_layer_only": nE, "everyday_dev_sample_held": nEv, "everyday_dev_sample_n": len(everyday_plot), "projection": "UMAP cosine n_neighbors 18 min_dist 0.9 spread 2.2 random_state 15"}, open(ROOT/"out"/"verb_map_v15_info.json", "w"), indent=1)
print("ok", nU, nE, nEv)
