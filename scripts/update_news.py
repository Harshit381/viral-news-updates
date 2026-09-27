import json,re,hashlib,urllib.request,xml.etree.ElementTree as ET,html
from pathlib import Path
from datetime import datetime,timezone,timedelta
from email.utils import parsedate_to_datetime

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
SOURCES=ROOT/"sources.json"
OUT=DATA/"issues.json"
ARCHIVE=DATA/"issue_archive.json"
DAYS=DATA/"days"
PIPELINE=DATA/"pipeline.json"
UA="ViralNewsUpdates/0.4 (+https://github.com/Harshit381/viral-news-updates)"

STOP={
    "india","indian","today","latest","news","report","reports","says","said","say","update","updates",
    "live","breaking","after","over","amid","new","will","from","into","with","this","that","the","and",
    "for","has","have","its","their","were","been","being","video","videos","watch","viral","top","live",
    "story","stories","photo","photos","picture","pictures","clip","clips","official","officials",
    "government","govt","ministry","minister","department","state","country","city","people","according",
    "day","days","full","results","result","campaign","action","coverage","newsroom","year","years"
}

CATEGORY_RULES=[
    ("Sports",{"asian","games","cricket","football","soccer","badminton","squash","hockey","tennis","medal","medals","olympic","athlete","athletes","match","tournament"}),
    ("Technology",{"ai","artificial","intelligence","semiconductor","semiconductors","quantum","chip","chips","technology","tech","cyber","google","microsoft","apple","startup","startups"}),
    ("Business",{"economy","economic","growth","gdp","market","markets","rupee","tax","taxes","budget","investment","investments","bank","banks","finance","financial","trade","industry","industries"}),
    ("Crime & Safety",{"crime","police","arrest","arrested","murder","murdered","fraud","scam","scams","theft","stolen","missing","accident","fire","attack","attacked"}),
    ("Karnataka",{"karnataka","bengaluru","bangalore","mysuru","mysore"}),
    ("Politics & Government",{"election","elections","parliament","parliamentary","court","courts","supreme","cabinet","bill","bills","law","laws","policy","policies","modi","president","congress","bjp","lok","sabha"}),
    ("World",{"russia","ukraine","israel","iran","china","america","american","united","states","europe","pakistan","nepal","bangladesh","japan"})
]

def now():
    return datetime.now(timezone.utc)

