import json,sys,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src_py"))
from instruction_check import InstructionCheck
ic=InstructionCheck(ROOT/"models"/"verb_families_v1_3.json")
rows=[json.loads(l) for l in open(ROOT/"data"/"dev_set.jsonl")]
c=collections.Counter(); miss=[]
for r in rows:
    h,rs=ic.check(r["text"]); c[(r["family"],h)]+=1
    if (r["gold"]=="HOLD")!=h: miss.append((r["family"],r["template"][:100],rs[:2]))
for k in sorted(c): print(k,c[k])
for m in miss: print("WRONG:",m)
