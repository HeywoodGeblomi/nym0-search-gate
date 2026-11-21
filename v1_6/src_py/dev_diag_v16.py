import sys; sys.path.insert(0,"/workspace/frontier_pivot/search_gate_v1_6/src_py")
from dev16_lib import *
from collections import Counter
D=jl(DATA/"dev_v16.jsonl"); e=Emu()
fh=Counter(); fl=Counter(); ex=[]; lifted=Counter(); lex=[]
for r in D:
    h,layer,sc=e.hold(r["text"],"all",None,True)
    c=e.comps(r["text"],"all")
    raw=e.hold(r["text"],"all",None,False)[0]
    if r["label"]==0 and h: fh[(r["group"],layer)]+=1; 
    if r["label"]==0 and h and len(ex)<400: ex.append((r["group"],layer,r["text"][:260].replace("\n"," "),c["instr"][:1],c["map"][:1],round(sc,2)))
    if r["label"]==1 and raw and not h: lifted[(r["group"].split(":")[0],r.get("category"),r.get("kind"))]+=1; lex.append((r.get("kind"),r.get("category"),r.get("injection","")[:90]))
print("clean false holds by group,layer:"); 
for k,v in sorted(fh.items()): print(" ",k,v)
print("lifted injected by group,category,kind:", sum(lifted.values()))
for k,v in lifted.most_common(30): print(" ",k,v)
import random; random.Random(1).shuffle(ex)
print("\nsamples of remaining false holds:")
for x in ex[:28]: print(x)
