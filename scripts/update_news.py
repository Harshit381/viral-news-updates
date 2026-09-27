"""Free RSS ingestion and deterministic issue grouping for Viral News Updates.
No third-party Python packages and no paid API.
"""
import json, re, hashlib
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCES=ROOT/"sources.json"
OUT=ROOT/"data/issues.json"
USER_AGENT="ViralNewsUpdates/0.1 (+https://github.com/Harshit381/viral-news-updates)"

def now(): return datetime.now(timezone.utc)

def parse_date(value):
    if not value: return now()
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except Exception:
        try: return datetime.fromisoformat(value.replace("Z","+00:00")).astimezone(timezone.utc)
        except Exception: return now()

def clean(text):
    text=re.sub(r"<[^>]+>"," ",text or "")
    return re.sub(r"\s+"," ",text).strip()

def tag_text(el, name):
    x=el.find(name)
    if x is None:
        x=el.find("{*}"+name)
    return clean(x.text if x is not None else "")

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":USER_AGENT})
    with urllib.request.urlopen(req,timeout=20) as r:
        return r.read()

def read_feed(source):
    try:
        root=ET.fromstring(fetch(source["url"]))
    except Exception as exc:
        print("Feed failed:",source["name"],exc)
        return []
    items=[]
    for item in root.findall(".//item") + root.findall(".//{*}entry"):
        title=tag_text(item,"title")
        link=tag_text(item,"link")
        if not link:
            link_el=item.find("{*}link")
            if link_el is not None: link=link_el.attrib.get("href","")
        desc=tag_text(item,"description") or tag_text(item,"summary")
        date=tag_text(item,"pubDate") or tag_text(item,"published") or tag_text(item,"updated")
        if title and link:
            items.append({"title":title,"summary":desc,"url":link,"published":parse_date(date).isoformat(),"source":source["name"],"weight":source.get("weight",1)})
    return items

def normalize(title):
    words=re.findall(r"[a-z0-9]{3,}",title.lower())
    stop={"india","today","latest","news","report","says","said","update","live","breaking","after","over","amid"}
    return set(w for w in words if w not in stop)

def similarity(a,b):
    aa,bb=normalize(a),normalize(b)
    if not aa or not bb: return 0
    return len(aa&bb)/max(1,len(aa|bb))

def score(items):
    sources=len({x["source"] for x in items})
    latest=max(parse_date(x["published"]) for x in items)
    age=max(0,(now()-latest).total_seconds()/3600)
    recency=max(0,24-age)/24
    return round(sources*10 + sum(x["weight"] for x in items)*2 + recency*5,2)

def build():
    sources=json.loads(SOURCES.read_text())
    articles=[]
    for source in sources:
        articles.extend(read_feed(source))
    # Keep the newest occurrence of an identical URL.
    unique={x["url"]:x for x in articles}
    articles=list(unique.values())
    groups=[]
    for article in sorted(articles,key=lambda x:x["published"],reverse=True):
        placed=False
        for group in groups:
            if similarity(article["title"],group[0]["title"])>=0.35:
                group.append(article); placed=True; break
        if not placed: groups.append([article])
    issues=[]
    for group in groups:
        if not group: continue
        group=sorted(group,key=lambda x:x["published"])
        lead=max(group,key=lambda x:len(x["title"]))
        events=[{"time":x["published"],"title":x["title"],"description":x["summary"],"source":x["source"],"url":x["url"]} for x in group]
        issues.append({
            "id":hashlib.sha1(("|".join(x["url"] for x in group)).encode()).hexdigest()[:12],
            "title":lead["title"],
            "summary":lead["summary"] or "Multiple public sources are reporting this issue.",
            "category":"India",
            "status":"Monitoring",
            "score":score(group),
            "first_observed":group[0]["published"],
            "last_updated":group[-1]["published"],
            "authority":"Not automatically inferred; verify from official sources.",
            "timeline":events,
            "sources":[{"name":x["source"],"url":x["url"]} for x in group]
        })
    issues=sorted(issues,key=lambda x:x["score"],reverse=True)[:10]
    for n,i in enumerate(issues,1): i["rank"]=n
    OUT.write_text(json.dumps({"generated_at":now().isoformat(),"issues":issues},ensure_ascii=False,indent=2))
    print(f"Collected {len(articles)} articles; generated {len(issues)} issues.")

if __name__=="__main__":
    build()
