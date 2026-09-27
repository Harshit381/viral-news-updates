import json,re,hashlib,urllib.request,xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
SOURCES=ROOT/"sources.json"
OUT=DATA/"issues.json"
ARCHIVE=DATA/"issue_archive.json"
DAYS=DATA/"days"
PIPELINE=DATA/"pipeline.json"
UA="ViralNewsUpdates/0.3 (+https://github.com/Harshit381/viral-news-updates)"
STOP={"india","today","latest","news","report","reports","says","said","update","live","breaking","after","over","amid","new","will","from","into","with","this","that","the","and","for","has","have","its","their","were","been"}

def now(): return datetime.now(timezone.utc)

def load(path,default):
    try:return json.loads(path.read_text())
    except:return default

def parse_date(value):
    try:return parsedate_to_datetime(value).astimezone(timezone.utc)
    except:
        try:return datetime.fromisoformat((value or "").replace("Z","+00:00")).astimezone(timezone.utc)
        except:return now()

def clean(value):
    return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",value or "")).strip()

def local_text(el):
    return el.text if el is not None else ""

def children_text(el,name):
    for x in list(el):
        if x.tag.rsplit("}",1)[-1]==name:
            return clean(local_text(x))
    return ""

def links_from_item(item,primary):
    out=[]
    if primary: out.append({"type":"article","url":primary,"label":"Article / source"})
    for x in item.iter():
        local=x.tag.rsplit("}",1)[-1]
        u=x.attrib.get("url") or x.attrib.get("href")
        if u and local.lower() in {"enclosure","content","thumbnail","link"} and u not in [a["url"] for a in out]:
            kind="media" if local.lower() in {"enclosure","content"} else "related"
            out.append({"type":kind,"url":u,"label":"Video / media" if kind=="media" else "Related link"})
    return out[:6]

def read_feed(source):
    try:
        req=urllib.request.Request(source["url"],headers={"User-Agent":UA})
        root=ET.fromstring(urllib.request.urlopen(req,timeout=20).read())
    except Exception as exc:
        print("Feed failed:",source["name"],exc)
        return []
    items=[]
    elems=root.findall(".//item")+root.findall(".//{*}entry")
    for item in elems:
        title=clean(children_text(item,"title"))
        link=children_text(item,"link")
        if not link:
            for x in list(item):
                if x.tag.rsplit("}",1)[-1]=="link" and x.attrib.get("href"):
                    link=x.attrib["href"]; break
        desc=children_text(item,"description") or children_text(item,"summary") or children_text(item,"content")
        when=children_text(item,"pubDate") or children_text(item,"published") or children_text(item,"updated")
        if title and link:
            items.append({"title":title,"summary":desc[:1200],"url":link,"published":parse_date(when).isoformat(),"source":source["name"],"weight":source.get("weight",1),"type":source.get("type","publisher"),"links":links_from_item(item,link)})
    return items

def words(title):
    return {w for w in re.findall(r"[a-z0-9]{3,}",title.lower()) if w not in STOP}

def similarity(a,b):
    x,y=words(a),words(b)
    return len(x&y)/max(1,len(x|y)) if x and y else 0

def key_title(title):
    return "|".join(sorted(words(title)))

def score(items):
    sources=len({x["source"] for x in items})
    official=sum(x["type"]=="official" for x in items)
    latest=max(parse_date(x["published"]) for x in items)
    age=max(0,(now()-latest).total_seconds()/3600)
    return round(sources*10+sum(x["weight"] for x in items)*2+official*4+max(0,24-age)/24*5,2)

def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+",clean(text)) if s.strip()]

def make_summary(items,limit):
    used=set(); parts=[]
    for x in sorted(items,key=lambda a:a["published"],reverse=True):
        for s in sentences(x.get("summary","")):
            norm=re.sub(r"\W+"," ",s.lower()).strip()
            if norm and norm not in used:
                used.add(norm); parts.append(s)
                if len(" ".join(parts).split())>=limit: return " ".join(parts).split()[:limit]
    return " ".join(parts).split()[:limit]

def event_key(e):
    return e.get("url") or hashlib.sha1((e.get("time","")+e.get("title","")).encode()).hexdigest()

def source_list(events):
    seen=set(); out=[]
    for e in events:
        for link in e.get("links",[]):
            u=link.get("url")
            if u and u not in seen:
                seen.add(u); out.append({"name":link.get("label","Source"),"url":u,"type":link.get("type","article")})
    return out

