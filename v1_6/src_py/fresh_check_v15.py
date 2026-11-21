#!/usr/bin/env python3
"""Fresh-unpack check: re-run the v1.5 gate (Rust map engine) on the new set from THIS folder and compare the output byte for byte with out/new_v15.out.jsonl.
Needs python3 with onnxruntime and numpy (the classifier and instruction check workers). Does not touch out/SCORE.json."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runlib import *
W12 = ROOT/"models"/"classifier_v1_2.json"
NEW = DATA/"new_all.jsonl"; recs = jl(NEW)
with Stack(ROOT, W12, "fresh", clf_args=["--map-engine", "rust"]) as st:
    r, outp, logp, sb = st.batch(NEW, "fresh_new", bin_path=BIN, root=ROOT)
assert r.returncode == 0, r.stderr[-300:]
mine = sha_file(outp); ref = sha_file(ROOT/"out"/"new_v15.out.jsonl")
ok, vr = verify_replay_tamper(logp, "fresh_new", BIN, ROOT)
o = load_out(outp); s = summarize(recs, o, sb)
print(json.dumps({"records": len(recs), "decided": len(o), "out_sha256": mine, "reference_sha256": ref, "byte_identical": mine == ref, "replay_and_tamper_ok": ok, "by": s["by"], "fire_weapon": s["fire_weapon_outputs"], "emitted_on_hold": s["emitted_on_hold"]}, indent=1))
sys.exit(0 if (mine == ref and ok) else 1)
