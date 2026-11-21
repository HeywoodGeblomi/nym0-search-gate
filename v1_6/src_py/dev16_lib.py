#!/usr/bin/env python3
"""Dev emulator for v1.6 (Python ONNX engine for the map). Used only for development and the choice rule."""
import json, sys, hashlib, random
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; DATA = ROOT/"data"; MODELS = ROOT/"models"
sys.path.insert(0, str(ROOT/"src_py"))
import instruction_check as IC
import map_check as MCm
from map_check15 import MapCheck15
from classifier_infer import Classifier
import howto16
def jl(p): return [json.loads(l) for l in open(p) if l.strip()]
def split_of(url): return "val" if int(hashlib.sha256(url.encode()).hexdigest(), 16) % 100 < 30 else "fit"
def set_cfg(end_fix=True, system_tag=True, resource_obj=True, oov=True, compound=True, np=True):
    IC.CFG.update(end_fix=end_fix, system_tag=system_tag, resource_obj=resource_obj)
    MCm.MAPCFG.update(oov=oov, compound=compound, np=np)
CONFIGS = {"v15": dict(end_fix=False, system_tag=False, resource_obj=False, oov=False, compound=False, np=False),
           "all": dict(end_fix=True, system_tag=True, resource_obj=True, oov=True, compound=True, np=True)}
class Emu:
    def __init__(self, clf_path=None):
        self.mc = MapCheck15(MODELS/"verb_families_v1_3.json", MODELS)
        self.ic = IC.InstructionCheck(MODELS/"verb_families_v1_3.json")
        self.clfs = {}
        self.cache = {}; self.pcache = {}
        self.clf_path = clf_path or MODELS/"classifier_v1_2.json"
    def clf(self, path=None):
        path = str(path or self.clf_path)
        if path not in self.clfs: self.clfs[path] = Classifier.load(path)
        return self.clfs[path]
    def decide_cached(self, variants):
        k = tuple(variants)
        if k not in self.pcache: self.pcache[k] = self.mc.decide(variants)
        return self.pcache[k]
    def comps(self, text, cfgname):
        key = (cfgname, hashlib.sha1(text.encode()).hexdigest())
        if key in self.cache: return self.cache[key]
        set_cfg(**CONFIGS[cfgname])
        ih, ireasons = self.ic.check(text)
        cands = self.mc.candidates(text)
        mreasons = []
        for variants, why in cands:
            h, rule, reg, ph, s = self.decide_cached(variants)
            if h: mreasons.append(f"map:{rule}:{reg}:{ph}:{s:.3f}")
        wv, info, st = howto16.howto_info(self.mc, text, ireasons)
        c = {"instr": ireasons, "map": mreasons, "waive": wv, "waive_info": info, "n_cands": len(cands)}
        self.cache[key] = c
        return c
    def hold(self, text, cfgname, clfpath=None, waiver=False):
        c = self.comps(text, cfgname)
        cl = self.clf(clfpath); h, sc = cl.hold(text)
        raw = bool(h or c["instr"] or c["map"])
        layer = "classifier" if h else ("instruction_check" if c["instr"] else ("meaning_map" if c["map"] else "allow"))
        if waiver and c["waive"]: return False, layer + "_waived", sc
        return raw, layer, sc
