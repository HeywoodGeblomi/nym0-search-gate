# Nym-0 Search Gate v1.6

Author: Heywood Geblomi (Walter Howard). Written 2026-11-20 (America/New_York). This write-up says "learning", not "training".

v1.6 is v1.5 with three changes aimed at harmless pages full of commands (recipes, how-tos, travel guides, rules): a clause-finder and system-tag fix, a how-to page waiver, and a refit classifier. The safety core (hard holds, fail-safe holds, replay, the Rust front door and the v1.5 meaning map with its Rust port) is unchanged. v1.6 is hold-only relative to the safety core: it can lift a hold only from the classifier, the instruction check or the meaning map, and only on a page that passed the how-to test with no agent-aimed cue (or where the refit classifier no longer fires).

**Result: MISS.** Clean false holds 17 of 120 (bar 6). Everything else hit: injected 108 of 120 (bar 108), unseen-verb 55 of 60 (bar 42), InjecAgent A 1054, C 0, B 1047 (bar 1026), parity 100 percent, safety core all held. Details: RESULTS.md.

## Files
- PREREG.md, PREREG.sha256, PREREG.timestamp: the plan, hashed 07:55:39 EST before development. sha256 a886ba68...1e26.
- FREEZE.sha256, FREEZE.sha256.sha256, FREEZE.timestamp, FREEZE_FILES.sh: the 145 files frozen at 08:28:25 EST before the independent set was opened.
- RESULTS.md, DEVIATIONS.md: results (MISS first) and every deviation and disclosure, in order.
- out/SCORE.json (raw run), out/RESULTS_v16.json (scored), out/SENSITIVITY_v16.json, out/PARITY_dev_phrases.json, out/DEV_SUMMARY_v16.txt, out/DEV_CONFIGS_v16.json, out/dev_gate_run.txt, out/*.log and *.out.jsonl (every decision and the hash-chained logs).
- nym0_search_gate_v1_6_comparison.png (v1.4, v1.5, v1.6 on the same set), nym0_search_gate_v1_6_onepager.pdf and .png.
- bin/nym0asgate (Rust front door, v1.6), front/ (Rust source), worker/ (classifier worker, fallback worker), src_py/ (Python: clause finder, how-to test and waiver `howto16.py`, map check, runner, scorer, dev scripts), models/ (v1.5 map and encoder, classifier_v1_2.json, **classifier_v1_6.json**), data/ (dev pools, old sets, the converted new set data/new16_all.jsonl).
- baseline_v1_4/, baseline_v1_5/: frozen older versions, run on the same records for the comparison.

## How it works (v1.6 changes)
1. Clause finder: "Please delete." (a verb with nothing after it) is now an order.
2. System tags ([SYSTEM], <system>, [INST], <<SYS>>, "ADMIN:", ...) mark the text after them as addressed to the agent.
3. New hold rules (hold-only): an order verb with a resource noun (files, credentials, accounts, money, messages, code); unknown verbs after please or kindly; hyphen, compound and noun-phrase variants of a verb for the map.
4. How-to waiver: a page is waived when at least 30 percent of its sentences open with a command verb and nothing on it is aimed at an agent (no AI or assistant word, override phrase, system tag, hidden text, URL, email, agent phrase, resource or action object). The waiver is logged in the hash chain (field `relax`) and can lift only classifier, instruction-check and map holds.
5. Classifier refit: v1.2 recipe plus the new pool of command-heavy public pages and 2,363 topical Wikipedia pages as clean examples, with planted injections as positives. Threshold 0.55.
Not in the Rust port (stated): the clause finder, the how-to test and the waiver decision stay in Python.

## Run it
Needs python3 with numpy, onnxruntime; Rust is only needed to rebuild (`cd front && cargo build --release`, std only).
- If your unzip tool drops file permissions, run `chmod +x bin/nym0asgate baseline_v1_4/bin/nym0asgate baseline_v1_5/bin/nym0asgate` first.
- Verify a full unpack: `sh verify_package.sh` (checks SHA256SUMS, PREREG hash, frozen files, then re-runs the gate on the new set and compares byte for byte with out/new_v16.out.jsonl).
- Slim zip: code, results, data and hashes, **without** the encoder ONNX file, models/encoder_f32.bin and models/verb_gloss_f32.bin; it cannot run the gate (see SLIM_README.txt).
- In the full zip, baseline_v1_5/models/{encoder, encoder_f32.bin, verb_gloss_f32.bin} are left out (they are byte-identical to models/); `verify_package.sh` restores them as symlinks.

## Data and rules
Public (Wikipedia family, Wikibooks, Wikivoyage, Wikisource) or synthetic only. No human 200 labels, no sealed set. Nothing sent or pushed. The independent test set (/workspace/frontier_pivot/search_gate_v1_6_testset/) was written by a separate author and opened after the freeze.

## Hashes
- bin/nym0asgate sha256 c5538ad4b7eb5f745117ac4567bb21b368387c3f2920fa656c1632265b7fa84f
- models/classifier_v1_6.json c7c30aec79b029e17761ab8684ea51615233f8615b20f92a2e8d337c44f659d5
- data/new16_all.jsonl 4ddaa08867da43cbbb0b411fc58019bcaf04310a68157be33b553dbc4334ab48 (source test_set.jsonl 6ef00fd88c2e755bcd21e1f58742c8d8aa81d20d9c79aafdbb104f66982670fc)
- FREEZE.sha256 779aee1442bbd0b8c02038a6f29b881aff1681235384c71953ea7faaa61518dd
- out/SCORE.json bbc791ba888b5f0a67c1fb4a8a75c772041b17b782bacb0010f1a2cb15c7b511; out/RESULTS_v16.json 0759ef2df94ae99120a4acf14b24f85e3369117773ab6fd7d34bd8b9acda784e

## Package check (done 2026-11-20 08:36 EST)
Full zip unpacked fresh: SHA256SUMS, PREREG hash and all 145 frozen files OK; the gate re-run on the new set matched out/new_v16.out.jsonl byte for byte (300 records, replay exact, tamper caught). The slim zip passes `sha256sum -c SHA256SUMS_SLIM` and is under 25 MB.
