import sys, numpy as np
sys.path.insert(0,'.')
from dev_cv_v15 import *
from dev_combo_v15 import oof, rv, evw
import json
P14 = json.load(open(ROOT/"models"/"verbmap_params.json"))
def m14(words):
    return np.array([mc.score_phrase(w, exclude_anchor=w)[0] for w in words])
M14r = m14(rv); M14e = m14(evw)
print("v1.4 rule alone: pool recall %.3f, everyday FP %.3f" % ((M14r >= -0.02).mean(), (M14e >= -0.02).mean()))
pr, pe, mr, me = oof(1.0, True, 2)
for b in np.arange(-1.0, 3.01, 0.25):
    fp = ((pe >= b) | (M14e >= -0.02)).mean(); rec = ((pr >= b) | (M14r >= -0.02)).mean()
    print(f"b={b:+.2f} combined FP {fp:.3f} recall {rec:.3f} | probe alone FP {(pe>=b).mean():.3f} recall {(pr>=b).mean():.3f}")
