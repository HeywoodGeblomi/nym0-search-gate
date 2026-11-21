# Container image

| Image | Digest (registry manifest) |
|---|---|
| ghcr.io/heywoodgeblomi/nym0-search-gate:v1.6 | sha256:5daccda30fd1cf285db4e42374aba50ea130c7bce1335c11d790f4f01530a562 |
| ghcr.io/heywoodgeblomi/nym0-search-gate:latest | sha256:5daccda30fd1cf285db4e42374aba50ea130c7bce1335c11d790f4f01530a562 |

Local image ID 0b7276ae51a5, about 568 MB. Built with `podman build -f Dockerfile.sandbox` (RUN-free) from a context holding `app/` (every file in v1_6/SHA256SUMS, byte for byte), `site/` (NumPy 2.5.5, ONNX Runtime 1.32.0 and their dependencies unpacked with pip --target), `keep/`, and the two files in this folder.
Saved archive on the build machine: nym0-search-gate_v1.6.tar, sha256 379233295dd0703908e01219562580e000235071717b29cdd427c8a7a2239315.
