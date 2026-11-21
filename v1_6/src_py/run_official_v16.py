#!/usr/bin/env python3
"""The one official run and score of Nym-0 Search Gate v1.6. Run once. Refuses to run if a frozen hash differs or out/SCORE.json exists.
Reads data/NEWSET.json (written by the converter after the independent test set was opened): {records: file, sha256, injected: [ids], clean: [ids], unseen: [ids], everyday: [ids], family: {id: name}, verb: {id: key verb}}."""
import json, os, sys, shutil
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runlib import *
TZ = ZoneInfo("America/New_York")
def now(): return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
OUT.mkdir(exist_ok=True)
DRY = os.environ.get("NYM0_DRY") == "1"
SCORE = OUT/("DRY_SCORE.json" if DRY else "SCORE.json")
if SCORE.exists() and not DRY: raise SystemExit("SCORE.json exists: official run already done. Scored once.")
if not DRY:
    for line in open(ROOT/"FREEZE.sha256"):
        h, p = line.split(None, 1); p = p.strip()
        assert sha_file(ROOT/p) == h, f"frozen file changed: {p}"
S12 = Path("/workspace/frontier_pivot/search_gate_v1_2")
ABC = Path("/workspace/frontier_pivot/toolcall_gate_v1/data/official_ABC.jsonl")
V1SET = Path("/workspace/frontier_pivot/search_gate_test_v1/data/official_set.jsonl")
V12SET = S12/"data"/"test_set.jsonl"; V13SET = DATA/"V13_test_set.jsonl"
assert sha_file(V13SET) == "18947b04547afe45e15ac1f92ba0027eceb038e3d20e14c864ba8f681f0506c0"
assert sha_file(ABC) == "acdd2b302795472c4e365582f3840559621e47be887d11685b7eee0fd1cf41a0"
assert sha_file(V1SET) == "b45fae8eef3d34327e7b10840be43d8d52679d6b71620e90cb4ad9fc364dbd2b"
assert sha_file(V12SET) == "66a182168525399d2ff8cf914fe41dd7b41471be49ec40adf30b7db8b84c0a3d"
NS = json.load(open(DATA/("NEWSET_DRY.json" if DRY else "NEWSET.json"))); NEW = Path(NS["records"]); assert sha_file(NEW) == NS["sha256"]
OLD = DATA/"test_set.jsonl"; OLDSLICE = DATA/"slice_set.jsonl"
W16 = ROOT/"models"/"classifier_v1_6.json"; W12 = ROOT/"baseline_v1_5"/"models"/"classifier_v1_2.json"
B15 = ROOT/"baseline_v1_5"; B15BIN = B15/"bin"/"nym0asgate"
B14 = ROOT/"baseline_v1_4"; B14BIN = B14/"bin"/"nym0asgate"
res = {"started_at": now(), "hashes": {"bin_v1_6": sha_file(BIN), "bin_v1_5": sha_file(B15BIN), "bin_v1_4": sha_file(B14BIN),
       "newset": NS["sha256"], "old_test_set": sha_file(OLD), "old_slice": sha_file(OLDSLICE), "abc": sha_file(ABC), "v1_set": sha_file(V1SET), "v1_2_set": sha_file(V12SET), "v1_3_set": sha_file(V13SET),
       "classifier_v1_6": sha_file(W16), "classifier_v1_2": sha_file(W12), "howto16_py": sha_file(ROOT/"src_py"/"howto16.py"), "instruction_check_py": sha_file(ROOT/"src_py"/"instruction_check.py"), "pipeline_rs": sha_file(ROOT/"front"/"src"/"pipeline.rs"), "map_table_v15.json": sha_file(ROOT/"models"/"map_table_v15.json"), "map_table_v15.bin": sha_file(ROOT/"models"/"map_table_v15.bin"), "encoder_f32.bin": sha_file(ROOT/"models"/"encoder_f32.bin"),
       "verbmap_v15.json": sha_file(ROOT/"models"/"verbmap_v15.json"), "map_check15_py": sha_file(ROOT/"src_py"/"map_check15.py"), "mapcheck_rs": sha_file(ROOT/"front"/"src"/"mapcheck.rs")}}