def build():
    DATA.mkdir(exist_ok=True); DAYS.mkdir(exist_ok=True)
    config=load(SOURCES,[])
    articles=[]; health=[]
    for s in config:
        rows=read_feed(s); articles.extend(rows)
        health.append({"name":s["name"],"type":s.get("type"),"status":"ok" if rows else "no data/error","items":len(rows)})
    articles=list({x["url"]:x for x in articles}.values())

    groups=[]
    for a in sorted(articles,key=lambda x:x["published"],reverse=True):
        best_score=0; best_group=None
        for g in groups:
            sc=similarity(a["title"],g[0]["title"])
            if sc>best_score:
                best_score=sc; best_group=g
        if best_score>=.35: best_group.append(a)
        else: groups.append([a])

    old=load(ARCHIVE,{"issues":[]}).get("issues",[])
    issues=[]
    for group in groups:
        group.sort(key=lambda x:x["published"])
        lead=max(group,key=lambda x:len(x["title"]))
        previous_match=max(((similarity(lead["title"],o.get("title","")),o) for o in old),default=(0,None))
        previous=previous_match[1] if previous_match[0]>=.32 else None
        events=previous.get("timeline",[])[:] if previous else []
        seen={event_key(e) for e in events}
        for x in group:
            e={"time":x["published"],"title":x["title"],"description":x["summary"],"source":x.get("publisher",x["source"]),"url":x["url"],"links":x["links"]}
            if event_key(e) not in seen: events.append(e)
        events.sort(key=lambda e:e.get("time",""))
        brief=make_summary(group,50)
        detailed=make_summary(group,100)
        issues.append({
          "id":previous["id"] if previous else hashlib.sha1(key_title(lead["title"]).encode()).hexdigest()[:12],
          "title":lead["title"],
          "brief_summary":" ".join(brief),
          "summary_100":" ".join(detailed),
          "category":"India",
          "status":previous.get("status","Monitoring") if previous else "Monitoring",
          "score":score(group),
          "first_observed":events[0]["time"],
          "last_updated":events[-1]["time"],
          "authority":previous.get("authority","Not automatically inferred; official source required.") if previous else "Not automatically inferred; official source required.",
          "timeline":events,
          "sources":source_list(events)
        })

    byid={x.get("id"):x for x in old}
    for x in issues: byid[x["id"]]=x
    ARCHIVE.write_text(json.dumps({"updated_at":now().isoformat(),"issues":sorted(byid.values(),key=lambda x:x.get("last_updated",""),reverse=True)},ensure_ascii=False,indent=2))

    day=now().date().isoformat()
    top=sorted(issues,key=lambda x:x["score"],reverse=True)[:10]
    for n,x in enumerate(top,1):
        x["rank"]=n
        x["snapshot_date"]=day
    OUT.write_text(json.dumps({"generated_at":now().isoformat(),"snapshot_date":day,"issues":top},ensure_ascii=False,indent=2))

    day_file=DAYS/f"{day}.json"
    day_file.write_text(json.dumps({"date":day,"label":now().strftime("%d %b %Y"),"generated_at":now().isoformat(),"issues":[{"id":x["id"],"rank":x["rank"],"title":x["title"],"brief_summary":x["brief_summary"],"status":x["status"],"score":x["score"],"last_updated":x["last_updated"]} for x in top]},ensure_ascii=False,indent=2))
    idx=load(DAYS/"index.json",{"days":[]})
    bydate={d.get("date"):d for d in idx.get("days",[])}
    bydate[day]={"date":day,"label":now().strftime("%d %b %Y"),"file":f"data/days/{day}.json","count":len(top)}
    (DAYS/"index.json").write_text(json.dumps({"updated_at":now().isoformat(),"days":sorted(bydate.values(),key=lambda x:x["date"],reverse=True)},ensure_ascii=False,indent=2))

    PIPELINE.write_text(json.dumps({"generated_at":now().isoformat(),"article_count":len(articles),"candidate_issue_count":len(issues),"top10_count":len(top),"source_count":len(config),"source_health":health,"cost_policy":"$0 only"},ensure_ascii=False,indent=2))
    print("Collected",len(articles),"articles; generated",len(top),"Top 10 for",day)

if __name__=="__main__": build()
