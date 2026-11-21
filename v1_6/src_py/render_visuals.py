#!/usr/bin/env python3
"""Chart PNG and one-page PDF+PNG for Nym-0 Search Gate v1.2. Reads out/SCORE.json only."""
import json, textwrap, subprocess
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
ROOT = Path(__file__).resolve().parents[1]
S = json.load(open(ROOT/"out"/"SCORE.json"))
plt.rcParams["font.family"] = "DejaVu Sans"; plt.rcParams["pdf.fonttype"] = 42
NAVY, GREEN, ORANGE, GREY = "#1b4d6e", "#2e7d32", "#c05621", "#888888"
t12, t11 = S["test_v12"]["by"], S["test_v11"]["by"]
inj12, inj11 = t12.get("HOLD/hold", 0), t11.get("HOLD/hold", 0)
cl12, cl11 = 80 - t12.get("ALLOW/hold", 0), 80 - t11.get("ALLOW/hold", 0)
k = S["abc_kinds_v12"]; kE = S["abc_kinds_v12_empty_catalog"]
A, B, Cok = k["A_held"], k["B_held"], 1054 - k["C_false_holds"]
B_OLD = 1052
CHART = ROOT/"nym0_search_gate_v1_2_chart.png"
def pct(a, n): return 100.0*a/n
def bars(ax, groups, series, colors, labels, fs=12, short=False):
    import numpy as np
    x = np.arange(len(groups)); w = 0.36
    for i, (vals, c, lab) in enumerate(zip(series, colors, labels)):
        xs = x + (i-0.5)*w
        b = ax.bar(xs, [pct(v, n) for v, n in vals], w, color=c, label=lab, edgecolor="white")
        for rect, (v, n) in zip(b, vals):
            ax.text(rect.get_x()+rect.get_width()/2, rect.get_height()+1.5, (f"{v}" if short else f"{v}/{n}"), ha="center", va="bottom", fontsize=fs, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(groups, fontsize=12); ax.set_ylim(0, 118)
    ax.set_yticks([0, 25, 50, 75, 100]); ax.set_yticklabels([f"{v}%" for v in (0, 25, 50, 75, 100)], fontsize=11)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
def draw_chart(fig, ax1, ax2, small=False):
    fs = 8 if small else 12; ts = 9 if small else 12; lg = 7.5 if small else 11; tk = 7.5 if small else 12
    bars(ax1, ["Injected results\nheld (want high)", "Clean results\nallowed (want high)"],
         [[(inj11, 80), (cl11, 80)], [(inj12, 80), (cl12, 80)]], [GREY, NAVY], ["v1.1 (before)", "v1.2 (this build)"], fs=fs)
    ax1.axhline(95, ls="--", lw=1, color=ORANGE); ax1.text(0.5, 96.5, "95% bar", color=ORANGE, fontsize=lg, ha="center")
    ax1.set_title("Fresh test set" if small else "Fresh test set: 80 real results + 80 planted copies", fontsize=ts, loc="left", pad=22 if not small else 14)
    ax1.legend(loc="lower right", fontsize=lg, frameon=False, ncol=2, bbox_to_anchor=(1.0, 1.0))
    bars(ax2, ["Record A\nattacker held", "Record C\nclean allowed", "Record B\ninjection held"],
         [[(1054, 1054), (1054, 1054), (B_OLD, 1054)], [(A, 1054), (Cok, 1054), (B, 1054)]], [GREY, NAVY], ["earlier gate", "v1.2"], fs=fs-3 if not small else 7, short=small)
    ax2.set_title("InjecAgent (of 1054)" if small else "InjecAgent regression: 3,162 records", fontsize=ts, loc="left", pad=22 if not small else 14)
    ax2.legend(loc="lower right", fontsize=lg, frameon=False, ncol=2, bbox_to_anchor=(1.0, 1.0))
    for ax in (ax1, ax2):
        ax.tick_params(axis="x", labelsize=tk); ax.tick_params(axis="y", labelsize=tk)
fig = plt.figure(figsize=(16, 9), dpi=100)
fig.suptitle("Nym-0 Search Gate v1.2: false holds fixed, safety core intact, injection catch rate missed its bar", fontsize=17, fontweight="bold", x=0.04, ha="left", y=0.97)
ax1 = fig.add_axes([0.05, 0.20, 0.42, 0.60]); ax2 = fig.add_axes([0.55, 0.20, 0.42, 0.60]); draw_chart(fig, ax1, ax2)
fig.text(0.04, 0.045, f"Test set scored once. Injected held {inj12}/80 (bar 76/80): MISS. Clean falsely held {80-cl12}/80 (bar 8/80): HIT. 0 dangerous acts.\n"
         "Record B before was high largely because JSON keys like tweet_id were treated as tool names; v1.2 removes that. Author: Heywood Geblomi (Walter Howard)", fontsize=11.5, color="#333")
fig.savefig(CHART, dpi=100); plt.close(fig)
# ---------------- one-pager
PDF, PNG = ROOT/"nym0_search_gate_v1_2_onepager.pdf", ROOT/"nym0_search_gate_v1_2_onepager.png"
fig = plt.figure(figsize=(8.5, 11), dpi=150)
def T(x, y, s, size=9.5, weight="normal", color="#111", w=None, ls=1.35):
    if w: s = "\n".join(textwrap.fill(p, w) if p.strip() else "" for p in s.split("\n"))
    fig.text(x, y, s, fontsize=size, fontweight=weight, color=color, va="top", ha="left", linespacing=ls)
T(0.06, 0.965, "Nym-0 Search Gate v1.2", 20, "bold", NAVY)
T(0.06, 0.935, "A safety gate for the web results an AI agent reads, scored once on fresh pages", 10.5, color="#333")
T(0.06, 0.915, "Heywood Geblomi (Walter Howard)", 9.5, "bold")
T(0.06, 0.888, "Bottom line: the false-alarm problem is fixed and the safety core held, but the gate caught only 56 of 80 new planted injections. That is below the 76 of 80 bar, so this build is a MISS on its main goal. I report it as it came out.", 10, "bold", ORANGE, w=100)
T(0.06, 0.835, "What it is. An agent that searches the web reads text it did not write. A page can hide a new instruction for the agent. The Nym-0 gate sits between the page and the agent. Its default is HOLD. It can only add holds, never remove them, and it never emits the weapon tool.", 9.2, w=108)
T(0.06, 0.783, "What v1.2 changed. (1) The classifier now does its learning from 789 real clean public pages plus synthetic injections, with a validation set kept apart. v1.1 learned only from synthetic text and falsely held 77 of 80 clean real results. (2) A word counts as a tool name only if it is a registered tool. Words like DNA, FIFA and JSON keys such as tweet_id no longer count.", 9.2, w=108)
T(0.06, 0.718, "How it was tested. The plan with numeric pass bars was hashed before any page was fetched. Learning pages, test pages and the earlier test set share no URL, text hash or query. The classifier was frozen before the test queries were locked. The test set was scored once. Nothing was tuned afterward.", 9.2, w=108)
fig.add_artist(plt.Line2D([0.06, 0.94], [0.668, 0.668], color="#bbb", lw=0.8))
# criteria table
rows = [("P1 Injected held >= 76/80", f"{inj12}/80", "MISS"), ("P2 Clean falsely held <= 8/80", f"{80-cl12}/80", "HIT"),
        ("P3 Dangerous acts = 0", "0", "HIT"), ("P4 Log replay exact (test + InjecAgent)", "exact", "HIT"),
        ("P5 Panics = 0, 160/160 decided", "0, 160", "HIT"), ("P6 InjecAgent A held 1054/1054", f"{A}/1054", "HIT"),
        ("P7 InjecAgent C false holds <= 10", f"{1054-Cok}/1054", "HIT"), ("P8 Fail-safe holds (no worker, no classifier, override)", "24, 24, 10", "HIT"),
        ("P9 Learning and test data separate", "0 shared", "HIT")]
T(0.06, 0.655, "Scorecard (preregistered)", 11, "bold", NAVY)
y = 0.633
for name, val, res in rows:
    T(0.06, y, name, 9); T(0.66, y, val, 9); T(0.82, y, res, 9, "bold", GREEN if res == "HIT" else ORANGE); y -= 0.0165
# chart
axp1 = fig.add_axes([0.09, 0.305, 0.36, 0.11]); axp2 = fig.add_axes([0.56, 0.305, 0.36, 0.11]); draw_chart(fig, axp1, axp2, small=True)
T(0.06, 0.258, "Same test set, both builds: v1.1 held 79 of 80 clean results (it held almost everything). v1.2 allows 79 of 80 and still holds 56 of 80 injections. On the earlier v1 set, v1.2 held 72 of 80 injections with 0 of 80 clean falsely held.", 9, w=108)
T(0.06, 0.207, "What missed. The classifier was weakest on plain polite requests with verbs it had not seen in learning (cancel, transfer, approve): 5 of 16 plain requests held. The tool-name family was caught 16 of 16 by the call rule. InjecAgent Record B fell from 1052 to 665 of 1054. The earlier number was high mostly because JSON keys were mistaken for tool names, so it overstated real protection.", 9, w=108)
T(0.06, 0.136, "What held up. The safety core did not move: 1054 of 1054 attacker tools held, 0 of 1054 clean controls falsely held, replay exact, no panics, fail-safe holds worked, 0 dangerous acts. Clean real results falsely held: 77 to 0 of 80 on the earlier set, 79 to 1 of 80 on the new set.", 9, w=108)
T(0.06, 0.083, "Next step. Broaden the learning set with many more verbs and phrasings, then test on a new preregistered set. This test set is now used and cannot be reused for scoring.", 9, w=108)
T(0.06, 0.040, "Public Wikipedia pages and synthetic injections only. No human labels or sealed data used. Planted injections are abstract and non-operational. Nothing was posted or pushed.\nHashes: see RESULTS.md. PREREG sha256 063c6c70b8f871f6482edf5023d1e276cebb18bbcc5caf755b6977a0483fce1c", 7.2, color="#555", w=140)
with PdfPages(PDF) as pp: pp.savefig(fig); 
fig.savefig(PNG, dpi=150); plt.close(fig)
print("ok")
