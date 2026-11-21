#!/usr/bin/env python3
"""Export the v1.5 map decision tables for the Rust front door: seed and anchor vectors (v1.4 rule), the probe weights, thresholds, the seed list, and the sha256 of
every file the Rust map engine reads. Build-time only. Run after build_v15_tables.py and export_encoder_v15.py."""
import sys, json, hashlib, numpy as np
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT/"src_py"))
from map_check15 import MapCheck15
md = ROOT/"models"
mc = MapCheck15(md/"verb_families_v1_3.json", md)
P = json.loads((md/"verbmap_v15.json").read_text())["probe"]
buf = []; regions = []; n = 0
for r in mc.regions:
    S = mc.S[r].astype("<f4"); regions.append({"name": r, "start": n, "n": int(S.shape[0])}); n += S.shape[0]; buf.append(S)
A = mc.A.astype("<f4"); anchors = {"start": n, "n": int(A.shape[0])}; n += A.shape[0]; buf.append(A)
wv_off = n * 384; wg_off = wv_off + 384
tail = np.concatenate([np.array(P["weights_verb"]), np.array(P["weights_gloss"])]).astype("<f4")
raw = b"".join(x.tobytes() for x in buf) + tail.tobytes()
(md/"map_table_v15.bin").write_bytes(raw)
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
hdr = {"version": "v1.5", "dim": 384, "frame": mc.frame, "topk": mc.k, "tau": mc.tau, "thr": P["thr"], "bias": P["bias"], "regions": regions, "anchors": anchors,
       "wv_offset_floats": wv_off, "wg_offset_floats": wg_off, "seedlist": sorted(mc.seedlist),
       "files": {f: sha(md/f) for f in ["map_table_v15.bin", "encoder_f32.bin", "encoder_f32.index.json", "vocab.txt", "verb_gloss_f32.bin", "verb_gloss_index.txt"]},
       "sources": {"verbmap_params.json": sha(md/"verbmap_params.json"), "verbmap_v15.json": sha(md/"verbmap_v15.json"), "onnx__model.onnx": sha(md/"encoder"/"onnx__model.onnx")}}
(md/"map_table_v15.json").write_text(json.dumps(hdr, indent=1))
print("map table", len(raw), sha(md/"map_table_v15.bin"), "header", sha(md/"map_table_v15.json"))
