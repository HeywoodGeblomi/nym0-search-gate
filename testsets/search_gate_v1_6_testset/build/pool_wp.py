import sys,random,json; sys.path.insert(0,'.')
from common import *
subs=["Biology and health sciences/Animals","Biology and health sciences/Plants","Geography/Physical","Geography/Cities","Physical sciences/Astronomy","Physical sciences/Chemistry","Physical sciences/Earth science","Technology","Arts","Society and social sciences/Culture","Everyday life","Mathematics","Measurement","History","Society and social sciences/Politics and economics"]
pool={}
for s in subs:
    d=api("en.wikipedia.org",dict(action="query",prop="revisions",rvprop="content",rvslots="main",titles="Wikipedia:Vital articles/Level 4/"+s,format="json"))
    pg=list(d['query']['pages'].values())[0]
    if 'revisions' not in pg: print('miss',s); continue
    t=pg['revisions'][0]['slots']['main']['*']
    ts=[x.split('|')[0].strip() for x in re.findall(r"\[\[([^\]\[#:]+)\]\]",t)]
    ts=[x for x in ts if not x.startswith(('File','Category','Image'))]
    pool[s]=sorted(set(ts)); print(s,len(pool[s]))
json.dump(pool,open("vital_pool.json","w"))
