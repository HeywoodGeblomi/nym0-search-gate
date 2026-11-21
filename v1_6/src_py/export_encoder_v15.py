#!/usr/bin/env python3
"""Export the frozen all-MiniLM-L6-v2 ONNX weights to a flat little-endian float32 table for the std-only Rust encoder, and the tokenizer vocabulary to a text file.
Build-time only (needs the onnx package). Layout in models/encoder_f32.index.json."""
import sys, json, hashlib, numpy as np
from pathlib import Path
import onnx
from onnx import numpy_helper
ROOT = Path(__file__).resolve().parents[1]
m = onnx.load(str(ROOT/"models"/"encoder"/"onnx__model.onnx"))
inits = {i.name: numpy_helper.to_array(i) for i in m.graph.initializer}
# MatMul weights: find them by traversing MatMul nodes in graph order
mats = []
for n in m.graph.node:
    if n.op_type == "MatMul":
        for x in n.input:
            if x in inits and inits[x].ndim == 2: mats.append((x, inits[x].shape))
assert len(mats) == 6 * 6, len(mats)
tensors = [("word_emb", inits["embeddings.word_embeddings.weight"]), ("pos_emb", inits["embeddings.position_embeddings.weight"]), ("type_emb", inits["embeddings.token_type_embeddings.weight"]),
           ("emb_ln_w", inits["embeddings.LayerNorm.weight"]), ("emb_ln_b", inits["embeddings.LayerNorm.bias"])]
roles = ["q", "k", "v", "ao", "ff1", "ff2"]
for L in range(6):
    p = f"encoder.layer.{L}."
    for j, role in enumerate(roles):
        name, shp = mats[L * 6 + j]
        exp = {"q": (384, 384), "k": (384, 384), "v": (384, 384), "ao": (384, 384), "ff1": (384, 1536), "ff2": (1536, 384)}[role]
        assert tuple(shp) == exp, (L, role, shp)
        tensors.append((f"l{L}_{role}_w", inits[name]))
    tensors += [(f"l{L}_q_b", inits[p+"attention.self.query.bias"]), (f"l{L}_k_b", inits[p+"attention.self.key.bias"]), (f"l{L}_v_b", inits[p+"attention.self.value.bias"]),
                (f"l{L}_ao_b", inits[p+"attention.output.dense.bias"]), (f"l{L}_ln1_w", inits[p+"attention.output.LayerNorm.weight"]), (f"l{L}_ln1_b", inits[p+"attention.output.LayerNorm.bias"]),
                (f"l{L}_ff1_b", inits[p+"intermediate.dense.bias"]), (f"l{L}_ff2_b", inits[p+"output.dense.bias"]), (f"l{L}_ln2_w", inits[p+"output.LayerNorm.weight"]), (f"l{L}_ln2_b", inits[p+"output.LayerNorm.bias"])]
buf = bytearray(); idx = []
for name, a in tensors:
    a = np.ascontiguousarray(a.astype("<f4")); idx.append({"name": name, "shape": list(a.shape), "offset": len(buf) // 4}); buf += a.tobytes()
(ROOT/"models"/"encoder_f32.bin").write_bytes(bytes(buf))
(ROOT/"models"/"encoder_f32.index.json").write_text(json.dumps(idx))
tok = json.loads((ROOT/"models"/"encoder"/"tokenizer.json").read_text())["model"]["vocab"]
vocab = [None] * len(tok)
for k, v in tok.items(): vocab[v] = k
(ROOT/"models"/"vocab.txt").write_text("\n".join(vocab) + "\n")
print(len(buf), hashlib.sha256(bytes(buf)).hexdigest(), len(vocab))
