#!/usr/bin/env python3
"""Build data/dev_v16.jsonl: every dev record with group, label and split. Dev only."""
import json, random, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; DATA = ROOT/"data"
sys.path.insert(0, str(ROOT/"src_py"))
from dev16_lib import jl, split_of
import inj_gen_v16 as G
rng = random.Random(16016)
out = []
def add(group, text, label, split, **kw): out.append(dict(id=f"D{len(out):05d}", group=group, text=text, label=label, split=split, **kw))
pool = jl(DATA/"pool_v16.jsonl")
for r in pool:
    sp = split_of(r["url"]); add("pool_clean:" + r["source"], r["text"], 0, sp, url=r["url"])
    t, meta = G.plant(r["text"], rng); add("pool_inj:" + r["source"], t, 1, sp, url=r["url"], **meta)
wp = [dict(text=r["text"], url=r["url"]) for r in jl(DATA/"learning_pool.jsonl")] + [dict(text=r["text"], url=r["url"]) for r in jl(DATA/"dev_fp_pages.jsonl")]
rng.shuffle(wp)
for k, r in enumerate(wp):
    sp = split_of(r["url"]); add("wp_clean", r["text"], 0, sp, url=r["url"])
    if k < 900:
        t, meta = G.plant(r["text"], rng); add("wp_inj", t, 1, sp, url=r["url"], **meta)
# the spent v1.5 test set (dev now). groups by id prefix
new = {r["id"]: r for r in jl(DATA/"new_all.jsonl")}; NS = json.load(open(DATA/"NEWSET_v15.json"))
for i in NS["injected"]: add("v15_inj", new[i]["untrusted_text"], 1, "dev", src_id=i, family=NS["family"][i], disguise=NS["disguise"][i])
for i in NS["unseen"]: add("v15_unseen", new[i]["untrusted_text"], 1, "dev", src_id=i, verb=new[i]["key_verb"], category=new[i].get("category"))
for i in NS["everyday"]: add("v15_everyday", new[i]["untrusted_text"], 0, "dev", src_id=i, verb=new[i]["key_verb"])
for i in NS["clean"]: add("v15_clean:" + NS["clean_source"][i], new[i]["untrusted_text"], 0, "dev", src_id=i)
# older dev sets (v1.4 dev set, old main set and slice)
for r in jl(DATA/"dev_set.jsonl"): add("dev_set:" + r["family"], r["text"], 1 if r["gold"] == "HOLD" else 0, "dev", src_id=r["id"])
for tag, f in (("old", "test_set.jsonl"), ("oldslice", "slice_set.jsonl")):
    for r in jl(DATA/f): add(f"{tag}:{r['gold']}", r["untrusted_text"], 1 if r["gold"] == "HOLD" else 0, "dev", src_id=r["id"])
rng2 = random.Random(16017)
for r in jl(DATA/"topical_v16.jsonl"):       # topical Wikipedia pages (banking, email, security, smart home, robotics, cooking ...): hard clean pages
    sp = split_of(r["url"]); add("topical_clean", r["text"], 0, sp, url=r["url"], cat=r["source"])
    t, meta = G.plant(r["text"], rng2); add("topical_inj", t, 1, sp, url=r["url"], cat=r["source"], **meta)
(DATA/"dev_v16.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
from collections import Counter
print(len(out)); print(Counter((r["group"].split(":")[0], r["split"]) for r in out))
