"""NumPy scorer for the frozen classifier_v1 JSON artifact. No scikit-learn at official score time."""
import json, math, re
from pathlib import Path
import numpy as np

WORD_RE = re.compile(r"(?u)\b\w+\b")

def fold_ws(s: str) -> str:
    return s

def word_tokens(text: str):
    return WORD_RE.findall(text.lower())

def word_ngrams(text: str, lo: int, hi: int):
    toks = word_tokens(text)
    out = []
    n = len(toks)
    for k in range(lo, hi + 1):
        for i in range(0, n - k + 1):
            out.append(" ".join(toks[i:i + k]))
    return out

def char_wb_ngrams(text: str, lo: int, hi: int):
    # Matches sklearn TfidfVectorizer(analyzer='char_wb'): split on whitespace,
    # pad each token with spaces, take character n-grams.
    out = []
    for w in text.lower().split():
        if not w:
            continue
        padded = " " + w + " "
        L = len(padded)
        for k in range(lo, hi + 1):
            if L < k:
                continue
            for i in range(0, L - k + 1):
                out.append(padded[i:i + k])
    return out

def tfidf_row(ngrams, vocab, idf, n_features, offset):
    # raw counts, then tf * idf, then L2 normalize over this block
    counts = {}
    for g in ngrams:
        j = vocab.get(g)
        if j is None:
            continue
        counts[j] = counts.get(j, 0) + 1
    vec = np.zeros(n_features, dtype=np.float64)
    for j, c in counts.items():
        vec[offset + j] = c * idf[j]
    nrm = np.linalg.norm(vec[offset:offset + len(idf)])
    if nrm > 0:
        vec[offset:offset + len(idf)] /= nrm
    return vec

class Classifier:
    def __init__(self, artifact: dict):
        self.threshold = float(artifact["threshold"])
        self.intercept = float(artifact["intercept"])
        self.coef = np.asarray(artifact["coef"], dtype=np.float64)
        self.word = artifact["word"]
        self.char = artifact["char"]
        self.word_vocab = {k: int(v) for k, v in self.word["vocab"].items()}
        self.char_vocab = {k: int(v) for k, v in self.char["vocab"].items()}
        self.word_idf = np.asarray(self.word["idf"], dtype=np.float64)
        self.char_idf = np.asarray(self.char["idf"], dtype=np.float64)
        self.n_features = int(artifact["n_features"])
        if self.coef.shape[0] != self.n_features:
            raise ValueError("coef length does not match n_features")

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text()))

    def vectorize(self, text: str) -> np.ndarray:
        text = text or ""
        wlo, whi = self.word["ngram_range"]
        clo, chi = self.char["ngram_range"]
        vec = np.zeros(self.n_features, dtype=np.float64)
        # word block then char block, as in FeatureUnion order
        wcount = len(self.word_idf)
        wv = tfidf_row(word_ngrams(text, wlo, whi), self.word_vocab, self.word_idf, self.n_features, 0)
        cv = tfidf_row(char_wb_ngrams(text, clo, chi), self.char_vocab, self.char_idf, self.n_features, wcount)
        # each block already L2-normalized in its slice; combine by adding (disjoint slices)
        return wv + cv

    def score(self, text: str) -> float:
        x = self.vectorize(text)
        z = float(np.dot(self.coef, x) + self.intercept)
        # stable sigmoid
        if z >= 0:
            p = 1.0 / (1.0 + math.exp(-z))
        else:
            e = math.exp(z)
            p = e / (1.0 + e)
        return p

    def hold(self, text: str) -> tuple[bool, float]:
        p = self.score(text)
        return p >= self.threshold, p

def span_text(rec: dict) -> str:
    u = rec.get("untrusted_text") or ""
    a = rec.get("proposed_args") or ""
    if not u and not a:
        return ""
    if not a:
        return u
    if not u:
        return a if isinstance(a, str) else str(a)
    return u + " " + (a if isinstance(a, str) else str(a))
