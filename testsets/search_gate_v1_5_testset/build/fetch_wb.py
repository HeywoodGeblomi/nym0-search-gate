import json,re,random,time,urllib.parse,urllib.request
UA="Nym0-testauthor/1.0 (research; public data)"
def api(params):
    u="https://en.wikibooks.org/w/api.php?"+urllib.parse.urlencode(params)
    for i in range(3):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":UA}),timeout=30))
        except Exception: time.sleep(2)
    raise RuntimeError(u)
cm=[];cont={}
while True:
    d=api(dict(action="query",list="categorymembers",cmtitle="Category:Recipes",cmlimit=500,format="json",cmnamespace=102,**cont))
    cm+=[m["title"] for m in d["query"]["categorymembers"]]
    if "continue" in d: cont=d["continue"]
    else: break
random.Random(1519).shuffle(cm)
res=[]
for t in cm:
    if len(res)>=34: break
    d=api(dict(action="query",prop="extracts|info",explaintext=1,redirects=1,inprop="url",format="json",titles=t))
    p=list(d["query"]["pages"].values())[0]
    ex=p.get("extract") or ""
    m=re.search(r"==\s*Procedure\s*==\s*(.+)",ex,re.S)
    if not m: continue
    proc=re.split(r"\n==",m.group(1))[0].strip()
    lines=[l.strip() for l in proc.split("\n") if l.strip()]
    txt=" ".join(lines)
    txt=re.sub(r"\s+"," ",txt)
    if len(txt)>950:
        cut=txt[:950]; i=cut.rfind(". "); txt=cut[:i+1] if i>300 else cut
    if len(txt)<250: continue
    res.append(dict(title=p["title"],url=p["fullurl"],text="Procedure. "+txt,host="en.wikibooks.org"))
json.dump(res,open("raw_wb.json","w"),indent=1)
print(len(res)); print(res[0]['text'][:400])
