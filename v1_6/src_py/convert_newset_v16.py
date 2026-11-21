#!/usr/bin/env python3
"""Written after the independent test set was opened (disclosed in DEVIATIONS.md). Converts nothing in the text: it copies test_set.jsonl, adds key_verb and category fields to the unseen-verb records
(copied from unseen_verb_meta.jsonl), checks that every text is byte-identical, writes data/new16_all.jsonl and data/NEWSET.json, and runs the separation check against all dev data."""
import json, hashlib, re, unicodedata
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; DATA = ROOT/"data"; SRC = Path("/workspace/frontier_pivot/search_gate_v1_6_testset")
def jl(p): return [json.loads(l) for l in open(p) if l.strip()]
def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def norm(t): return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", t)).strip().lower()
ts = jl(SRC/"test_set.jsonl"); im = {r["id"]: r for r in jl(SRC/"injection_meta.jsonl")}; cm = {r["id"]: r for r in jl(SRC/"clean_meta.jsonl")}; um = {r["id"]: r for r in jl(SRC/"unseen_verb_meta.jsonl")}
inj_f = {r["id"]: r for r in jl(SRC/"injected_120.jsonl")}; cl_f = {r["id"]: r for r in jl(SRC/"clean_120.jsonl")}; un_f = {r["id"]: r for r in jl(SRC/"unseen_verb_60.jsonl")}
out = []; NS = {"records": str(DATA/"new16_all.jsonl"), "source_dir": str(SRC), "source_sha256sums": hashlib.sha256((SRC/"SHA256SUMS").read_bytes()).hexdigest(), "source_test_set_sha256": hashlib.sha256((SRC/"test_set.jsonl").read_bytes()).hexdigest(),
                "injected": [], "clean": [], "unseen": [], "family": {}, "key_verb": {}, "disguise": {}, "placement": {}, "clean_source": {}, "category": {}}
for r in ts:
    i = r["id"]; r = dict(r)
    if r["gold"] == "ALLOW":
        assert i in cl_f and cl_f[i]["untrusted_text"] == r["untrusted_text"]; NS["clean"].append(i); NS["clean_source"][i] = cm[i]["kind"]
    elif r.get("injection_family") == "unseen_verb":
        assert i in un_f and un_f[i]["untrusted_text"] == r["untrusted_text"]; NS["unseen"].append(i); m = um[i]
        r["key_verb"] = m["phrase"]; r["category"] = m["category"]; NS["key_verb"][i] = m["phrase"]; NS["category"][i] = m["category"]; NS["placement"][i] = m["placement"]; NS["disguise"][i] = m["frame"]; NS["clean_source"][i] = m["page_kind"]; NS["family"][i] = "unseen_verb:" + m["category"]
    else:
        assert i in inj_f and inj_f[i]["untrusted_text"] == r["untrusted_text"]; NS["injected"].append(i); m = im[i]
        NS["family"][i] = m["category"]; NS["key_verb"][i] = m["verb_phrase"]; NS["disguise"][i] = m["disguise"]; NS["placement"][i] = m["placement"]
    out.append(r)
assert len(NS["injected"]) == 120 and len(NS["clean"]) == 120 and len(NS["unseen"]) == 60
(DATA/"new16_all.jsonl").write_text("".join(json.dumps(r, separators=(",", ":"), ensure_ascii=False) + "\n" for r in out))
for a, b in zip(ts, jl(DATA/"new16_all.jsonl")): assert a["untrusted_text"] == b["untrusted_text"] and a["id"] == b["id"] and a["gold"] == b["gold"]
NS["sha256"] = hashlib.sha256((DATA/"new16_all.jsonl").read_bytes()).hexdigest()
json.dump(NS, open(DATA/"NEWSET.json", "w"), indent=1)
# separation check: text hashes (first 300 chars normalised), URLs and titles against every dev file
dev_u, dev_t, dev_h = {}, {}, {}
def add(src, u, t, text):
    if u: dev_u.setdefault(u, src)
    if t: dev_t.setdefault(norm(t), src)
    if text: dev_h.setdefault(sha(norm(text)[:300]), src)
for f in ("pool_v16", "topical_v16", "learning_pool", "dev_fp_pages"):
    for r in jl(DATA/f"{f}.jsonl"): add(f, r.get("url") or r.get("source_url"), r.get("title") or r.get("source_title"), r.get("text") or r.get("untrusted_text"))
for f in ("new_all", "test_set", "slice_set", "V13_test_set", "dev_set"):
    for r in jl(DATA/f"{f}.jsonl"): add(f, r.get("source_url"), r.get("source_title"), r.get("untrusted_text") or r.get("text"))
for r in jl(DATA/"dev_v16.jsonl"): add("dev_v16", r.get("url"), None, r["text"])
hits = {"url": [], "title": [], "text_hash": []}
for r in ts:
    u, t, h = r.get("source_url"), r.get("source_title"), sha(norm(r["untrusted_text"])[:300])
    if u in dev_u: hits["url"].append((r["id"], dev_u[u], u))
    if t and norm(t) in dev_t: hits["title"].append((r["id"], dev_t[norm(t)], t))
    if h in dev_h: hits["text_hash"].append((r["id"], dev_h[h]))
chk = {"records": len(ts), "overlap_counts": {k: len(v) for k, v in hits.items()}, "overlaps": hits, "dev_urls": len(dev_u), "dev_titles": len(dev_t), "dev_text_hashes": len(dev_h), "texts_byte_identical_to_source": True}
json.dump(chk, open(DATA/"SEPARATION_CHECK_v16.json", "w"), indent=1)
print(NS["sha256"], chk["overlap_counts"], json.dumps(hits)[:1500])
