import sys,random,json,re; sys.path.insert(0,'.')
from common import *
from bs4 import BeautifulSoup
R=random.Random(1620)
out={}
def fullurl_wp(t): return "https://en.wikipedia.org/wiki/"+t.replace(" ","_")
# ---------- Wikipedia ordinary pool
pool=json.load(open("vital_pool.json")); allt=sorted({t for v in pool.values() for t in v if t.lower() not in V15T}); R.shuffle(allt)
wp=[]
batch=[]
def wp_extract(titles):
    d=api("en.wikipedia.org",dict(action="query",prop="extracts|info",explaintext=1,exintro=1,redirects=1,inprop="url",exlimit="max",format="json",titles="|".join(titles)))
    return list(d["query"]["pages"].values())
i=0
while len(wp)<200 and i<len(allt):
    for p in wp_extract(allt[i:i+20]):
        if "missing" in p: continue
        if p["fullurl"] in V15: continue
        t=trim(norm(p.get("extract") or ""))
        if len(t)<350 or "may refer to" in t or "may also refer" in t: continue
        if any(q["url"]==p["fullurl"] for q in wp): continue
        wp.append(dict(title=p["title"],url=p["fullurl"],text=t,host="en.wikipedia.org",src="wikipedia_extract_intro"))
    i+=20
out["wp"]=wp; print("wp",len(wp))
# ---------- Cookbook
cm=[];cont={}
while True:
    d=api("en.wikibooks.org",dict(action="query",list="categorymembers",cmtitle="Category:Recipes",cmlimit=500,format="json",cmnamespace=102,**cont))
    cm+=[m["title"] for m in d["query"]["categorymembers"]]
    if "continue" in d: cont=d["continue"]
    else: break
R.shuffle(cm); rec=[]
for t in cm:
    if len(rec)>=56: break
    d=api("en.wikibooks.org",dict(action="query",prop="extracts|info",explaintext=1,redirects=1,inprop="url",format="json",titles=t))
    p=list(d["query"]["pages"].values())[0]
    if p["fullurl"] in V15: continue
    m=re.search(r"==\s*Procedure\s*==\s*(.+)",p.get("extract") or "",re.S)
    if not m: continue
    txt=norm(re.split(r"\n==[^=]",m.group(1))[0]); txt=trim("Procedure. "+txt)
    if len(txt)<300: continue
    rec.append(dict(title=p["title"],url=p["fullurl"],text=txt,host="en.wikibooks.org",src="wikibooks_cookbook_procedure"))
out["recipes"]=rec; print("recipes",len(rec))
# ---------- Wikibooks how-to / manual
IMP=re.compile(r"(?:^|[.!?] )(Place|Remove|Insert|Turn|Press|Open|Check|Make|Use|Take|Put|Add|Keep|Hold|Pull|Push|Connect|Attach|Apply|Clean|Fill|Tighten|Loosen|Select|Click|Type|Enter|Start|Stop|Wait|Wipe|Cut|Mix|Lift|Set|Choose|Run|Install|Save|Copy|Read|Find|Remember|Make sure|Ensure|Replace|Align|Slide|Adjust|Measure|Lay|Fold|Tie)\b")
qs=["how to repair step by step","how to change","how to install","how to clean","maintenance procedure","first aid how to","how to build","how to set up","user guide steps","how to tie","how to make","guide: do not forget to","assembly instructions","troubleshooting steps","how to use"]
cands=[]
for q in qs:
    d=api("en.wikibooks.org",dict(action="query",list="search",srsearch=q,srnamespace=0,srlimit=30,format="json"))
    cands+= [x["title"] for x in d["query"]["search"]]
cands=sorted(set(cands)); R.shuffle(cands); how=[]
for t in cands:
    if len(how)>=22: break
    if "Structural Biochemistry" in t: continue
    d=api("en.wikibooks.org",dict(action="query",prop="extracts|info",explaintext=1,redirects=1,inprop="url",format="json",titles=t))
    p=list(d["query"]["pages"].values())[0]
    if "missing" in p or p["fullurl"] in V15: continue
    lines=[l.strip() for l in (p.get("extract") or "").split("\n") if len(l.strip())>45]
    txt=norm(" ".join(lines))
    # find window with most imperatives
    best=None
    for s in range(0,max(1,min(len(txt)-900,6000)),150):
        w=txt[s:s+1000]; n=len(IMP.findall(w))
        if best is None or n>best[0]: best=(n,s)
    if best is None or best[0]<3: continue
    w=txt[best[1]:best[1]+1000]; w=w[w.find(". ")+2:] if best[1]>0 else w
    w=trim(w)
    if len(w)<350: continue
    how.append(dict(title=p["title"],url=p["fullurl"],text=w,host="en.wikibooks.org",src="wikibooks_howto"))
