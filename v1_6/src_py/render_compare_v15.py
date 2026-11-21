#!/usr/bin/env python3
"""Comparison chart v1.1..v1.5 on the old 80/80 set and the new independent set; and the one-page summary (PNG + PDF)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
R = json.load(open(ROOT/"out"/"RESULTS_v15.json")); N = R["new_set_by_version"]; O = R["R2_R3_old_sets_in_sample_for_v1_5"]
V = ["v1_1", "v1_2", "v1_3", "v1_4", "v1_5"]; LAB = ["v1.1", "v1.2", "v1.3", "v1.4", "v1.5"]
COL = {"v1_1": "#bbbbbb", "v1_2": "#9ecae1", "v1_3": "#6baed6", "v1_4": "#3182bd", "v1_5": "#e6550d"}
def pct(a, b): return 100.0 * a / b
inj_old = [pct(O["old"][v]["injected_or_unseen_held"], 80) for v in V]
inj_new = [pct(N[v]["main_injected"], 120) for v in V]
fh_old = [pct(O["old"][v]["clean_false_holds"], 80) for v in V]
fh_new = [pct(N[v]["main_clean"], 120) for v in V]
un_old = [pct(O["oldslice"][v]["injected_or_unseen_held"], 40) if v in O["oldslice"] else None for v in V]
un_new = [pct(N[v]["unseen_slice"], 60) for v in V]
fig, ax = plt.subplots(1, 3, figsize=(19, 6.6), dpi=150); fig.patch.set_facecolor("#fbfaf7")
def panel(a, title, groups, bars, bar_line=None, ylabel="percent", note=None):
    a.set_facecolor("#fbfaf7"); w = 0.16
    for g, (gname, vals, hatch) in enumerate(zip(*groups)) if False else []: pass
    for gi, (gname, vals, hat) in enumerate(bars):
        for k, (v, val) in enumerate(zip(V, vals)):
            if val is None: continue
            x = gi + (k - 2) * w; a.bar(x, val, w * 0.92, color=COL[v], hatch=hat if v == "v1_5" else None, edgecolor="white" if not (hat and v == "v1_5") else "#333", linewidth=0.8)
            a.text(x, val + 1.2, f"{val:.0f}", ha="center", va="bottom", fontsize=8.5, color="#222")
    a.set_xticks(range(len(bars))); a.set_xticklabels([b[0] for b in bars], fontsize=10)
    if bar_line: a.axhline(bar_line[0], color="#c0392b", lw=1.8, ls="--"); a.text(-0.48, bar_line[0] + 2.5, bar_line[1], ha="left", color="#c0392b", fontsize=9.5, fontweight="bold", bbox=dict(fc="#fbfaf7", ec="none", pad=1))
    a.set_ylim(0, 118); a.set_ylabel(ylabel, fontsize=10); a.set_title(title, fontsize=12.5, fontweight="bold", loc="left")
    for s in ("top", "right"): a.spines[s].set_visible(False)
panel(ax[0], "Injected pages held (higher is better)", None, [("old set\n(80, in-sample for v1.5)", inj_old, "//"), ("new set\n(120, independent)", inj_new, None)], (90, "bar 90% (new set)"))
panel(ax[1], "Unseen risky verbs held (higher is better)", None, [("old slice\n(40, in-sample for v1.5)", un_old, "//"), ("new slice\n(60)", un_new, None)], (70, "bar 70% (new slice)"))
panel(ax[2], "Clean pages wrongly held (lower is better)", None, [("old set (80)", fh_old, None), ("new set (120)", fh_new, None)], (2, "bar 2%"))
fig.legend(handles=[Patch(fc=COL[v], label=l) for v, l in zip(V, LAB)] + [Patch(fc="white", ec="#333", hatch="//", label="v1.5 on data it learned from")], fontsize=10, frameon=False, loc="upper right", ncol=6, bbox_to_anchor=(0.99, 0.925))
fig.suptitle("Nym-0 Search Gate v1.1 to v1.5 on the same old set and the new independent set", fontsize=19, fontweight="bold", x=0.01, ha="left")
fig.text(0.01, 0.005, "Heywood Geblomi (Walter Howard)   |   v1.1 holds almost everything, so its high numbers come with high false holds. v1.5 widened the verbs on dev data and gained on the new set, but 35 of 120 clean pages are still held (27 are Wikibooks recipes).", fontsize=9.5, color="#555")
fig.tight_layout(rect=(0, 0.03, 1, 0.9)); fig.savefig(ROOT/"nym0_search_gate_v1_5_comparison.png", bbox_inches="tight", facecolor=fig.get_facecolor()); plt.close(fig)
print("compare ok")
