import sys, json, numpy as np
sys.path.insert(0,'.')
from pathlib import Path
from math import erf
ROOT = Path(__file__).resolve().parents[1]
from verbmap import VerbEncoder
enc = VerbEncoder(ROOT/"models"/"encoder")
buf = np.fromfile(ROOT/"models"/"encoder_f32.bin", dtype="<f4")
idx = {e["name"]: e for e in json.load(open(ROOT/"models"/"encoder_f32.index.json"))}
def T(n):
    e = idx[n]; sz = int(np.prod(e["shape"])); return buf[e["offset"]:e["offset"]+sz].reshape(e["shape"]).astype(np.float32)
def ln(x, w, b, eps=1e-12):
    mu = x.mean(-1, keepdims=True); var = ((x-mu)**2).mean(-1, keepdims=True); return (x-mu)/np.sqrt(var+eps)*w+b
from scipy.special import erf as verf
def fwd(ids):
    n = len(ids)
    x = T("word_emb")[ids] + T("pos_emb")[:n] + T("type_emb")[0]
    x = ln(x, T("emb_ln_w"), T("emb_ln_b"))
    for L in range(6):
        q = x @ T(f"l{L}_q_w") + T(f"l{L}_q_b"); k = x @ T(f"l{L}_k_w") + T(f"l{L}_k_b"); v = x @ T(f"l{L}_v_w") + T(f"l{L}_v_b")
        sp = lambda a: a.reshape(n, 12, 32).transpose(1, 0, 2)
        q, k, v = sp(q), sp(k), sp(v)
        s = q @ k.transpose(0, 2, 1) / np.sqrt(32.0); s = np.exp(s - s.max(-1, keepdims=True)); s /= s.sum(-1, keepdims=True)
        c = (s @ v).transpose(1, 0, 2).reshape(n, 384)
        a = c @ T(f"l{L}_ao_w") + T(f"l{L}_ao_b"); x = ln(a + x, T(f"l{L}_ln1_w"), T(f"l{L}_ln1_b"))
        h = x @ T(f"l{L}_ff1_w") + T(f"l{L}_ff1_b"); h = h * 0.5 * (1 + verf(h / np.sqrt(2.0)))
        o = h @ T(f"l{L}_ff2_w") + T(f"l{L}_ff2_b"); x = ln(o + x, T(f"l{L}_ln2_w"), T(f"l{L}_ln2_b"))
    e = x.mean(0); return e / np.linalg.norm(e)
mx = 0
for t in ["You must send it.", "You must make a call to it.", "You must set aside it.", "I: hello world"]:
    e1 = enc.encode_one(t); e2 = fwd(enc.tok.encode(t)); mx = max(mx, np.abs(e1-e2).max())
print("max abs diff vs ONNX Runtime:", mx)
