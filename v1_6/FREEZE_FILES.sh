#!/bin/sh
# lists every file frozen before the independent test set was opened (relative to the build folder)
cd "$(dirname "$0")"
{ ls PREREG.md bin/nym0asgate worker/*.py worker/*.sh front/Cargo.toml front/src/*.rs baseline_v1_4/bin/nym0asgate baseline_v1_5/bin/nym0asgate
  ls models/*.json models/*.txt models/*.bin models/encoder/* models/*.sha256
  ls src_py/*.py
  ls data/*.jsonl data/*.txt data/VERB_LOCK.json
  ls out/DEV_SUMMARY_v16.txt out/DEV_CONFIGS_v16.json out/PARITY_dev_phrases.json out/dev_gate_run.txt out/dev_ablate.txt; } | sort
