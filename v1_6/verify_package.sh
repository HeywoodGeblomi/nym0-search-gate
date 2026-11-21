#!/bin/sh
# Fresh-unpack check for the FULL zip. Run from the unpacked folder.
set -e
cd "$(dirname "$0")"
for f in encoder encoder_f32.bin verb_gloss_f32.bin; do [ -e baseline_v1_5/models/$f ] || ln -s ../../models/$f baseline_v1_5/models/$f; done
echo "== SHA256SUMS"; sha256sum -c SHA256SUMS --quiet && echo "all files match SHA256SUMS"
echo "== preregistration hash"; sha256sum -c PREREG.sha256
echo "== frozen design (145 files)"; sha256sum -c FREEZE.sha256 --quiet && echo "frozen files unchanged"
echo "== gate re-run on the new set (needs python3 + onnxruntime + numpy)"; python3 src_py/fresh_check_v16.py
