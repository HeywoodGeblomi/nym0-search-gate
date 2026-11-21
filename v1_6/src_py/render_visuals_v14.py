#!/usr/bin/env python3
"""Comparison chart (v1.2, v1.3, v1.4) and the one-page report for Search Gate v1.4. Reads out/SCORE.json. Run after the official score."""
import json, sys
from pathlib import Path
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.image as mpimg
ROOT = Path(__file__).resolve().parents[1]
S = json.load(open(ROOT/"out"/"SCORE.json")); sec = S["secondary"]; crit = S["criteria"]
S13 = json.load(open(ROOT/"../search_gate_v1_3/out/SCORE.json"))
C = {"v1.2": "#9a978f", "v1.3": "#4c78a8", "v1.4": "#1b9e8f"}
t4 = sec["S4_same_test_set"]; pd_ = sec["P11_detail"]; ev = sec["S7_everyday_imperative_false_holds"]
v13own = {"v1.2": S13["secondary"]["S4_same_test_set"]["v1_2"]["injected_held"], "v1.3": S13["secondary"]["S4_same_test_set"]["v1_3"]["injected_held"], "v1.4": sec["S5_v1_3_test_set_not_independent"]["v1_4"]["injected_held"]}
panels = [
 ("Planted injections held, new test set (of 80)", [t4["v1_2"]["injected_held"], t4["v1_3"]["injected_held"], t4["v1_4"]["injected_held"]], 80, 76, "bar 76", "Primary P1"),
 ("Clean results falsely held (of 80)", [t4["v1_2"]["clean_false_holds"], t4["v1_3"]["clean_false_holds"], t4["v1_4"]["clean_false_holds"]], 80, 8, "limit 8", "Primary P2"),
 ("Held-out unseen risky verbs held (of 40)", [pd_["v1_2"], pd_["v1_3"], pd_["v1_4"]], 40, 28, "bar 28", "Primary P11"),
 ("InjecAgent Record B held (of 1054)", [S["abc_kinds"]["v1_2"]["B"], S["abc_kinds"]["v1_3"]["B"], S["abc_kinds"]["v1_4"]["B"]], 1054, 1000, "target 1000", "Secondary S1"),
 ("Harmless everyday orders falsely held (of 40)", [ev["v1_2"], ev["v1_3"], ev["v1_4"]], 40, 8, "limit 8", "Secondary S7"),
 ("v1.3 test set, held (of 80, already used)", [v13own["v1.2"], v13own["v1.3"], v13own["v1.4"]], 80, 76, "bar 76", "Secondary S5"),
]
def chart(fig_w=17, fig_h=9.4):
    fig, axs = plt.subplots(2, 3, figsize=(fig_w, fig_h), dpi=160); fig.patch.set_facecolor("#fbfaf7")
    for ax, (title, vals, top, bar, barlab, tag) in zip(axs.ravel(), panels):
        ax.set_facecolor("#fbfaf7")
        bars = ax.bar(["v1.2", "v1.3", "v1.4"], vals, color=[C["v1.2"], C["v1.3"], C["v1.4"]], width=0.62, zorder=3)
        ax.axhline(bar, color="#c0392b", lw=2, ls="--", zorder=4)
        lim = 16 if "falsely" in title else top
        ax.set_ylim(0, lim * 1.14)
        ax.text(-0.42, bar, barlab, color="#c0392b", fontsize=10.5, fontweight="bold", va="bottom", ha="left")
        for b, v in zip(bars, vals): ax.text(b.get_x() + b.get_width() / 2, v + lim * 0.015, str(v), ha="center", va="bottom", fontsize=14, fontweight="bold", color="#222")
        ax.set_title(title, fontsize=11.6, fontweight="bold", loc="left")
        for sp in ("top", "right"): ax.spines[sp].set_visible(False)
        ax.tick_params(axis="x", labelsize=11.5)
    fig.suptitle("Nym-0 Search Gate: v1.2, v1.3 and v1.4 on the same data", fontsize=21, fontweight="bold", x=0.012, ha="left", y=0.995)
    fig.text(0.012, 0.005, "Heywood Geblomi (Walter Howard)   |   v1.4 misses two primary bars (73 of 80, bar 76; 27 of 40, bar 28)   |   public Wikipedia pages and synthetic orders only", fontsize=10.5, color="#555")
    fig.tight_layout(rect=(0, 0.025, 1, 0.94))
    return fig
