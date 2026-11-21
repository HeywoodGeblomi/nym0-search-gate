"""Nym-0 verb meaning map (Search Gate v1.4). Standard library + NumPy + ONNX Runtime only. No torch, no network, no `tokenizers` package.

A frozen small open sentence-embedding model (all-MiniLM-L6-v2, Apache-2.0, ONNX, CPU) turns a command verb or short verb phrase
into a 384-dimension unit vector. Risky action regions are sets of seed verbs (src_py/verbmap_seeds.py). A verb's score for a region
is its full-dimensional cosine similarity to the nearest seed of that region. A verb at or above the dev-set threshold is inside a
region. The 2D picture is for illustration only; every decision uses the full 384 dimensions.
"""
import hashlib, json, unicodedata
from pathlib import Path
import numpy as np

EXPECTED_SHA256 = {
    "onnx__model.onnx": "6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452",
    "tokenizer.json": "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037",
    "config.json": "953f9c0d463486b10a6871cc2fd59f223b2c70184f49815e7efbcab5d8908b41",
}
MODEL_NAME = "all-MiniLM-L6-v2"

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()

def _is_punct(ch):
    cp = ord(ch)
    if (33 <= cp <= 47) or (58 <= cp <= 64) or (91 <= cp <= 96) or (123 <= cp <= 126): return True
    return unicodedata.category(ch).startswith("P")

class WordPiece:
    """BERT uncased basic tokenizer + WordPiece, read from the frozen tokenizer.json (checked against the `tokenizers` package at build time)."""
    def __init__(self, path):
        j = json.loads(Path(path).read_text())
        self.vocab = j["model"]["vocab"]
        self.unk = self.vocab["[UNK]"]; self.cls = self.vocab["[CLS]"]; self.sep = self.vocab["[SEP]"]
        self.prefix = j["model"].get("continuing_subword_prefix", "##")
        self.maxw = j["model"].get("max_input_chars_per_word", 100)
    def basic(self, text):
        out = []
        for ch in text:
            cp = ord(ch)
            if cp == 0 or cp == 0xFFFD or (unicodedata.category(ch) in ("Cc", "Cf") and ch not in "\t\n\r"): continue
            out.append(" " if ch.isspace() else ch)
        text = "".join(out).lower()
        text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
        words, cur = [], []
        for ch in text:
            if ch == " ":
                if cur: words.append("".join(cur)); cur = []
            elif _is_punct(ch):
                if cur: words.append("".join(cur)); cur = []
                words.append(ch)
            else: cur.append(ch)
        if cur: words.append("".join(cur))
        return words
    def wordpiece(self, w):
        if len(w) > self.maxw: return [self.unk]
        ids, s = [], 0
        while s < len(w):
            e, got = len(w), None
            while s < e:
                sub = w[s:e] if s == 0 else self.prefix + w[s:e]
                if sub in self.vocab: got = self.vocab[sub]; break
                e -= 1
            if got is None: return [self.unk]
            ids.append(got); s = e
        return ids
    def encode(self, text, max_len=64):
        ids = [self.cls]
        for w in self.basic(text): ids.extend(self.wordpiece(w))
        ids = ids[: max_len - 1] + [self.sep]
        return ids

class VerbEncoder:
    """Frozen encoder. One text per forward pass (no batching), one intra-op thread: deterministic. Mean pool over tokens, L2 normalize."""
    def __init__(self, root):
        self.root = Path(root)
        self.file_sha256 = {}
        for name, exp in EXPECTED_SHA256.items():
            p = self.root / name
            if not p.is_file(): raise FileNotFoundError(f"missing encoder file: {p}")
            got = sha256_file(p)
            if got != exp: raise ValueError(f"encoder hash mismatch for {name}: {got}")
            self.file_sha256[name] = got
        import onnxruntime as ort
        self.tok = WordPiece(self.root / "tokenizer.json")
        op = ort.SessionOptions(); op.intra_op_num_threads = 1; op.inter_op_num_threads = 1
        self.sess = ort.InferenceSession(str(self.root / "onnx__model.onnx"), sess_options=op, providers=["CPUExecutionProvider"])
        self.inputs = [x.name for x in self.sess.get_inputs()]
        self.outputs = [x.name for x in self.sess.get_outputs()]
        self.cache = {}
    def tag(self):
        return f"{MODEL_NAME}@{self.file_sha256['onnx__model.onnx'][:12]}"
    def encode_one(self, text):
        v = self.cache.get(text)
        if v is not None: return v
        ids = self.tok.encode(text)
        d = {"input_ids": np.asarray([ids], dtype=np.int64), "attention_mask": np.ones((1, len(ids)), dtype=np.int64), "token_type_ids": np.zeros((1, len(ids)), dtype=np.int64)}
        out = self.sess.run(None, {k: d[k] for k in self.inputs})
        if "sentence_embedding" in self.outputs: e = out[self.outputs.index("sentence_embedding")][0]
        else:
            h = next(x for x in out if getattr(x, "ndim", 0) == 3)[0]
            e = h.mean(axis=0)
        e = e.astype(np.float64); e = e / (np.linalg.norm(e) + 1e-12)
        self.cache[text] = e
        return e
    def encode(self, texts):
        return np.stack([self.encode_one(t) for t in texts])
