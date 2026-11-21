import sys,random,json,re; sys.path.insert(0,'.')
from common import *
from bs4 import BeautifulSoup
R=random.Random(1621)
raw=json.load(open("raw_pages_v16.json"))
cities="Lisbon|Porto|Seville|Granada|Valencia|Naples|Florence|Venice|Bologna|Turin|Vienna|Salzburg|Prague|Krakow|Budapest|Zagreb|Split|Athens|Istanbul|Tbilisi|Kyoto|Osaka|Hanoi|Hoi An|Chiang Mai|Luang Prabang|Kathmandu|Cusco|Quito|Cartagena|Oaxaca|Montreal|Quebec City|Reykjavik|Edinburgh|Cork|Bruges|Ghent|Tallinn|Riga|Vilnius|Marrakech|Cape Town|Zanzibar|Hobart|Queenstown|Wellington|Banff|Tromsø|Bergen|Ljubljana|Dubrovnik|Sintra|Lucerne|Interlaken|Heidelberg|Rothenburg|Cologne|Hamburg|Gdansk|Brasov|Sofia|Plovdiv".split("|")
R.shuffle(cities); wv=[]
for c in cities:
    if len(wv)>=22: break
    d=api("en.wikivoyage.org",dict(action="parse",page=c,prop="sections",format="json",redirects=1))
    if "parse" not in d: continue
    secs=d["parse"]["sections"]; url="https://en.wikivoyage.org/wiki/"+d["parse"]["title"].replace(" ","_")
    if url in V15: continue
    pick=[s for s in secs if s["line"]=="Get in"] if len(wv)%2==0 else [s for s in secs if s["line"]=="Do"]
    pick=pick or [s for s in secs if s["line"] in("Do","Get in")]
    if not pick: continue
    s=pick[0]
    d2=api("en.wikivoyage.org",dict(action="parse",page=c,prop="text",section=s["index"],format="json",redirects=1))
    soup=BeautifulSoup(d2["parse"]["text"]["*"],"html.parser")
    for x in soup.select(".mw-editsection,table,style,script,.thumb,figure,.toc,#toc,.vector-toc,.mw-heading,h2,h3,h4,.listing-metadata"): x.decompose()
    txt=norm(soup.get_text(" "))
    if "Contents" in txt[:40]: continue
    txt=trim(f"{s['line']}. "+txt)
    if len(txt)<350: continue
    wv.append(dict(title=d["parse"]["title"]+" ("+s["line"]+")",url=url,text=txt,host="en.wikivoyage.org",src="wikivoyage_"+s["line"].lower().replace(" ","_")))
raw["voyage"]=wv
raw["howto"]=[x for x in raw["howto"] if "SPM" not in x["title"]]
json.dump(raw,open("raw_pages_v16.json","w"),indent=1)
print(len(wv),len(raw["howto"]))
for x in wv[:3]: print(x['text'][:300],'\n')
