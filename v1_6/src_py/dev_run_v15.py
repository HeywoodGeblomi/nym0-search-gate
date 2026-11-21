#!/usr/bin/env python3
"""Dev end-to-end run of v1.5 on a record file with the Rust map engine and with the Python reference engine; prints held counts and compares record by record."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runlib import *
inp = Path(sys.argv[1]); tag = sys.argv[2]
recs = jl(inp); W = ROOT/"models"/"classifier_v1_2.json"
res = {}
for eng in ("rust", "python"):
    with Stack(ROOT, W, f"{tag}_{eng}", clf_args=["--map-engine", eng]) as st:
        args_extra = ["--map-engine", eng]
        out = ROOT/"out"; outp, logp, sb = out/f"{tag}_{eng}.out.jsonl", out/f"{tag}_{eng}.log", out/f"{tag}_{eng}_sb"
        for p in (outp, logp):
            if p.exists(): p.unlink()
        r = gate(BIN, ROOT, "batch", str(inp), "--out", str(outp), "--log", str(logp), "--sandbox", str(sb), "--sock", str(st.ws), "--clf-sock", str(st.cs), "--weights", str(W), *args_extra)
    outs = load_out(outp); s = summarize(recs, outs, sb); res[eng] = (outs, s, logp)
    print(eng, r.returncode, s["by"], flush=True)
a, b = res["rust"][0], res["python"][0]
diff = [i for i in a if a[i].get("decision") != b.get(i, {}).get("decision") or a[i].get("layer") != b.get(i, {}).get("layer")]
print("record-level differences rust vs python engine:", len(diff), diff[:5])
v = gate(BIN, ROOT, "mapverify", str(res["rust"][2])); print(v.stdout.strip()[-300:])
