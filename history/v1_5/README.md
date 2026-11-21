# Nym-0 Search Gate v1.5

Author: Heywood Geblomi (Walter Howard). Times are America/New_York. This write-up says "learning", not "training".

**Result: MISS.** Injected held 91 of 120 (bar 108). Clean false holds 35 of 120 (bar 2). Unseen verbs 42 of 60 (bar 42, hit at the bar, and see DEVIATIONS.md item 7). InjecAgent A 1054, B 1026, C 0, parity 100 percent, safety core intact. Read RESULTS.md first.

## What this is
A gate that reads a search result an agent is about to open and holds it when the text gives the agent an order to do something risky. Hold-only: it can hold, never lift another layer's hold. It tests a safety gate, not any vendor's search model. Public and synthetic data only.

## What v1.5 adds over v1.4
1. A wider verb map: 12 risky regions (v1.4 had 8), 422 listed risky verbs, 1028 everyday contrast verbs, and a learned linear probe on the verb vector plus a WordNet gloss vector. Hold when the verb is on the list, or the v1.4 margin rule fires, or the probe fires.
2. A Rust port of the map decision (WordPiece, the MiniLM encoder forward pass, scores, margin, probe), std only, from an exported f32 weight table with hash checks. The Python clause finder (Gerund-0 and Synonym-0) still finds the orders and hands the phrases over. Rust and Python agree on every record and phrase checked.
3. Small clause finder changes: extra order frames, a modal filter, an ASCII filter.

## Folder
- RESULTS.md, PREREG.md (+ .sha256, .timestamp), DEVIATIONS.md, out/RESULTS_v15.json, out/SCORE.json (raw run), out/DEV_*.json, out/PARITY_dev_phrases.json
- nym0_search_gate_v1_5_verb_map.png, nym0_search_gate_v1_5_comparison.png, nym0_search_gate_v1_5_onepager.pdf / .png
- bin/nym0asgate (Rust front door), front/ (Rust source), worker/, src_py/ (reference, dev and scoring scripts), models/, data/
- baseline_v1_1 .. baseline_v1_4: the earlier versions, run on the same sets by the official runner
- FREEZE.sha256: 119 files hashed before the test set was opened

## Run it
```
cd <this folder>
python3 -m pip install onnxruntime numpy        # only the Python reference needs onnxruntime
# batch on a set of records (default map engine: rust)
python3 src_py/run_official_v15.py              # refuses to rerun: SCORE.json exists
bin/nym0asgate batch <records.jsonl> --out out.jsonl --log out.log ...   # see src_py/runlib.py for the exact arguments
python3 src_py/score_v15.py                     # recompute RESULTS_v15.json from SCORE.json
sha256sum -c FREEZE.sha256                      # frozen design check
bash verify_package.sh                          # fresh-unpack check used for this zip
```
The Rust engine is the default (`--map-engine rust`). `--map-engine python` runs the Python reference (needs onnxruntime and models/encoder/). models/encoder_f32.bin (90 MB) is the Rust encoder table.

## The slim zip
nym0_search_gate_v1_5_slim.zip is under 25 MB. It has everything except the ONNX model, models/encoder_f32.bin and front/target. It holds the code, results, charts, data and hashes, but **it cannot run the gate** without the model files. Use the full zip for that.

## Honest limits
Two primary misses (P1, P3). The P2 hit is at the bar and rests on a converter written after the set was opened. 8 of the 18 unseen misses are records where the clause finder found no order. All 7 system_tag injections are missed. The 35 clean false holds come from older layers on recipe pages. See RESULTS.md.