new = jl(NEW); old = jl(OLD); oslc = jl(OLDSLICE); ds_v1 = jl(V1SET); ds_v12 = jl(V12SET); ds_v13 = jl(V13SET); abc = jl(ABC)
ALL = {}
def run_set(tag, recs, inp, weights, root, binp, clf_args=(), bin_args=()):
    with Stack(root, weights, tag, clf_args=clf_args) as st:
        out = root/"out"; out.mkdir(exist_ok=True)
        outp, logp, sb = out/f"{tag}.out.jsonl", out/f"{tag}.log", out/f"{tag}_sb"
        for p in (outp, logp):
            if p.exists(): p.unlink()
        r = gate(binp, root, "batch", str(inp), "--out", str(outp), "--log", str(logp), "--sandbox", str(sb), "--sock", str(st.ws), "--clf-sock", str(st.cs), "--weights", str(weights), *bin_args)
    outs = load_out(outp); s = summarize(recs, outs, sb)
    ok, vr = verify_replay_tamper(logp, tag, binp, root)
    ALL[tag] = outs
    return {"returncode": r.returncode, "panic": "panicked" in (r.stderr or "").lower(), "decided": len(outs), "total": len(recs), **s, "log_ok": ok, "log_detail": vr, "log_sha256": sha_file(logp), "out_sha256": sha_file(outp), "stderr_tail": (r.stderr or "")[-200:]}
def v16(tag, recs, inp, eng="rust"): return run_set(f"{tag}_v16" + ("" if eng == "rust" else "_pyeng"), recs, inp, W16, ROOT, BIN, clf_args=["--map-engine", eng], bin_args=["--map-engine", eng])
def v15(tag, recs, inp): return run_set(f"{tag}_v15", recs, inp, W12, B15, B15BIN, clf_args=["--map-engine", "rust"], bin_args=["--map-engine", "rust"])
def v14(tag, recs, inp): return run_set(f"{tag}_v14", recs, inp, W12, B14, B14BIN, clf_args=["--models", str(B15/"models")])
SETS = [("new", new, NEW, ("16", "15", "14")), ("old", old, OLD, ("16", "15", "14")), ("oldslice", oslc, OLDSLICE, ("16", "15", "14")),
        ("v13set", ds_v13, V13SET, ("16", "15")), ("v12set", ds_v12, V12SET, ("16", "15")), ("v1set", ds_v1, V1SET, ("16", "15")), ("abc", abc, ABC, ("16", "15", "14"))]
fn = {"16": v16, "15": v15, "14": v14}
for tag, recs, inp, vs in SETS:
    for v in vs: res[f"{tag}_v{v}"] = fn[v](tag, recs, inp)
    print("done", tag, flush=True)
# python-engine runs for record-level parity (the Python reference decides the map check)
for tag, recs, inp in (("new", new, NEW), ("old", old, OLD), ("oldslice", oslc, OLDSLICE), ("abc", abc, ABC)):
    res[f"{tag}_v16_pyeng"] = v16(tag, recs, inp, "python")
print("done python-engine runs", flush=True)
# fail-safe slice
p8 = {}
cs = jl(DATA/"p6_classifier_slice.jsonl"); slice_soft = [r for r in jl(DATA/"p6_slice.jsonl") if r["id"].startswith("p6-soft")]
def heldn(o, rs): return sum(1 for x in rs if x["id"] in o and not is_allow(o[x["id"]]))
with Stack(ROOT, W16, "fs_w", worker=False, clf=True, clf_args=["--map-engine", "rust"]) as st:
    r, outp, logp, sb = st.batch(DATA/"p6_slice.jsonl", "fs_noworker", no_restart=True)
o = load_out(outp); ids = [x["id"] for x in slice_soft]
p8["worker_missing"] = {"n": len(ids), "held": sum(1 for i in ids if i in o and not is_allow(o[i])), "acts": len(emitted(sb) & set(ids))}
with Stack(ROOT, W16, "fs_c", worker=True, clf=False) as st:
    r, outp, logp, sb = st.batch(DATA/"p6_classifier_slice.jsonl", "fs_noclf", no_restart=True)
o = load_out(outp); p8["classifier_missing"] = {"n": len(cs), "held": heldn(o, cs), "acts": len(emitted(sb))}
ovr = []
for x in [x for x in jl(DATA/"p6_slice.jsonl") if x["id"].startswith("A-dh")]:
    y = dict(x); y["override"] = "allow"; y["id"] = "ov-" + x["id"]; y["session_id"] = y["id"]; ovr.append(y)
wjl(OUT/"override_allow.jsonl", ovr)
with Stack(ROOT, W16, "fs_o", clf_args=["--map-engine", "rust"]) as st: r, outp, logp, sb = st.batch(OUT/"override_allow.jsonl", "fs_override")
o = load_out(outp); p8["override_allow_on_A"] = {"n": len(ovr), "held": heldn(o, ovr), "acts": len(emitted(sb))}
for key, flag in (("instruction_check_raises", "--instr-raise-after"), ("map_check_raises", "--map-raise-after")):
    with Stack(ROOT, W16, "fs_" + key[:1], clf_args=[flag, "0", "--map-engine", "rust"]) as st: r, outp, logp, sb = st.batch(DATA/"p6_classifier_slice.jsonl", "fs_" + key, no_restart=True)
    o = load_out(outp); p8[key] = {"n": len(cs), "held": heldn(o, cs), "acts": len(emitted(sb)), "layers": dict(Counter(v.get("layer") for v in o.values()))}
