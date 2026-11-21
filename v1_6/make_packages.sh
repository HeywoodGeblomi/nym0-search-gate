#!/bin/sh
# builds SHA256SUMS, SHA256SUMS_SLIM and the two zips (run from the build folder; output next to it)
set -e
cd "$(dirname "$0")"
NAME=nym0_search_gate_v1_6
EXC_COMMON='front/target/* run/* *_sb/* *_tamper.log out/fs_tamper_root/* *__pycache__/* *.pyc out/fresh_new* baseline_v1_5/models/encoder/* baseline_v1_5/models/encoder_f32.bin baseline_v1_5/models/verb_gloss_f32.bin SHA256SUMS SHA256SUMS_SLIM'
EXC_SLIM='models/encoder/onnx__model.onnx models/encoder_f32.bin models/verb_gloss_f32.bin baseline_v1_5/models/* baseline_v1_4/models/encoder/* baseline_v1_4/models/encoder_f32.bin baseline_v1_4/models/verb_gloss_f32.bin'
list() { find . -type f | sed 's#^\./##' | sort | while read -r f; do
  skip=0; for p in $1; do case "$f" in $p) skip=1;; esac; done; [ $skip = 0 ] && echo "$f"; done; }
list "$EXC_COMMON" > /tmp/full.list
list "$EXC_COMMON $EXC_SLIM" > /tmp/slim.list
xargs -d '\n' sha256sum < /tmp/full.list > SHA256SUMS
xargs -d '\n' sha256sum < /tmp/slim.list > SHA256SUMS_SLIM
echo SHA256SUMS >> /tmp/full.list; echo SHA256SUMS_SLIM >> /tmp/full.list; echo SHA256SUMS >> /tmp/slim.list; echo SHA256SUMS_SLIM >> /tmp/slim.list
python3 - "$NAME" <<'PY'
import sys, zipfile
name = sys.argv[1]
for kind in ("full", "slim"):
    with zipfile.ZipFile(f"../{name}_{kind}.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in open(f"/tmp/{kind}.list").read().split("\n"):
            if f: z.write(f, f"{name}/{f}")
PY
ls -l ../${NAME}_full.zip ../${NAME}_slim.zip
