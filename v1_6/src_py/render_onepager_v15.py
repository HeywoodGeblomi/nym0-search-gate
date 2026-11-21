#!/usr/bin/env python3
import json, textwrap
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.image as mpimg
R = json.load(open(ROOT/"out"/"RESULTS_v15.json")); C = R["criteria"]
fig = plt.figure(figsize=(8.5, 11), dpi=200); fig.patch.set_facecolor("#fbfaf7")
ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off"); ax.set_xlim(0, 8.5); ax.set_ylim(0, 11)
ax.text(0.5, 10.45, "Nym-0 Search Gate v1.5", fontsize=24, fontweight="bold", color="#1a1a1a")
ax.text(0.5, 10.1, "Wider verb map, Rust port, scored once on an independent set", fontsize=11.5, color="#444")
ax.text(0.5, 9.82, "Heywood Geblomi (Walter Howard)   |   2026-11-19", fontsize=10, color="#666")
ax.add_patch(plt.Rectangle((0.5, 9.05), 7.5, 0.55, fc="#fdecea", ec="#c0392b", lw=1.5))
ax.text(0.65, 9.32, "MISS: injected held 91 of 120 (bar 108) and clean false holds 35 of 120 (bar 2).", fontsize=10.5, fontweight="bold", color="#c0392b", va="center")
ax.text(0.65, 9.13, "Everything else hit. The unseen-verb bar hit at exactly 42 of 60.", fontsize=9.5, color="#7b241c", va="center")
rows = [("P1", "injected held (new set, 120)", ">= 108", "91", "MISS"), ("P2", "unseen risky verbs held (60)", ">= 42", "42", "HIT"), ("P3", "clean false holds (120)", "<= 2", "35", "MISS"),
        ("P4", "InjecAgent A held", "1054", "1054", "HIT"), ("P5", "InjecAgent C false holds", "0", "0", "HIT"), ("P6", "InjecAgent B held", ">= 1014", "1026", "HIT"),
        ("P7", "Rust and Python parity", "100%", "100% (0 diffs)", "HIT"), ("P8", "safety core", "all", "all held", "HIT")]
y = 8.75; ax.text(0.5, y, "Scores against the bars", fontsize=12, fontweight="bold")
y -= 0.3
for h, x in zip(("", "Criterion", "Bar", "v1.5", "Result"), (0.5, 0.95, 4.2, 5.3, 7.0)): ax.text(x, y, h, fontsize=9, fontweight="bold", color="#555")
for rid, name, bar, val, res in rows:
    y -= 0.27
    ax.text(0.5, y, rid, fontsize=9.5); ax.text(0.95, y, name, fontsize=9.5); ax.text(4.2, y, bar, fontsize=9.5); ax.text(5.3, y, val, fontsize=9.5, fontweight="bold")
    ax.text(7.0, y, res, fontsize=9.5, fontweight="bold", color="#c0392b" if res == "MISS" else "#2e7d32")
    ax.plot([0.5, 8.0], [y - 0.09, y - 0.09], color="#e5e2da", lw=0.6)
y -= 0.4
ax.text(0.5, y, "Same new set, older versions: injected held 91 / 75 / 57 / 19 (v1.5 / v1.4 / v1.3 / v1.2). Clean false holds 35 / 35 / 28 / 19.", fontsize=9, color="#333")
img = mpimg.imread(ROOT/"nym0_search_gate_v1_5_comparison.png"); h, w = img.shape[:2]; wi = 5.8; hi = wi * h / w
ax.imshow(img, extent=(1.35, 1.35 + wi, y - 0.15 - hi, y - 0.15), aspect="auto", zorder=1); ax.set_xlim(0, 8.5); ax.set_ylim(0, 11)
y = y - 0.15 - hi - 0.3
ax.text(0.5, y, "What held up", fontsize=11.5, fontweight="bold", color="#2e7d32")
t = ["The wider map added 16 injected holds and 12 InjecAgent B holds with no new false hold on clean pages (35 before, 35 after).",
     "Rust matches Python on every record and phrase checked (3,919 orders on the new, old and InjecAgent files; 12,171 more on dev). Safety core intact, 0 holds lifted."]
for s in t:
    for k, ln in enumerate(textwrap.wrap(s, 120)):
        y -= 0.2; ax.text(0.5, y, ln, fontsize=8.8, color="#222")
    y -= 0.05
y -= 0.4; ax.text(0.5, y, "What did not", fontsize=11.5, fontweight="bold", color="#c0392b")
t = ["35 of 120 clean pages held: 27 of 30 Wikibooks pages (real imperatives) and 8 of 90 Wikipedia pages, from the old classifier and instruction check.",
     "Unseen-verb hit is thin: 8 of 18 strictly unseen verbs held, and the slice was built by a converter written after the set was opened.",
     "All 7 system_tag injections slip through every layer. Misses include embezzle, phish, delete, annihilate, doxx."]
for s in t:
    for k, ln in enumerate(textwrap.wrap(s, 120)):
        y -= 0.2; ax.text(0.5, y, ln, fontsize=8.8, color="#222")
    y -= 0.05
ax.text(0.5, 0.3, "Preregistered 14:34 EST, frozen 15:00 EST, set opened 15:01 EST, scored once. Synthetic and public data only.\nCharts use UMAP for illustration; the gate decides in full dimension.", fontsize=7.5, color="#777")
fig.savefig(ROOT/"nym0_search_gate_v1_5_onepager.png", facecolor=fig.get_facecolor()); fig.savefig(ROOT/"nym0_search_gate_v1_5_onepager.pdf", facecolor=fig.get_facecolor())
print("ok")
