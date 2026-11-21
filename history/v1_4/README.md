# Nym-0 Search Gate v1.4

A hold-by-default safety gate for the web search results an AI agent reads. Built on Search Gate v1.3 (the v1.2 classifier plus the Gerund-0 and Synonym-0 instruction check), with a new hold-only "verb meaning map" check. Author: Heywood Geblomi (Walter Howard).

Result in one line: MISS on two primary bars. 73 of 80 planted injections held (bar 76; v1.3 held 67 on the same set) and 27 of 40 held-out unseen risky verbs held (bar 28; v1.3 held 6), with 0 of 80 clean results falsely held and every other primary criterion met. See `RESULTS.md`.

What is new (details in `PREREG.md`): `src_py/map_check.py` finds the verb of every order addressed to the reader or agent (the Gerund-0 clause finder), places the verb, or a short phrase like "make a call to", in the meaning space of the frozen all-MiniLM-L6-v2 sentence model (ONNX, CPU, offline), and holds it when it sits nearer one of eight risky verb regions than everyday verbs, by a threshold set on dev data only. All decisions use the full 384 dimensions. The 2D picture is for illustration. It only adds holds, never lifts one. The Rust front door logs the check's reasons (`mapc`) and the model tag (`mapm`), so replay stays exact. If the check raises an error, the gate holds.

## How to run (three commands)
From this directory. Needs Python 3 with NumPy and onnxruntime (for the map check); the Rust binary `bin/nym0asgate` is included. Create the folder `run` first if it is missing (`mkdir -p run`).

```
python3 worker/fallback_worker.py --socket run/worker.sock --pidfile run/worker.pid &
python3 worker/classifier_worker.py --socket run/classifier.sock --pidfile run/classifier.pid --weights models/classifier_v1_2.json &
bin/nym0asgate batch data/test_set.jsonl --out /tmp/out.jsonl --log /tmp/decisions.log --sandbox /tmp/sandbox --sock run/worker.sock --clf-sock run/classifier.sock --weights models/classifier_v1_2.json --root "$PWD"
```

The classifier worker loads the instruction check and the map check from `models/` (`verb_families_v1_3.json`, `verbmap_params.json`, `verb_lexicon_all.txt`, `encoder/`). The encoder files are hash checked at load. Check the log with `bin/nym0asgate verify /tmp/decisions.log --root "$PWD"` and `bin/nym0asgate replay /tmp/decisions.log --root "$PWD"`. Try the check alone: `echo "Kindly dispatch the file to the reviewer." | python3 src_py/map_check.py`. To redraw the pictures (needs matplotlib, umap-learn, adjustText, scikit-learn): `python3 src_py/render_map_v14.py` and `python3 src_py/render_visuals_v14.py`. `src_py/run_official_v14.py` refuses to run again because `out/SCORE.json` exists.

## Layout
- `PREREG.md`, `PREREG.sha256`, `PREREG.timestamp`: the plan with numeric bars, hashed before any test data. `FREEZE.sha256`: hashes of the frozen gate, checks, models and dev files (before the test queries and templates). `FREEZE2_TEST.sha256`: hashes of the test locks and test set. `DEVIATIONS.md`.
- `src_py/`: `map_check.py` (the check), `verbmap.py` (WordPiece reader and encoder wrapper), `verbmap_seeds.py` (seed verbs, dev lists), `dev_map.py`, `dev_report_v14.py`, `lock_test_inputs_v14.py`, `fetch_build_test_v14.py`, `run_official_v14.py`, `render_map_v14.py`, `render_visuals_v14.py`, plus the v1.3 files.
- `data/`: dev set and pages, locks (`TEST_*`, `VERB_LOCK.json`), `test_set.jsonl`, `slice_set.jsonl`, `SEPARATION_CHECK.json`, fail-safe slices, copies of earlier sets for secondary scoring.
- `models/`: classifier (unchanged), tool registry, `verb_families_v1_3.json`, `verbmap_params.json`, `verb_lexicon_all.txt`, `encoder/`.
- `front/`: Rust source of the front door (std only). `baseline_v1_1/`, `baseline_v1_2/`, `baseline_v1_3/`: frozen earlier builds used for the before columns.
- `out/SCORE.json` (the one official score), `out/DEV_RESULTS.json`, `out/dry_run/` (pre-freeze dry run, summary only), logs.
- `RESULTS.md`, `nym0_search_gate_v1_4_verb_map.png`, `nym0_search_gate_v1_4_threshold_chart.png`, `nym0_search_gate_v1_4_comparison_chart.png`, `nym0_search_gate_v1_4_onepager.pdf` and `.png`.

Model: all-MiniLM-L6-v2 (Apache-2.0), file hashes in `RESULTS.md`. Public Wikipedia data and synthetic data only. Nothing was pushed or posted. HeywoodGeblomi repos, `lucas_gated_store.json`, the Dual Residual floors, `/workspace/pg_v1_7_portable` and every earlier build folder were not touched.
