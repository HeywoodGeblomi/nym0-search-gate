import sys, json, pickle
sys.path.insert(0,'.')
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
from map_check import MapCheck
mc = MapCheck(ROOT/"models"/"verb_families_v1_3.json", ROOT/"models")
out = {}
for fn in ("learning_pool", "dev_fp_pages"):
    rows = [json.loads(l) for l in open(ROOT/"data"/f"{fn}.jsonl")]
    out[fn] = [[(v, why) for v, why in mc.candidates(r["text"])] for r in rows]
    print(fn, len(rows), sum(len(x) for x in out[fn]), flush=True)
pickle.dump(out, open("/tmp/page_cands.pkl", "wb"))