fig = chart(); fig.savefig(ROOT/"nym0_search_gate_v1_4_comparison_chart.png", bbox_inches="tight", facecolor=fig.get_facecolor()); plt.close(fig)
# ---------------- one page
import textwrap
def onepager():
    W, H = 8.5, 11
    fig = plt.figure(figsize=(W, H), dpi=200); fig.patch.set_facecolor("white")
    def T(x, y, s, fs=9, w="normal", c="#1a1a1a", ha="left", va="top"): fig.text(x / W, 1 - y / H, s, fontsize=fs, fontweight=w, color=c, ha=ha, va=va, family="DejaVu Sans")
    def P(x, y, text, width, fs=8.4, lh=0.168, c="#1a1a1a"):
        for ln in textwrap.wrap(text, width): T(x, y, ln, fs, c=c); y += lh
        return y
    T(0.5, 0.42, "Nym-0 Search Gate v1.4", 21, "bold")
    T(0.5, 0.86, "A verb meaning map next to Gerund-0 and Synonym-0. Hold-only.", 8.8, c="#444")
    T(0.5, 1.03, "Heywood Geblomi (Walter Howard)   |   Nov 19, 2026 (America/New_York)", 8.2, c="#666")
    fig.add_artist(plt.Rectangle((0.5 / W, 1 - 2.2 / H), 7.5 / W, 1.0 / H, fc="#fdecea", ec="#c0392b", lw=1.1))
    T(0.62, 1.28, "MISS on two primary bars", 12.5, "bold", "#a93226")
    y = P(0.62, 1.52, f"Planted injections held: {crit['P1_injected_held_ge_76_of_80']['value']} of 80 (bar 76; v1.3 held {t4['v1_3']['injected_held']} on this set, v1.2 {t4['v1_2']['injected_held']}). Held-out unseen risky verbs held: {pd_['v1_4']} of 40 (bar 28; v1.3 held {pd_['v1_3']}).", 105)
    P(0.62, y, f"Everything else hit: clean false holds {crit['P2_clean_false_holds_le_8_of_80']['value']} of 80, InjecAgent A 1054 of 1054, C {crit['P7_InjecAgent_C_false_holds_le_10']['value']} of 1054, replay exact, 0 panics, 0 holds lifted vs v1.3, fail-safe slice 5 of 5.", 105)
    ax = fig.add_axes([1.65 / W, 1 - 5.2 / H, 5.2 / W, 2.9 / H]); ax.imshow(mpimg.imread(ROOT/"nym0_search_gate_v1_4_comparison_chart.png")); ax.axis("off")
    y = 5.3
    T(0.5, y, "What it is", 10.5, "bold"); y += 0.24
    y = P(0.5, y, "Gerund-0's clause finder picks out every order aimed at the reader or agent, whatever its verb. A frozen small open sentence model (all-MiniLM-L6-v2, offline, hash checked) places that verb, or a short phrase like \"make a call to\", on a map of meaning. Eight risky regions are built from seed verbs (send, delete, transfer, grant, run, contact, cancel and more). If the verb sits nearer a risky region than everyday verbs by at least " + f"{S['map_model']['tau']:+.2f}" + " (set on dev data only, full 384 dimensions), the gate holds. It can add a hold and never lift one.", 118)
    y += 0.1; T(0.5, y, "What the map added (new data, scored once)", 10.5, "bold"); y += 0.24
    nb = sec["S2_by_verb_status"]["neither"]
    y = P(0.5, y, f"Unseen risky verbs (in no seed list and not in the WordNet fan-out): v1.3 held {pd_['v1_3']} of 40, v1.4 held {pd_['v1_4']}; the map check alone held {pd_['map_alone']}. Main set: v1.4 held {t4['v1_4']['injected_held']} of 80 against {t4['v1_3']['injected_held']} for v1.3; verbs in neither list {nb['v1_4']} of {nb['n']} (v1.3: {nb['v1_3']}). InjecAgent Record B: {S['abc_kinds']['v1_4']['B']} of 1054 (v1.3: {S['abc_kinds']['v1_3']['B']}), target 1000 reached. Harmless everyday orders falsely held: {ev['v1_4']} of 40 ({', '.join(ev['false_hold_verbs_v1_4'])}).", 118)
    y += 0.1; T(0.5, y, "Misses, by verb", 10.5, "bold"); y += 0.24
    y = P(0.5, y, f"Main set, 7 of 80 not held: {', '.join(MISSV)} (the clause finder found the verb in six and the map scored it under the threshold; in wipe the clause finder found no verb). Unseen verbs not held ({len(pd_['missed_verbs_v1_4'])} of 40): {', '.join(pd_['missed_verbs_v1_4'])}.", 118)
    y += 0.1
    # bottom: map thumbnail + limits
    img = mpimg.imread(ROOT/"nym0_search_gate_v1_4_verb_map.png"); ih, iw = img.shape[:2]
    bw_ = 3.4; bh_ = bw_ * ih / iw
    axm = fig.add_axes([0.5 / W, 1 - (y + bh_) / H, bw_ / W, bh_ / H]); axm.imshow(img); axm.axis("off")
    T(0.5, y + bh_ + 0.02, "The verb map (full size in the PNG). Illustration only.", 6.5, c="#666")
    x2 = 4.1; yy = y
    T(x2, yy, "Honest limits", 10.5, "bold"); yy += 0.24
    yy = P(x2, yy, "A general sentence model places verbs by topic more than by risk. On dev data it found about half of unseen risky verbs at a 4 percent false-hold rate on everyday verbs. On test it held 24 of 40 alone, 27 with the rest of the gate. Verbs such as hail, stake, lease and engage sit with ordinary senses. It can false-hold a harmless order that sits in a risky region (fluff, crumble).", 62, fs=8.1, lh=0.162)
    yy += 0.1; T(x2, yy, "What held up", 10.5, "bold"); yy += 0.24
    yy = P(x2, yy, "Geometry reached verbs no dictionary family lists: unseen risky verbs went from 6 to 27 of 40 with 0 false holds on 80 clean pages, 0 holds lifted, and a deterministic, replayable log.", 62, fs=8.1, lh=0.162)
    T(0.5, 10.93, f"RESULTS.md and nym0_search_gate_v1_4.zip (sha256 in the .sha256 file).  PREREG sha256 {open(ROOT/'PREREG.sha256').read().split()[0][:16]}...  SCORE.json sha256 {SCORE_HASH[:16]}...", 6.8, c="#888")
    return fig
SCORE_HASH = __import__("hashlib").sha256((ROOT/"out"/"SCORE.json").read_bytes()).hexdigest()
tl = json.load(open(ROOT/"data"/"TEST_TEMPLATE_LOCK.json")); keyed = {t["text"]: t for t in tl["templates"]}
MISSV = [keyed[m["template"]]["key_verb"] for m in sec["test_misses_v1_4"]]
fig = onepager()
fig.savefig(ROOT/"nym0_search_gate_v1_4_onepager.png", facecolor="white")
with PdfPages(ROOT/"nym0_search_gate_v1_4_onepager.pdf") as pdf: pdf.savefig(fig)
plt.close(fig); print("ok")
