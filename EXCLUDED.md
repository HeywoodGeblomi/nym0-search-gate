# What is not in git, and why

Nothing here was edited. Files were left out only because they are binary or large (kept out of git to keep the repo light and under GitHub file limits), or out of scope. Every left-out file is still covered by the build's SHA256SUMS / FREEZE.sha256, so missing ones show as missing, never as changed.

## Binary or larger than 1.5 MB (restore with `scripts/fetch_models.sh`, or take them from the container image)

| File | Reason and sha256 |
|---|---|
| `v1_6/bin/nym0asgate` | binary 776624, sha256 c5538ad4b7eb5f745117ac4567bb21b368387c3f2920fa656c1632265b7fa84f |
| `v1_6/data/dev_v16.jsonl` | size 9651352, sha256 91a337bb2d1869af1a6262c4738750e08993748fd84817c9893ebee989ece10e |
| `v1_6/data/pool_v16.jsonl` | size 1680401, sha256 3dbfd4cef3fa7ab63bad60682db3550770b0c70d64f3c7e70fd215f56c8e9eb9 |
| `v1_6/data/topical_v16.jsonl` | size 2105863, sha256 384b4141a0386d81bd982d672feda2378a838b791f81d1afbbf83aa53ce42843 |
| `v1_6/models/map_table_v15.bin` | binary 884736, sha256 ba9c2ed617d81bf0f1dab763bc5c51e8af6d04da3e1bd330859bf4e0e01b6cfe |
| `v1_6/nym0_search_gate_v1_6_comparison.png` | binary 171178, sha256 509cf525dd88b848a652a64906182d12f7ed4dda8ee03653311a34364d7dd2f4 |
| `v1_6/nym0_search_gate_v1_6_onepager.pdf` | binary 143033, sha256 0ba3c0d335c5b34f0afbe3bd25ae67d68cf1da0dac10e32985e0faba63b8f088 |
| `v1_6/nym0_search_gate_v1_6_onepager.png` | binary 449873, sha256 0710ff2a1fffb1a8bd309a3b9c42f9d15a8530820664a31af7af9140078d2fe7 |
| `v1_6/out/abc_v16.log` | size 5074768, sha256 a96263761578901a04297ac568611c713cf031796edc1233d14e9c40c1c34e1f |
| `v1_6/out/abc_v16_pyeng.log` | size 5022669, sha256 8d99a01af601f485a234ef3284768894fca13812d35f17900ad987c9ded66b30 |
| `v1_6/out/dg_v15.log` | size 2637105, sha256 3689e69544fe372be13606c5d003de17788ec9a069cdf6c9e9faff6c5a582459 |
| `v1_6/out/dg_v16_py.log` | size 2634159, sha256 2cd26c1b60cd02a57389206970cc36a8abe76d6bcae5891e663d0ec1ec086b01 |
| `v1_6/out/dg_v16_rust.log` | size 2672820, sha256 57419cd529fae2413e55291fcbc5e67785ac9e9181d2955f33611b6e6851df0f |

Charts and one-pager PNGs are in `figures/`; PDFs of the one-pagers are left out (same content as the PNGs).
Large dev pools and the bigger hash-chained logs stay on the author's machine and in the full release zips; the scored results that use them are in `out/`.

## Out of scope (234 files)

Older baseline copies run for comparison (`baseline_*`), dev scratch runs (`out_dev/`), the tamper-test fixture tree (`out/fs_tamper_root/`), Rust build output (`front/target/`), and container build contexts. Their results are reported in RESULTS.md.

## Never included

- InjecAgent input records (upstream repository shows no license); only our counts and per-record decisions are here.
- Human-labelled data and sealed sets (none were used in this work).
- The all-MiniLM-L6-v2 ONNX file (90 MB): fetched from Hugging Face at a pinned revision and checked against sha256 `6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452`.