# Rust map engine unavailable: a copy of the root whose map table has one flipped byte (hash check must fail, every record must be held)
TR = OUT/"fs_tamper_root"
if TR.exists(): shutil.rmtree(TR)
(TR/"models").mkdir(parents=True); (TR/"run").mkdir(); (TR/"bin").symlink_to(ROOT/"bin"); (TR/"worker").symlink_to(ROOT/"worker"); (TR/"src_py").symlink_to(ROOT/"src_py")
for f in (ROOT/"models").iterdir():
    if f.name != "map_table_v15.bin": (TR/"models"/f.name).symlink_to(f)
b = bytearray((ROOT/"models"/"map_table_v15.bin").read_bytes()); b[1000] ^= 1; (TR/"models"/"map_table_v15.bin").write_bytes(bytes(b))
with Stack(ROOT, W16, "fs_t", clf_args=["--map-engine", "rust"]) as st:
    outp, logp = OUT/"fs_map_engine_tampered.out.jsonl", OUT/"fs_map_engine_tampered.log"
    for p in (outp, logp):
        if p.exists(): p.unlink()
    r = gate(BIN, TR, "batch", str(DATA/"p6_classifier_slice.jsonl"), "--out", str(outp), "--log", str(logp), "--sandbox", str(OUT/"fs_t_sb"), "--sock", str(st.ws), "--clf-sock", str(st.cs), "--weights", str(W16), "--no-restart", "--map-engine", "rust")
o = load_out(outp); p8["map_engine_unavailable"] = {"n": len(cs), "held": heldn(o, cs), "acts": len(emitted(OUT/"fs_t_sb")), "layers": dict(Counter(v.get("layer") for v in o.values()))}
res["p8"] = p8
# hold-only: lifted holds of v1.6 against v1.5 and v1.4 (every one is listed with its v1.5 layer)
mono = {}
for tag, recs, inp, vs in SETS:
    a16 = ALL[f"{tag}_v16"]
    for base in ("15", "14"):
        a = ALL.get(f"{tag}_v{base}")
        if a is None: continue
        mono[f"{tag}_vs_v{base}"] = {"base_held": sum(1 for r in recs if r["id"] in a and not is_allow(a[r["id"]])), "lifted": [{"id": r["id"], "gold": r["gold"], "base_layer": a[r["id"]].get("layer")} for r in recs if r["id"] in a and not is_allow(a[r["id"]]) and (r["id"] not in a16 or is_allow(a16[r["id"]]))],
                                      "newly_held_by_v16": sum(1 for r in recs if r["id"] in a and is_allow(a[r["id"]]) and r["id"] in a16 and not is_allow(a16[r["id"]]))}
res["monotone"] = mono
# parity: record level (Rust engine vs Python engine), log recompute (mapverify), and order level on every order found in the new set and InjecAgent
par = {"record_level": {}, "mapverify": {}}
for tag in ("new", "old", "oldslice", "abc"):
    a, b = ALL[f"{tag}_v16"], ALL[f"{tag}_v16_pyeng"]
    diff = [i for i in a if a[i].get("decision") != b.get(i, {}).get("decision") or a[i].get("layer") != b.get(i, {}).get("layer")]
    rdiff = [i for i in a if a[i].get("reason") != b.get(i, {}).get("reason")]
    par["record_level"][tag] = {"records": len(a), "decision_or_layer_differences": len(diff), "examples": diff[:5], "reason_text_differences_only": len(rdiff)}
    v = gate(BIN, ROOT, "mapverify", str(OUT/f"{tag}_v16.log")); par["mapverify"][tag] = json.loads(v.stdout.strip().splitlines()[-1])
sys.path.insert(0, str(ROOT/"src_py"))
import parity_v16 as PV
def txt(r): return (r.get("untrusted_text") or "") + (" " + r["proposed_args"] if r.get("proposed_args") else "")
res["parity_orders"] = []
for tag, recs in (("new", new), ("abc", abc), ("old", old), ("oldslice", oslc)):
    orders = [v for r in recs for v, why in PV.mc.candidates(txt(r))]
    res["parity_orders"].append(PV.compare(f"orders_found_in_{tag}", orders))
par["orders_total"] = sum(x["orders"] for x in res["parity_orders"]); par["orders_mismatches"] = sum(x["mismatches"] for x in res["parity_orders"])
res["parity"] = par
res["dev_parity_file"] = "out/PARITY_dev_phrases.json"
res["finished_at"] = now()
json.dump(res, open(SCORE, "w"), indent=1)
print("raw run finished; scoring is done by score_v16.py from out/SCORE.json")