def load(path,default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default

def parse_date(value):
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except Exception:
        try:
            return datetime.fromisoformat((value or "").replace("Z","+00:00")).astimezone(timezone.utc)
        except Exception:
            return now()

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

def clean_feed_summary(title,raw_desc,publisher,is_aggregator):
    text=html.unescape(raw_desc or "")
    fragments=[clean(p) for p in re.split(r"&nbsp;\s*&nbsp;|\s{2,}|\s+\|\s+",text) if clean(p)]
    if not fragments:
        fragments=[clean(text)]
    candidates=[]
    title_norm=" ".join(words(title))
    for part in fragments:
        part=re.sub(r"\s+-\s+"+re.escape(publisher)+r"$","",part,flags=re.I).strip()
        part=re.sub(r"\s+"+re.escape(publisher)+r"$","",part,flags=re.I).strip()
        norm=" ".join(words(part))
        if not part or (norm and norm==title_norm):
            continue
        candidates.append(part)
    if candidates:
        return max(candidates,key=len)[:1200] if not is_aggregator else candidates[0][:500]
    return ""

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
        publisher=children_text(item,"source") or source["name"]
        raw_desc=raw_child(item,"description") or raw_child(item,"summary") or raw_child(item,"content")
        desc=clean_feed_summary(title,raw_desc,publisher,source.get("type")=="aggregator")
        when=children_text(item,"pubDate") or children_text(item,"published") or children_text(item,"updated")
        if title and link:
            items.append({
                "title":display_title(title,publisher),
                "summary":desc,
                "url":link,
                "published":parse_date(when).isoformat(),
                "source":source["name"],
                "publisher":publisher,
                "weight":source.get("weight",1),
                "type":source.get("type","publisher"),
                "links":links_from_item(item,link)
            })
    return items

def words(title):
    return {w for w in re.findall(r"[a-z0-9]{3,}",title.lower()) if w not in STOP and not w.isdigit()}

def ordered_words(title):
    return [w for w in re.findall(r"[a-z0-9]{3,}",title.lower()) if w not in STOP and not w.isdigit()]

def bigrams(title):
    ws=ordered_words(title)
    return set(zip(ws,ws[1:]))

def similarity(a,b,idf=None):
    x,y=words(a),words(b)
    if not x or not y:
        return 0
    inter=x&y
    if len(inter)<2:
        return 0
    if idf:
        num=sum(idf.get(t,1.0) for t in inter)
        den=sum(idf.get(t,1.0) for t in x|y) or 1
        weighted=num/den
    else:
        weighted=len(inter)/len(x|y)
    contain=len(inter)/min(len(x),len(y))
    phrase=bool(bigrams(a)&bigrams(b))
    return max(weighted,contain*0.78,0.66 if phrase and len(inter)>=2 else 0)

def normalized_title(title):
    return " ".join(ordered_words(title))

def key_title(title):
    return "|".join(sorted(words(title)))

def category_for(title):
    ws=words(title)
    for name,signals in CATEGORY_RULES:
        if len(ws&signals)>=1:
            return name
    return "India"

def source_count(items):
    return len({x.get("publisher") or x.get("source") for x in items if x.get("publisher") or x.get("source")})

def score(items):
    sources=source_count(items)
    official=sum(x["type"]=="official" for x in items)
    latest=max(parse_date(x["published"]) for x in items)
    age=max(0,(now()-latest).total_seconds()/3600)
    volume=min(len(items),8)
    return round(sources*10+volume*1.75+sum(x["weight"] for x in items)*1.5+official*4+max(0,24-age)/24*5,2)

def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+",clean(text)) if s.strip()]

def make_summary(items,limit):
    used=set()
    parts=[]
    for x in sorted(items,key=lambda a:a["published"],reverse=True):
        for s in sentences(x.get("summary","")):
            norm=" ".join(words(s))
            if not norm or norm in used:
                continue
            if normalized_title(s)==normalized_title(x.get("title","")):
                continue
            used.add(norm)
            parts.append(s)
            if len(" ".join(parts).split())>=limit:
                return " ".join(" ".join(parts).split()[:limit])
    return " ".join(" ".join(parts).split()[:limit])

def fallback_summary(title,items,limit=45):
    publishers=[]
    for x in sorted(items,key=lambda a:a["published"],reverse=True):
        p=x.get("publisher") or x.get("source")
        if p and p not in publishers:
            publishers.append(p)
        if len(publishers)>=3:
            break
    coverage=", ".join(publishers) if publishers else "public news feeds"
    text=(f"{title}. Coverage from {coverage} is grouped here as one tracked issue. "
          f"Repeated reports are consolidated while distinct developments remain in chronological order. "
          f"Each update keeps its available article or video links so the story can be followed beyond the initial viral moment.")
    return " ".join(text.split()[:limit])

def coverage_digest(title,items,limit=100):
    parts=[f"{title}. The tracker consolidates related public reporting into one chronological record."]
    for x in sorted(items,key=lambda a:a["published"],reverse=True):
        p=x.get("publisher") or x.get("source")
        s=x.get("summary","").strip()
        if s:
            parts.append(f"{p}: {s}.")
        else:
            parts.append(f"{p}: {x.get('title','')}.")
        if len(" ".join(parts).split())>=limit:
            break
    return " ".join(" ".join(parts).split()[:limit])

def event_key(e):
    return e.get("url") or hashlib.sha1((e.get("time","")+e.get("title","")).encode()).hexdigest()

def display_title(title,publisher):
    title=clean(title)
    suffixes=[publisher,"The Hindu","The Times of India","Times of India","News On AIR","ANI News","NDTV","India Today"]
    for suffix in suffixes:
        if not suffix:
            continue
        tail=" - "+suffix
        if title.lower().endswith(tail.lower()):
            return title[:-len(tail)].rstrip()
    return title

def merge_event(base,incoming):
    links=list(base.get("links",[]))
    seen={l.get("url") for l in links if l.get("url")}
    for link in incoming.get("links",[]):
        u=link.get("url")
        if u and u not in seen:
            links.append(link); seen.add(u)
    sources=[]
    for item in [base,incoming]:
        for p in item.get("source_names",[]) or [item.get("source")]:
            if p and p not in sources:
                sources.append(p)
    title=max([base.get("title",""),incoming.get("title","")],key=lambda s:len(s))
    description=max([base.get("description",""),incoming.get("description","")],key=lambda s:len(s))
    return {
        "time":min(base.get("time",""),incoming.get("time","")),
        "title":title,
        "description":description,
        "source":sources[0] if len(sources)==1 else "Multiple sources",
        "publisher":sources[0] if sources else base.get("publisher",""),
        "source_names":sources,
        "url":base.get("url") or incoming.get("url"),
        "links":links
    }

def collapse_events(events):
    out=[]
    for e in sorted(events,key=lambda x:x.get("time","")):
        match=None
        for i,existing in enumerate(out):
            same_url=e.get("url") and e.get("url")==existing.get("url")
            try:
                hours=abs((parse_date(e.get("time"))-parse_date(existing.get("time"))).total_seconds())/3600
            except Exception:
                hours=999
            close_title=similarity(e.get("title",""),existing.get("title",""))>=0.82
            exact=normalized_title(e.get("title",""))==normalized_title(existing.get("title",""))
            if same_url or exact or (close_title and hours<=96):
                match=i
                break
        if match is None:
            copy=dict(e)
            if not copy.get("source_names"):
                copy["source_names"]=[copy.get("source")] if copy.get("source") else []
            out.append(copy)
        else:
            out[match]=merge_event(out[match],e)
    for e in out:
        e["links"]=e.get("links",[])[:10]
        if len(e.get("source_names",[]))>1:
            e["source"]="Multiple sources"
    return sorted(out,key=lambda x:x.get("time",""))

def source_list(events):
    seen=set()
    out=[]
    for e in events:
        for link in e.get("links",[]):
            u=link.get("url")
            if u and u not in seen:
                seen.add(u)
                label=("Video — " if link.get("type")=="video" else "Article — ")+("Multiple sources" if e.get("source")=="Multiple sources" else e.get("source","Source"))
                out.append({"name":label,"url":u,"type":link.get("type","article")})
    return out

def cluster_articles(articles):
    if not articles:
        return []
    df={}
    for a in articles:
        for t in words(a["title"]):
            df[t]=df.get(t,0)+1
    n=len(articles)
    idf={t:1+__import__("math").log((n+1)/(freq+1)) for t,freq in df.items()}
    inverted={}
    for i,a in enumerate(articles):
        for t in words(a["title"]):
            inverted.setdefault(t,set()).add(i)

    parent=list(range(n))
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]
            x=parent[x]
        return x
    def union(a,b):
        ra,rb=find(a),find(b)
        if ra!=rb:
            parent[rb]=ra

    for i,a in enumerate(articles):
        candidates=set()
        for t in words(a["title"]):
            candidates.update(inverted.get(t,set()))
        for j in candidates:
            if j<=i:
                continue
            b=articles[j]
            if similarity(a["title"],b["title"],idf)>=0.42:
                union(i,j)

    groups={}
    for i,a in enumerate(articles):
        groups.setdefault(find(i),[]).append(a)
    return list(groups.values())

