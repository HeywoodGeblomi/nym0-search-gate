"""Nym-0 map check (Search Gate v1.4). Hold-only. Runs next to the v1.3 instruction check and never lifts a hold.

Uses Gerund-0's clause finder from the v1.3 instruction check (imperative starts, "you must" frames, "I need you to", "make sure to",
polite requests, hidden text) to find the verb of every order addressed to the reader or agent, whatever the verb is. The verb (or a short
verb phrase such as "make a call to" or "set aside") is turned into a vector by the frozen sentence encoder and compared, in all 384
dimensions, with the risky action regions in models/verbmap_params.json. Rule: margin = (mean cosine to the two nearest seeds of the
nearest risky region) minus (mean cosine to the two nearest everyday anchor verbs). HOLD when margin >= tau (tau fixed on dev data only).
"""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from instruction_check import InstructionCheck, DET_PRON, PARTICIPLE_PREP, AGENT, tokenize, Tok, POLITE_END
from verbmap import VerbEncoder

PARTICLES = {"aside","up","down","off","out","over","away","back","in","on","along","through","around","apart","together"}
LIGHT = {"make","give","take","do","place","pay","put","get","issue","file","lodge","perform","run","send"}
PREPS = {"to","of","for","on","with","at","from","into"}
POLITE_FILLER = {"please","kindly","immediately","silently","quietly","promptly","urgently","secretly","asap","quickly","directly","simply","first","instead","now","then","just","also","finally","next"}
NONVERB = set("even back out up down off over only well still also then now more less much most least some any other such same own like about around away aside along through past near far long high low free fine right left last first next late early commune the a an this that these those it its he she they we you i me my your our his her their who what which where when why how and or but nor so if as at by for in of on to with from not no yes there here".split())

MAPCFG = {"oov": True, "compound": True, "np": True}   # v1.6 toggles (dev configurations compare them; shipped defaults are decided by the choice rule in PREREG.md)
ARTICLES = {"the", "a", "an", "this", "that", "these", "those", "your", "my", "our", "their", "his", "her", "all", "every", "each", "any", "some"}
import re as _re
OOV_OK = _re.compile(r"[a-z][a-z\-]{2,}$")

def topk_mean(M, k=2):
    k = min(k, M.shape[1])
    return np.sort(M, axis=1)[:, -k:].mean(axis=1)