out["howto"]=how; print("howto",len(how))
# ---------- Wikivoyage
cities="Lisbon|Porto|Seville|Granada|Valencia|Naples|Florence|Venice|Bologna|Turin|Vienna|Salzburg|Prague|Krakow|Budapest|Zagreb|Split|Athens|Istanbul|Tbilisi|Kyoto|Osaka|Hanoi|Hoi An|Chiang Mai|Luang Prabang|Kathmandu|Cusco|Quito|Cartagena|Oaxaca|Montreal|Quebec City|Reykjavik|Edinburgh|Cork|Bruges|Ghent|Tallinn|Riga|Vilnius|Marrakech|Cape Town|Zanzibar|Hobart|Queenstown|Wellington|Banff|Tromsø|Bergen|Ljubljana".split("|")
R.shuffle(cities); wv=[]
for c in cities:
    if len(wv)>=22: break
    d=api("en.wikivoyage.org",dict(action="parse",page=c,prop="sections",format="json",redirects=1))
    if "parse" not in d: continue
    secs=d["parse"]["sections"]; url="https://en.wikivoyage.org/wiki/"+d["parse"]["title"].replace(" ","_")
    if url in V15: continue
    pick=[s for s in secs if s["line"] in ("Get in","Do","By train","By bus")]
    for s in pick[:1] if pick else []:
        pass
    pick=[s for s in secs if s["line"]=="Do"] or [s for s in secs if s["line"]=="Get in"]
    if not pick: continue
    s=pick[0]
    d2=api("en.wikivoyage.org",dict(action="parse",page=c,prop="text",section=s["index"],format="json",redirects=1))
    soup=BeautifulSoup(d2["parse"]["text"]["*"],"html.parser")
    for x in soup.select(".mw-editsection,table,style,script,.thumb,figure"): x.decompose()
    txt=norm(soup.get_text(" "))
    txt=trim(f"{s['line']}. "+txt)
    if len(txt)<350: continue
    wv.append(dict(title=d["parse"]["title"]+" ("+s["line"]+")",url=url,text=txt,host="en.wikivoyage.org",src="wikivoyage_"+s["line"].lower().replace(" ","_")))
out["voyage"]=wv; print("voyage",len(wv))
# ---------- game / sport rules
games="Backgammon|Checkers|Rummy|Cribbage|Blackjack|Texas hold 'em|Contract bridge|Hearts (card game)|Spades (card game)|Uno (card game)|Mahjong|Dominoes|Scrabble|Monopoly (game)|Connect Four|Mancala|Battleship (game)|Hangman (game)|Darts|Ten-pin bowling|Volleyball|Badminton|Table tennis|Squash (sport)|Handball|Lacrosse|Field hockey|Softball|Ultimate (sport)|Kickball|Dodgeball|Pickleball|Netball|Archery|Croquet|Bocce|Gin rummy|Canasta|Euchre|Snooker|Shogi|Xiangqi|Othello (game)|Tic-tac-toe|Jenga|Capture the flag|Hopscotch|Tag (game)|Hide-and-seek|Musical chairs".split("|")
R.shuffle(games); gm=[]
for g in games:
    if len(gm)>=24: break
    d=api("en.wikipedia.org",dict(action="query",prop="extracts|info",explaintext=1,redirects=1,inprop="url",format="json",titles=g))
    p=list(d["query"]["pages"].values())[0]
    if "missing" in p or p["fullurl"] in V15: continue
    ex=p.get("extract") or ""
    m=re.search(r"\n==+\s*(Rules|Gameplay|Game play|How to play|Play|Objective|Basic rules|Rules of play|Playing|Equipment|Overview)\s*==+\s*\n(.+)",ex,re.S)
    if not m: continue
    body=re.split(r"\n==[^=]",m.group(2))[0]
    txt=trim(norm(body))
    if len(txt)<350: continue
    gm.append(dict(title=p["title"]+" ("+m.group(1)+")",url=p["fullurl"],text=txt,host="en.wikipedia.org",src="wikipedia_rules_section"))
out["games"]=gm; print("games",len(gm))
json.dump(out,open("raw_pages_v16.json","w"),indent=1)
