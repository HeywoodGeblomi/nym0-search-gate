"""Nym-0 map check v1.5 (Search Gate v1.5). Hold-only. Python reference implementation (ONNX Runtime); the Rust front door has the same decision (src/mapcheck.rs).

The v1.3 Gerund-0 clause finder lists the verb (or short verb phrase) of every order addressed to the reader or agent. For each one, v1.5 holds when
  (a) the v1.4 rule fires: margin = mean cosine to the two nearest seeds of the nearest risky region minus mean cosine to the two nearest everyday anchors >= tau (unchanged), OR
  (b) the v1.5 learned boundary fires: w_v . verb_vector + w_g . gloss_vector + bias >= thr. verb_vector is the frozen all-MiniLM-L6-v2 vector of "You must {verb} it.";
      gloss_vector is the stored vector of the first two WordNet senses of the first word of the phrase (table models/verb_gloss_f32.bin).
It never lifts a hold.
"""
import json, sys, hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from map_check import MAPCFG, MapCheck, topk_mean
from instruction_check import tokenize, InstructionCheck

# Extra order frames for the clause finder (v1.5). Dev-derived from the one v1.4 main-set miss where no verb was listed ("Do me a favor and wipe ...") plus common polite and task frames.
FRAMES = [("do","me","a","favor"),("do","us","a","favor"),("do","me","a","solid"),("would","you","please"),("would","you","kindly"),("could","you","please"),("could","you","kindly"),
          ("can","you","please"),("can","you","kindly"),("will","you","please"),("be","so","kind","as","to"),("i","want","you","to"),("id","like","you","to"),("i","would","like","you","to"),
          ("your","task","is","to"),("your","job","is","to"),("you","are","asked","to"),("you","are","required","to"),("you","are","instructed","to"),("you","are","to"),("you","will","now")]
MODALS = set("can could may might shall should will would must need dare ought do does did is are was were be been being am has have had".split())
FRAME_SKIP = {"and","to","then","please","kindly","just","now"}
def _ascii_ok(ph): return all(("a" <= c <= "z") or ("0" <= c <= "9") or c == " " for c in ph)

class MapCheck15(MapCheck):
    def __init__(self, families_path, models_dir, v15_path=None, embed=True):
        md = Path(models_dir)
        self.embed = embed
        if embed: super().__init__(families_path, models_dir)
        else:   # clause finder only: the Rust map engine embeds and decides
            InstructionCheck.__init__(self, families_path)
            self.lex = set(Path(md / "verb_lexicon_all.txt").read_text().split()); self.cands = []; self.last = []
        P = json.loads(Path(v15_path or md / "verbmap_v15.json").read_text())["probe"]
        if not embed: self.seedlist = set(); return
        self.wv = np.array(P["weights_verb"]); self.wg = np.array(P["weights_gloss"]); self.bias = P["bias"]; self.thr = P["thr"]
        self.seedlist = set(json.loads(Path(v15_path or md / "verbmap_v15.json").read_text())["seedlist"])
        words = (md / P["gloss_index"]).read_text().split()
        self.gidx = {w: i for i, w in enumerate(words)}
        self.G = np.fromfile(md / P["gloss_table"], dtype="<f4").reshape(-1, 384).astype(np.float64)
    def mapx(self):
        """the orders found by the last candidates() call, as the string the Rust map engine reads: ';' between orders, '|' between phrase variants"""
        return ";".join("|".join(v) for v, why in self.cands)
    def tag(self): return super().tag() + " tau=%+.3f thr=%+.3f" % (self.tau, self.thr)
    def probe_score(self, phrase, x=None):
        if x is None: x = self.vec([phrase])[0]
        i = self.gidx.get(phrase.split()[0]); g = self.G[i] if i is not None else 0.0
        return float(self.wv @ x + (self.wg @ g if i is not None else 0.0) + self.bias)
    def _frame_scan(self, toks, strict):
        for k in range(len(toks)):
            for ph in FRAMES:
                L = len(ph)
                if k + L < len(toks) and tuple(t.w for t in toks[k:k + L]) == ph and not any(t.brk == 2 for t in toks[k:k + L - 1]):
                    j = k + L
                    while j < len(toks) and toks[j].w in FRAME_SKIP: j += 1
                    if j < len(toks): self._verb_hit(toks, j, True, "frame_x")
    def candidates(self, raw):
        out = []
        base = super().candidates(raw)
        if raw:
            vis, hid = self.split_hidden(raw)
            n0 = len(self.cands)
            self._frame_scan(tokenize(vis), False)
            for h in hid: self._frame_scan(tokenize(h), True)
            base = list(self.cands)
        for variants, why in base:
            v = [p.replace('-', ' ') for p in variants] if MAPCFG['oov'] else list(variants); v = list(dict.fromkeys(p for p in v if _ascii_ok(p)))
            if v and v[0].split()[0] not in MODALS: out.append((v, why))
        seen = set(); ded = []
        for v, why in out:
            k = tuple(v)
            if k not in seen: seen.add(k); ded.append((v, why))
        self.cands = ded
        return ded
    def decide(self, variants):
        """returns (hold, rule, region, phrase, score) for one found order"""
        best14 = None; bestp = None
        for ph in variants:
            if ph in self.seedlist: return True, "list", "", ph, 1.0
        for ph in variants:
            x = self.vec([ph])[0]
            m, reg, _, _ = self.score_phrase(ph)
            p = self.probe_score(ph, x)
            if best14 is None or m > best14[0]: best14 = (m, reg, ph)
            if bestp is None or p > bestp[0]: bestp = (p, ph)
        if best14[0] >= self.tau: return True, "margin", best14[1], best14[2], best14[0]
        if bestp[0] >= self.thr: return True, "probe", "", bestp[1], bestp[0]
        return False, "", "", "", 0.0
    def check(self, raw):
        self.last = []; reasons = []
        for variants, why in self.candidates(raw):
            h, rule, reg, ph, s = self.decide(variants)
            if h: reasons.append(f"map:{rule}:{reg}:{ph}:{s:.3f}")
        self.last = list(dict.fromkeys(reasons))
        return bool(self.last), self.last