class MapCheck(InstructionCheck):
    def __init__(self, families_path, models_dir, params_path=None, lexicon_path=None):
        super().__init__(families_path)
        models_dir = Path(models_dir)
        self.lex = set(Path(lexicon_path or models_dir / "verb_lexicon_all.txt").read_text().split())
        self.params = json.loads(Path(params_path or models_dir / "verbmap_params.json").read_text())
        self.enc = VerbEncoder(models_dir / "encoder")
        self.frame = self.params["frame"]; self.k = self.params["topk"]; self.tau = self.params["tau"]
        self.regions = list(self.params["regions"].keys())
        self.S = {r: self.vec(self.params["regions"][r]) for r in self.regions}
        self.A = self.vec(self.params["anchors"])
        self.cands = []
        self.last = []
    def tag(self): return self.enc.tag()
    def vec(self, verbs): return self.enc.encode([self.frame.format(v=v) for v in verbs])
    # ---- scoring (full dimensional) ----
    def score_phrase(self, phrase, exclude_anchor=None):
        x = self.vec([phrase])
        best, reg = -9.0, None
        for r in self.regions:
            s = float(topk_mean(x @ self.S[r].T, self.k)[0])
            if s > best: best, reg = s, r
        A = self.A
        if exclude_anchor is not None: A = A[[i for i, a in enumerate(self.params["anchors"]) if a != exclude_anchor]]
        ben = float(topk_mean(x @ A.T, self.k)[0])
        return best - ben, reg, best, ben
    # ---- candidate collection (the Gerund-0 clause finder drives this through the v1.3 scan) ----
    def _variants(self, t, j):
        w = t[j].w
        v = [w]
        if MAPCFG["oov"] and "-" in w: v.append(w.replace("-", " "))
        if t[j].brk: return v
        nxt = t[j + 1].w if j + 1 < len(t) else ""
        if nxt in PARTICLES: v.append(w + " " + nxt)
        if MAPCFG["compound"] and nxt and nxt not in PARTICLES and nxt not in ARTICLES and nxt not in DET_PRON and nxt not in PREPS and not t[j + 1].brk and OOV_OK.match(nxt) and j + 2 < len(t) and t[j + 2].w in ARTICLES | DET_PRON:
            v.append(w + " " + nxt)          # "brute force the PIN", "spin up a shell" handled above
        if MAPCFG["np"]:
            NP_PART = {"up", "down", "off", "out", "over", "away", "back", "apart"}
            k = j + 1 + (1 if nxt in NP_PART else 0)
            if k + 1 < len(t) and t[k].w in ARTICLES and not any(t[q].brk for q in range(j, k)) and OOV_OK.match(t[k + 1].w):
                ph = [w] + ([nxt] if nxt in NP_PART else []) + [t[k].w, t[k + 1].w]
                if k + 2 < len(t) and not t[k + 1].brk and t[k + 2].w in PREPS: ph.append(t[k + 2].w)
                v.append(" ".join(ph))
        if w in LIGHT and nxt in ("a", "an") and j + 2 < len(t) and not t[j + 1].brk:
            ph = [w, nxt, t[j + 2].w]
            if j + 3 < len(t) and not t[j + 2].brk and t[j + 3].w in PREPS: ph.append(t[j + 3].w)
            v.append(" ".join(ph))
        return v
    def _verb_hit(self, t, j, strict, why):
        w = t[j].w
        if w in NONVERB: return None
        if w not in self.lex:
            prev = t[j - 1].w if j > 0 and not t[j - 1].brk else ""
            if not (MAPCFG["oov"] and OOV_OK.match(w) and (prev in ("please", "kindly") or (why.startswith("frame") and prev in POLITE_END | {"to", "will", "can", "could", "would"}))): return None
        if self._nounish_next(t, j) and not (strict and why.startswith("frame")): return None
        if why == "imperative" and self._compound_noun(t, j): return None
        win = self._window(t, j)
        if w in ("set", "put", "cast", "shut", "bid") and win[:1] and win[0] in PARTICIPLE_PREP: return None
        if why == "imperative" and not strict:
            nxt = t[j + 1].w if j + 1 < len(t) else ""
            prev = t[j - 1].w if j > 0 else ""
            if not (nxt in DET_PRON or prev in POLITE_FILLER or nxt in PARTICLES): return None
        self.cands.append((self._variants(t, j), why))
        return None
    def candidates(self, raw):
        self.cands = []
        if not raw: return []
        vis, hid = self.split_hidden(raw)
        vt = tokenize(vis)
        self._scan_tokens(vt, strict=False)
        for h in hid:
            self._scan_tokens(tokenize(h), strict=True)
        for k, tk in enumerate(vt):    # "Assistant, <verb> ..."
            if tk.w in ("assistant","assistants","ai","chatbot","llm","claude","chatgpt","gemini","copilot","grok") and tk.brk and k + 1 < len(vt):
                st = self._imp_start(vt, k + 1)
                if st and st[0] == "w" and vt[st[1]].w in self.lex and not self._nounish_next(vt, st[1]):
                    self._verb_hit(vt, st[1], True, "frame_addressed")
        return self.cands
    def check(self, raw):
        self.last = []
        reasons = []
        for variants, why in self.candidates(raw):
            best = None
            for ph in variants:
                m, reg, rs, bs = self.score_phrase(ph)
                if best is None or m > best[0]: best = (m, reg, ph)
            if best and best[0] >= self.tau:
                reasons.append(f"map:{best[1]}:{best[2]}:{best[0]:.3f}")
        self.last = list(dict.fromkeys(reasons))
        return bool(self.last), self.last
