import json,urllib.request,urllib.parse,time,re,html
UA="Nym0-testauthor/1.0 (research; public data)"
def api(host,params):
    u=f"https://{host}/w/api.php?"+urllib.parse.urlencode(params)
    for i in range(4):
        try: return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":UA}),timeout=40))
        except Exception as e: err=e; time.sleep(2)
    raise RuntimeError(str(err)+u)
def norm(t):
    t=re.sub(r"=+\s*([^=\n]+?)\s*=+",r"\1.",t); t=re.sub(r"\.\.","." ,t); return re.sub(r"\s+"," ",t).strip()
def trim(t,lo=300,hi=950):
    if len(t)<=hi: return t
    cut=t[:hi]; i=max(cut.rfind(". "),cut.rfind("? "),cut.rfind("! "))
    return cut[:i+1] if i>=lo else cut[:cut.rfind(" ")]+"."
V15=set(json.loads(l)["source_url"] for f in ("injected_120.jsonl","clean_120.jsonl") for l in open("/workspace/frontier_pivot/search_gate_v1_5_testset/"+f))
V15T=set(json.loads(l)["source_title"].lower() for f in ("injected_120.jsonl","clean_120.jsonl") for l in open("/workspace/frontier_pivot/search_gate_v1_5_testset/"+f))
