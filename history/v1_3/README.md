# Nym-0 Search Gate v1.3

A hold-by-default safety gate for the web search results an AI agent reads. Built from Search Gate v1.2 plus a new hold-only instruction check made from Heywood's Gerund-0 and Synonym-0 parts. Author: Heywood Geblomi (Walter Howard).

Result in one line: MISS. The gate held 65 of 80 new planted injections (bar 76), up from 33 of 80 for v1.2 on the same set, with 1 of 80 clean results falsely held and every other primary criterion met. InjecAgent Record B is 985 of 1054 (target 1000, not reached). See `RESULTS.md`.

What is new (details in `PREREG.md`): `src_py/instruction_check.py` holds an order addressed to the reader or agent whose verb is in a risky family (send, delete, cancel, approve, transfer, grant ...), with the families fanned out from a seed list through WordNet (frozen in `models/verb_families_v1_3.json`). Hidden text is scanned too. It only adds holds, never lifts one, and runs next to the v1.2 classifier. If it raises an error the gate holds.

## How to run (three commands)
From this directory (needs Python 3 with NumPy; the Rust binary `bin/nym0asgate` is included):

```
python3 worker/fallback_worker.py --socket run/worker.sock --pidfile run/worker.pid &
python3 worker/classifier_worker.py --socket run/classifier.sock --pidfile run/classifier.pid --weights models/classifier_v1_2.json &
bin/nym0asgate batch data/test_set.jsonl --out /tmp/out.jsonl --log /tmp/decisions.log --sandbox /tmp/sandbox --sock run/worker.sock --clf-sock run/classifier.sock --weights models/classifier_v1_2.json --root "$PWD"
```

The classifier worker loads the instruction check automatically. Check the log with `bin/nym0asgate verify /tmp/decisions.log --root "$PWD"` and `bin/nym0asgate replay /tmp/decisions.log --root "$PWD"`. To try the check alone: `echo "Please cancel my subscription." | python3 src_py/instruction_check.py`. To use your own tool catalog edit `models/tool_registry.txt` or set `NYM0_REGISTRY`.

## Layout
- `PREREG.md`, `PREREG.sha256`, `PREREG.timestamp`: the plan with numeric bars, hashed before any test data. `FREEZE.sha256`: hashes of the frozen gate, check, table and dev files (before the test queries and templates). `FREEZE2_TEST.sha256`: hashes of the test locks and test set. `DEVIATIONS.md`.
- `src_py/`: `instruction_check.py` (the check), `build_families.py` (WordNet fan-out, build time only, needs nltk), `make_dev.py`, `eval_dev.py`, `dev_report.py`, `fetch_dev_fp.py`, `lock_test_inputs_v13.py`, `fetch_build_test_v13.py`, `run_official_v13.py` (refuses to run twice), `render_visuals_v13.py`, plus the v1.2 files.
- `data/`: dev set and dev pages, learning pool, locks (`TEST_*`), `test_set.jsonl`, `SEPARATION_CHECK.json`, fail-safe slices.
- `models/`: classifier (unchanged from v1.2), tool registry, `verb_families_v1_3.json`.
- `front/`: Rust source of the front door (std only). `baseline_v1_1/`, `baseline_v1_2/`: frozen earlier builds used for the before columns.
- `out/SCORE.json` (the one official score), `out/DEV_RESULTS.json`, `out/dry_run/` (dev dry run), logs.
- `RESULTS.md`, `nym0_search_gate_v1_3_chart.png`, `nym0_search_gate_v1_3_onepager.pdf` and `.png`.

Public Wikipedia data and synthetic data only. Nothing was pushed or posted. HeywoodGeblomi repos, `lucas_gated_store.json`, the Dual Residual floors, `/workspace/pg_v1_7_portable` and every earlier build folder were not touched.
