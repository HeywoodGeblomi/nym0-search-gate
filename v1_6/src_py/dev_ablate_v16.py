import sys; sys.path.insert(0,"/workspace/frontier_pivot/search_gate_v1_6/src_py")
from dev16_lib import *
from collections import defaultdict
D=jl(DATA/"dev_v16.jsonl"); e=Emu()
OLDC=str(MODELS/"classifier_v1_2.json")
base=dict(end_fix=False,system_tag=False,resource_obj=False,oov=False,compound=False,np=False)
CONFIGS["none"]=base
names=["none","end_fix","system_tag","resource_obj","oov","compound","np","all"]
for t in names[1:-1]: CONFIGS[t]=dict(base,**{t:True})
def gk(r):
    g=r["group"].split(":")[0]
    return g if g not in ("old","oldslice") else r["group"]
print("%-14s"%"cfg", *[f"{k:>12s}" for k in ["v15_inj","v15_unseen","pool_inj","wp_inj","old:HOLD","old:ALLOW","v15_clean","wp_clean","pool_clean","v15_everyday"]])
for n in names:
    g=defaultdict(lambda:[0,0])
    for r in D:
        h=e.hold(r["text"],n,OLDC,False)[0]; k=gk(r); g[k][0]+=h; g[k][1]+=1
    print("%-14s"%n, *[f"{g[k][0]:>5d}/{g[k][1]:<6d}" for k in ["v15_inj","v15_unseen","pool_inj","wp_inj","old:HOLD","old:ALLOW","v15_clean","wp_clean","pool_clean","v15_everyday"]], flush=True)
