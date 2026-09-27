import json,re,hashlib,urllib.request,xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"
SOURCES=ROOT/"sources.json"; OUT=DATA/"issues.json"; ARCHIVE=DATA/"issue_archive.json"; PIPELINE=DATA/"pipeline.json"
UA="ViralNewsUpdates/0.2 (+https://github.com/Harshit381/viral-news-updates)"
STOP={"india","today","latest","news","report","reports","says","said","update","live","breaking","after","over","amid","new","will","from","into","with","this","that"}

def now(): return datetime.now(timezone.utc)
def load(path,default):
    try:return json.loads(path.read_text())
    except:return default
def date(v):
    try:return parsedate_to_datetime(v).astimezone(timezone.utc)
    except:
        try:return datetime.fromisoformat(v.replace("Z","+00:00")).astimezone(timezone.utc)
        except:return now()
def clean(v): return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",v or "")).strip()
def tag(e,n):
    x=e.find(n) or e.find("{*}"+n)
    return clean(x.text if x is not None else "")
def feed(source):
    try:
        req=urllib.request.Request(source["url"],headers={"User-Agent":UA})
        root=ET.fromstring(urllib.request.urlopen(req,timeout=20).read())
    except Exception as e:
        print("Feed failed:",source["name"],e); return []
    out=[]
    for e in root.findall(".//item")+root.findall(".//{*}entry"):
        title=tag(e,"title"); link=tag(e,"link")
        if not link:
            z=e.find("{*}link")
            if z is not None: link=z.attrib.get("href","")
        desc=tag(e,"description") or tag(e,"summary")
        when=tag(e,"pubDate") or tag(e,"published") or tag(e,"updated")
        if title and link: out.append({"title":title,"summary":desc[:360],"url":link,"published":date(when).isoformat(),"source":source["name"],"weight":source.get("weight",1),"type":source.get("type","publisher")})
    return out
def words(t): return {w for w in re.findall(r"[a-z0-9]{3,}",t.lower()) if w not in STOP}
def sim(a,b):
    x,y=words(a),words(b)
    return len(x&y)/max(1,len(x|y)) if x and y else 0
def evkey(e): return e.get("url") or hashlib.sha1((e.get("time","")+e.get("title","")).encode()).hexdigest()
def sources(events):
    seen=set(); out=[]
    for e in events:
        if e.get("url") and e["url"] not in seen:
            seen.add(e["url"]); out.append({"name":e.get("source","Source"),"url":e["url"]})
    return out
def score(items):
    n=len({x["source"] for x in items}); official=sum(x["type"]=="official" for x in items)
    latest=max(date(x["published"]) for x in items); age=max(0,(now()-latest).total_seconds()/3600)
    return round(n*10+sum(x["weight"] for x in items)*2+official*4+max(0,24-age)/24*5,2)

def build():
    DATA.mkdir(exist_ok=True); config=load(SOURCES,[]); articles=[]; health=[]
    for s in config:
        rows=feed(s); articles+=rows; health.append({"name":s["name"],"status":"ok" if rows else "no data/error","items":len(rows)})
    articles=list({x["url"]:x for x in articles}.values())
    groups=[]
    for a in sorted(articles,key=lambda x:x["published"],reverse=True):
        best=max((sim(a["title"],g[0]["title"]),g) for g in groups) if groups else (0,None)
        if best[0]>=.35: best[1].append(a)
        else: groups.append([a])
    old=load(ARCHIVE,{"issues":[]}).get("issues",[]); issues=[]
    for g in groups:
        g.sort(key=lambda x:x["published"]); lead=max(g,key=lambda x:len(x["title"]))
        match=max(((sim(lead["title"],o.get("title","")),o) for o in old),default=(0,None))
        previous=match[1] if match[0]>=.32 else None
        events=previous.get("timeline",[])[:] if previous else []; seen={evkey(e) for e in events}
        for x in g:
            e={"time":x["published"],"title":x["title"],"description":x["summary"],"source":x["source"],"url":x["url"]}
            if evkey(e) not in seen: events.append(e)
        events.sort(key=lambda x:x.get("time",""))
        issues.append({"id":previous["id"] if previous else hashlib.sha1("|".join(sorted(words(lead["title"]))).encode()).hexdigest()[:12],"rank":0,"title":lead["title"],"summary":lead["summary"] or "Multiple public sources are reporting this issue.","category":"India","status":previous.get("status","Monitoring") if previous else "Monitoring","score":score(g),"first_observed":events[0]["time"],"last_updated":events[-1]["time"],"authority":previous.get("authority","Not automatically inferred; verify from official sources.") if previous else "Not automatically inferred; verify from official sources.","timeline":events,"sources":sources(events)})
    byid={x.get("id"):x for x in old}
    for x in issues: byid[x["id"]]=x
    archive=sorted(byid.values(),key=lambda x:x.get("last_updated",""),reverse=True)[:500]
    ARCHIVE.write_text(json.dumps({"updated_at":now().isoformat(),"issues":archive},ensure_ascii=False,indent=2))
    top=sorted(issues,key=lambda x:x["score"],reverse=True)[:10]
    for n,x in enumerate(top,1): x["rank"]=n
    OUT.write_text(json.dumps({"generated_at":now().isoformat(),"issues":top},ensure_ascii=False,indent=2))
    PIPELINE.write_text(json.dumps({"generated_at":now().isoformat(),"article_count":len(articles),"candidate_issue_count":len(issues),"top10_count":len(top),"source_count":len(config),"source_health":health,"cost_policy":"$0 only"},ensure_ascii=False,indent=2))
    print("Collected",len(articles),"articles; generated",len(top),"Top 10 issues.")

if __name__=="__main__": build()
