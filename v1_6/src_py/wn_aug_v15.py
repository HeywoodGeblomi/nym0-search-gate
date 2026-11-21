import sys, json
sys.path.insert(0,'.')
from nltk.corpus import wordnet as wn
import verbmap_seeds_v15 as W
fam = json.load(open('../models/verb_families_v1_3.json'))
lex = set(open('../models/verb_lexicon_all.txt').read().split())
s14 = {v for vs in W.V14_REGIONS.values() for v in vs}
def lemmas(ss, onlyfirst=True):
    out=[]
    for l in ss.lemmas():
        n=l.name()
        if not n.isalpha() or not n.islower(): continue
        vs=wn.synsets(n,'v')
        if ss not in vs[:2] or len(vs)>5: continue
        out.append(n)
    return out
def build():
    aug={}
    for r, seeds in W.V14_REGIONS.items():
        for s in seeds:
            for ss in wn.synsets(s,'v')[:1]:   # dominant sense only
                for n in lemmas(ss):
                    if n!=s and n in lex: aug.setdefault(n,set()).add(r)
                for h in ss.hyponyms()[:6]:     # direct troponyms
                    for n in lemmas(h):
                        if n in lex: aug.setdefault(n,set()).add(r)
    return aug
if __name__=="__main__":
    a=build(); print(len(a)); print(' '.join(sorted(a)))
