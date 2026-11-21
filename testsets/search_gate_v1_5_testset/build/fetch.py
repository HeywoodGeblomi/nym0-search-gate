import json,urllib.request,urllib.parse,random,time,re,sys
import topics
UA="Nym0-testauthor/1.0 (research; public data)"
def api(host,params):
    u=f"https://{host}/w/api.php?"+urllib.parse.urlencode(params)
    for i in range(3):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":UA}),timeout=30))
        except Exception as e:
            time.sleep(2)
    raise RuntimeError(u)
def extract(host,title):
    d=api(host,dict(action="query",prop="extracts|info",explaintext=1,exintro=1,redirects=1,inprop="url",format="json",titles=title))
    p=list(d["query"]["pages"].values())[0]
    if "missing" in p: return None
    return dict(title=p["title"],url=p["fullurl"],text=(p.get("extract") or "").strip())
def trim(t,lo=350,hi=950):
    t=re.sub(r"\n+"," ",t); t=re.sub(r"\s+"," ",t)
    if len(t)<=hi: return t
    cut=t[:hi]; i=max(cut.rfind(". "),cut.rfind("? "))
    return cut[:i+1] if i>=lo else cut[:cut.rfind(" ")]+"."
out={"inj":[],"clean_wp":[],"clean_wb":[]}
def run(lst,host,key,need):
    for t in lst:
        if len(out[key])>=need: break
        r=extract(host,t)
        if not r: print("missing",t); continue
        r["text"]=trim(r["text"])
        if len(r["text"])<300 or "may refer to" in r["text"]: print("short",t); continue
        r["host"]=host; out[key].append(r)
run(topics.INJ_TOPICS,"en.wikipedia.org","inj",126)
run(topics.CLEAN_WP,"en.wikipedia.org","clean_wp",96)
# Wikibooks recipes
cm=[]; cont={}
while len(cm)<600:
    d=api("en.wikibooks.org",dict(action="query",list="categorymembers",cmtitle="Category:Recipes",cmlimit=500,format="json",cmnamespace=102,**cont))
    cm+=[m["title"] for m in d["query"]["categorymembers"]]
    if "continue" in d: cont=d["continue"]
    else: break
random.Random(1519).shuffle(cm)
run(cm,"en.wikibooks.org","clean_wb",36)
json.dump(out,open("raw_pages.json","w"),indent=1)
print({k:len(v) for k,v in out.items()})
