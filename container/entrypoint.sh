#!/bin/sh
# Release entrypoint for the Nym-0 Search Gate v1.6 image (packaging only; no gate code here).
# verify : preregistration hash + frozen-file check (files present in the image) + gate re-run on the new set, byte-compared with out/new_v16.out.jsonl
# shell  : a shell
set -e
cd /app
case "${1:-verify}" in
  verify)
    sha256sum -c PREREG.sha256
    sha256sum -c FREEZE.sha256 --quiet && echo "frozen files unchanged"
    exec python3 src_py/fresh_check_v16.py ;;
  shell) exec /bin/sh ;;
  *) echo "usage: verify | shell"; exit 2 ;;
esac
