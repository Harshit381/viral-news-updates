import json,re,hashlib,urllib.request,xml.etree.ElementTree as ET,html
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
STOP={"india","today","latest","news","report","reports","says","said","update","live","breaking","after","over","amid","new","will","from","into","with","this","that","the","and","for","has","have","its","their","were","been","video","videos","watch","viral","top","live","story","stories","photo","photos","picture","pictures","clip","clips"}

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
    value=html.unescape(value or "")
    return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",value)).strip()

def raw_child(el,name):
    for x in list(el):
        if x.tag.rsplit("}",1)[-1]==name:
            return x.text or ""
    return ""

def local_text(el):
    return el.text if el is not None else ""

def children_text(el,name):
    for x in list(el):
        if x.tag.rsplit("}",1)[-1]==name:
            return clean(local_text(x))
    return ""

def links_from_item(item,primary):
    out=[]
    if primary:
        out.append({"type":"article","url":primary,"label":"Open article"})
    seen={primary}
    for x in item.iter():
        local=x.tag.rsplit("}",1)[-1].lower()
        u=x.attrib.get("url") or x.attrib.get("href")
        if not u or u in seen:
            continue
        typ=(x.attrib.get("type") or "").lower()
        medium=(x.attrib.get("medium") or "").lower()
        is_video=("video" in typ or medium=="video" or re.search(r"\.(mp4|webm|mov|m3u8)(\?|$)",u.lower()) is not None)
        if local in {"enclosure","content"} and is_video:
            out.append({"type":"video","url":u,"label":"Open video"})
            seen.add(u)
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
        raw_desc=raw_child(item,"description") or raw_child(item,"summary") or raw_child(item,"content")
        publisher=children_text(item,"source") or source["name"]
        if source.get("type")=="aggregator":
            parts=[p.strip() for p in re.split(r"&nbsp;\\s*&nbsp;|\\s{2,}",raw_desc,flags=re.I) if p.strip()]
            desc=clean(parts[0] if parts else raw_desc)
        else:
            desc=clean(raw_desc)[:1200]
        when=children_text(item,"pubDate") or children_text(item,"published") or children_text(item,"updated")
        if title and link:
            items.append({"title":display_title(title,publisher),"summary":desc,"url":link,"published":parse_date(when).isoformat(),"source":source["name"],"publisher":publisher,"weight":source.get("weight",1),"type":source.get("type","publisher"),"links":links_from_item(item,link)})
    return items

def words(title):
    return {w for w in re.findall(r"[a-z0-9]{3,}",title.lower()) if w not in STOP}

def similarity(a,b):
    x,y=words(a),words(b)
    if not x or not y: return 0
    inter=len(x&y)
    jaccard=inter/max(1,len(x|y))
    containment=inter/max(1,min(len(x),len(y)))
    return max(jaccard, containment*0.85)

def key_title(title):
    return "|".join(sorted(words(title)))

def score(items):
    sources=len({x.get("publisher",x["source"]) for x in items})
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
                if len(" ".join(parts).split())>=limit:
                    return " ".join(parts).split()[:limit]
    return " ".join(parts).split()[:limit]

def fallback_summary(title,items,limit):
    publishers=sorted({x.get("publisher",x["source"]) for x in items})
    latest=max(items,key=lambda x:x["published"])
    text=(f"{title}. This issue is being tracked across {len(publishers)} distinct public publisher(s). "
          f"The latest observed feed update was published by {latest.get('publisher',latest['source'])}. "
          f"Source links are provided below for the underlying reports and later developments.")
    return " ".join(text.split()[:limit])

def coverage_digest(title,items,limit=100):
    lines=[f"{title}. Available public feed coverage is summarized here; this digest does not add facts beyond the linked sources."]
    for x in sorted(items,key=lambda a:a["published"],reverse=True):
        line=f" {x.get('publisher',x['source'])}: {x['title']}."
        if x.get("summary"): line+=" "+x["summary"]
        lines.append(line)
        if len(" ".join(lines).split())>=limit: break
    return " ".join(" ".join(lines).split()[:limit])

def event_key(e):
    return e.get("url") or hashlib.sha1((e.get("time","")+e.get("title","")).encode()).hexdigest()

def display_title(title,publisher):
    title=clean(title)
    suffixes=[publisher,"The Hindu","The Times of India","Times of India","News On AIR","ANI News","NDTV","India Today"]
    for suffix in suffixes:
        tail=" - "+suffix
        if title.lower().endswith(tail.lower()): return title[:-len(tail)].rstrip()
    return title

def source_list(events):
    seen=set(); out=[]
    for e in events:
        for link in e.get("links",[]):
            u=link.get("url")
            if u and u not in seen:
                seen.add(u); out.append({"name":("Video — " if link.get("type")=="video" else "Article — ")+e.get("source","Source"),"url":u,"type":link.get("type","article")})
    return out

def build():
    DATA.mkdir(exist_ok=True); DAYS.mkdir(exist_ok=True)
    config=load(SOURCES,[])
    articles=[]; health=[]
    for s in config:
        rows=read_feed(s); articles.extend(rows)
        health.append({"name":s["name"],"type":s.get("type"),"status":"ok" if rows else "no data/error","items":len(rows)})
    articles=list({x["url"]:x for x in articles}.values())
    cutoff=(now()-__import__("datetime").timedelta(hours=24)).timestamp()
    articles=[x for x in articles if parse_date(x["published"]).timestamp()>=cutoff]

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
        lead=max(group,key=lambda x:(1 if x["type"]!="aggregator" else 0, len(x.get("summary","")), len(x["title"])))
        previous_match=max(((similarity(lead["title"],o.get("title","")),o) for o in old),default=(0,None))
        previous=previous_match[1] if previous_match[0]>=.32 else None
        events=previous.get("timeline",[])[:] if previous else []
        seen={event_key(e) for e in events}
        for x in group:
            e={"time":x["published"],"title":x["title"],"description":x["summary"],"source":x.get("publisher",x["source"]),"publisher":x.get("publisher",x["source"]),"url":x["url"],"links":x["links"]}
            if event_key(e) not in seen: events.append(e)
        events.sort(key=lambda e:e.get("time",""))
        summary_items=[x for x in group if x.get("summary")] or group
        brief=" ".join(make_summary(summary_items,50))
        if len(brief.split())<30: brief=fallback_summary(lead["title"],group,40)
        detailed=" ".join(make_summary(summary_items,100))
        if len(detailed.split())<70: detailed=coverage_digest(lead["title"],group,100)
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

    issues=[x for x in issues if len(words(x["title"]))>=3 or x.get("brief_summary") or x.get("summary_100")]
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
