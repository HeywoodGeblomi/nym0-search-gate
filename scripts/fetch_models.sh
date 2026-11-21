#!/bin/sh
# Restores the model files that are not stored in git, then checks their sha256.
#  1. the frozen all-MiniLM-L6-v2 ONNX encoder, from Hugging Face at a pinned revision
#  2. the derived binary tables (encoder_f32.bin, verb_gloss_f32.bin, map_table_v15.bin) and the prebuilt
#     Rust front door bin/nym0asgate, copied out of the published container image
# Run from the repo root:  sh scripts/fetch_models.sh   (needs curl, sha256sum, and podman or docker for step 2)
set -e
D=v1_6
REV=1110a243fdf4706b3f48f1d95db1a4f5529b4d41
mkdir -p $D/models/encoder
curl -fL -o $D/models/encoder/onnx__model.onnx "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/$REV/onnx/model.onnx"
IMG=${IMG:-ghcr.io/heywoodgeblomi/nym0-search-gate:v1.6}
CT=$(command -v podman || command -v docker)
if [ -n "$CT" ]; then
  C=$($CT create "$IMG")
  for f in models/encoder_f32.bin models/verb_gloss_f32.bin models/map_table_v15.bin bin/nym0asgate; do mkdir -p "$D/$(dirname $f)"; $CT cp "$C:/app/$f" "$D/$f"; done
  $CT rm "$C" >/dev/null; chmod +x $D/bin/nym0asgate
else echo "no podman or docker: skipped the binary tables (or rebuild bin/ with: cd $D/front && cargo build --release)"; fi
cd $D && grep -E ' (models/encoder/onnx__model.onnx|models/encoder_f32.bin|models/verb_gloss_f32.bin|models/map_table_v15.bin|bin/nym0asgate)$' SHA256SUMS | sha256sum -c
