#!/usr/bin/env python3
"""Dev-only numbers for the instruction check (reported as dev, not as test)."""
import json, sys, collections, hashlib
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT/"src_py"))
from instruction_check import InstructionCheck
ic = InstructionCheck(ROOT/"models"/"verb_families_v1_3.json")
dev = [json.loads(l) for l in open(ROOT/"data"/"dev_set.jsonl")]
c = collections.Counter()
for r in dev:
    c[(r["family"], ic.check(r["text"])[0])] += 1
fam = {}
for (f, h), n in c.items(): fam.setdefault(f, {"hold": 0, "allow": 0})["hold" if h else "allow"] = n
real = {}
for name in ("learning_pool", "dev_fp_pages"):
    rows = [json.loads(l) for l in open(ROOT/"data"/f"{name}.jsonl")]
    real[name] = {"pages": len(rows), "false_holds": sum(ic.check(r["text"])[0] for r in rows)}
dev2 = {"file": "dev2_phrasings.txt", "n": 0, "missed": []}
for l in open(ROOT/"data"/"dev2_phrasings.txt"):
    l = l.rstrip("\n"); l = l.encode().decode("unicode_escape") if "\\u" in l else l
    dev2["n"] += 1
    if not ic.check(l)[0]: dev2["missed"].append(l)
out = {"by_family_instruction_check_alone": fam, "real_clean_pages": real, "dev2_second_batch": {"n": dev2["n"], "held": dev2["n"] - len(dev2["missed"]), "missed": dev2["missed"]}}
(ROOT/"out"/"DEV_RESULTS.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