def merge_issue_records(base,other):
    events=collapse_events((base.get("timeline") or [])+(other.get("timeline") or []))
    merged=dict(base)
    merged["timeline"]=events
    merged["first_observed"]=events[0]["time"] if events else min(base.get("first_observed",""),other.get("first_observed",""))
    merged["last_updated"]=events[-1]["time"] if events else max(base.get("last_updated",""),other.get("last_updated",""))
    merged["sources"]=source_list(events)
    merged["source_count"]=len({p for e in events for p in (e.get("source_names") or [e.get("source")]) if p})
    if len(other.get("brief_summary",""))>len(base.get("brief_summary","")):
        merged["brief_summary"]=other["brief_summary"]
    if len(other.get("summary_100",""))>len(base.get("summary_100","")):
        merged["summary_100"]=other["summary_100"]
    return merged

def canonicalize_archive(records):
    canonical=[]
    for record in sorted(records,key=lambda x:x.get("last_updated",""),reverse=True):
        match=None
        for i,existing in enumerate(canonical):
            if similarity(record.get("title",""),existing.get("title",""))>=0.55:
                match=i
                break
        if match is None:
            canonical.append(record)
        else:
            canonical[match]=merge_issue_records(canonical[match],record)
    return canonical

def build():
    DATA.mkdir(exist_ok=True)
    DAYS.mkdir(exist_ok=True)
    config=load(SOURCES,[])
    articles=[]
    health=[]
    for s in config:
        rows=read_feed(s)
        articles.extend(rows)
        health.append({"name":s["name"],"type":s.get("type"),"status":"ok" if rows else "no data/error","items":len(rows)})

    articles=list({x["url"]:x for x in articles}.values())
    cutoff=(now()-timedelta(hours=24)).timestamp()
    articles=[x for x in articles if parse_date(x["published"]).timestamp()>=cutoff]

    groups=cluster_articles(sorted(articles,key=lambda x:x["published"],reverse=True))
    old=load(ARCHIVE,{"issues":[]}).get("issues",[])
    issues=[]

    for group in groups:
        group.sort(key=lambda x:x["published"])
        lead=max(group,key=lambda x:(
            1 if x["type"]!="aggregator" else 0,
            len(x.get("summary","")),
            len(x["title"])
        ))

        previous_matches=[
            o for o in old
            if similarity(lead["title"],o.get("title",""))>=0.55
        ]
        previous=None
        if previous_matches:
            previous=max(previous_matches,key=lambda o:(similarity(lead["title"],o.get("title","")),o.get("last_updated","")))
            for duplicate in previous_matches:
                if duplicate.get("id")!=previous.get("id"):
                    previous=merge_issue_records(previous,duplicate)

        events=previous.get("timeline",[])[:] if previous else []
        for x in group:
            events.append({
                "time":x["published"],
                "title":x["title"],
                "description":x.get("summary",""),
                "source":x.get("publisher",x["source"]),
                "publisher":x.get("publisher",x["source"]),
                "source_names":[x.get("publisher",x["source"])],
                "url":x["url"],
                "links":x["links"]
            })
        events=collapse_events(events)

        summary_items=[x for x in group if x.get("summary")] or group
        brief=make_summary(summary_items,50)
        if len(brief.split())<30:
            brief=fallback_summary(lead["title"],group,45)

        detailed=make_summary(summary_items,100)
        if len(detailed.split())<70:
            detailed=coverage_digest(lead["title"],group,100)

        issue={
            "id":previous["id"] if previous else hashlib.sha1(key_title(lead["title"]).encode()).hexdigest()[:12],
            "title":lead["title"],
            "brief_summary":brief,
            "summary_100":detailed,
            "category":category_for(lead["title"]),
            "status":previous.get("status","Monitoring") if previous else "Monitoring",
            "score":score(group),
            "first_observed":events[0]["time"] if events else lead["published"],
            "last_updated":events[-1]["time"] if events else lead["published"],
            "authority":previous.get("authority","Not automatically inferred; official source required.") if previous else "Not automatically inferred; official source required.",
            "timeline":events,
            "sources":source_list(events),
            "source_count":len({p for e in events for p in (e.get("source_names") or [e.get("source")]) if p})
        }
        issues.append(issue)

    issues=[x for x in issues if len(words(x["title"]))>=3 or x.get("brief_summary") or x.get("summary_100")]
    archive_pool=old[:]
    byid={x.get("id"):x for x in archive_pool if x.get("id")}
    for x in issues:
        byid[x["id"]]=x
    archive=canonicalize_archive(list(byid.values()))
    ARCHIVE.write_text(json.dumps({"updated_at":now().isoformat(),"issues":archive},ensure_ascii=False,indent=2))

    day=now().date().isoformat()

    ranked=sorted(issues,key=lambda x:x["score"],reverse=True)
    top=[]
    for candidate in ranked:
        if all(similarity(candidate["title"],selected["title"])<0.55 for selected in top):
            top.append(candidate)
        if len(top)>=10:
            break
    if len(top)<10:
        selected_ids={x["id"] for x in top}
        for candidate in ranked:
            if candidate["id"] not in selected_ids:
                top.append(candidate)
            if len(top)>=10:
                break

    for n,x in enumerate(top,1):
        x["rank"]=n
        x["snapshot_date"]=day

    OUT.write_text(json.dumps({"generated_at":now().isoformat(),"snapshot_date":day,"issues":top},ensure_ascii=False,indent=2))

    day_file=DAYS/f"{day}.json"
    day_file.write_text(json.dumps({
        "date":day,
        "label":now().strftime("%d %b %Y"),
        "generated_at":now().isoformat(),
        "issues":[{
            "id":x["id"],
            "rank":x["rank"],
            "title":x["title"],
            "brief_summary":x["brief_summary"],
            "status":x["status"],
            "category":x["category"],
            "score":x["score"],
            "last_updated":x["last_updated"],
            "source_count":x.get("source_count",0),
            "timeline_count":len(x.get("timeline",[]))
        } for x in top]
    },ensure_ascii=False,indent=2))

    idx=load(DAYS/"index.json",{"days":[]})
    bydate={d.get("date"):d for d in idx.get("days",[])}
    bydate[day]={"date":day,"label":now().strftime("%d %b %Y"),"file":f"data/days/{day}.json","count":len(top)}
    (DAYS/"index.json").write_text(json.dumps({"updated_at":now().isoformat(),"days":sorted(bydate.values(),key=lambda x:x["date"],reverse=True)},ensure_ascii=False,indent=2))

    PIPELINE.write_text(json.dumps({
        "generated_at":now().isoformat(),
        "article_count":len(articles),
        "candidate_issue_count":len(issues),
        "top10_count":len(top),
        "source_count":len(config),
        "source_health":health,
        "deduplication":{
            "method":"pairwise title similarity with rare-token weighting; near-duplicate timeline events are consolidated",
            "candidate_diversity_threshold":0.55,
            "timeline_similarity_threshold":0.82
        },
        "cost_policy":"$0 only"
    },ensure_ascii=False,indent=2))
    print("Collected",len(articles),"articles; generated",len(top),"diversified Top 10 for",day)

if __name__=="__main__":
    build()
