#!/usr/bin/env python3
"""Build a free, local TF-IDF-style hashed vector index for RAG retrieval.

No external packages, model downloads, API keys, database server, or paid services.
Vectors are sparse feature-hashed term/bigram vectors; cosine similarity retrieves
candidate evidence. This is lexical retrieval, not a neural semantic embedding.
"""
import json, math, re, hashlib
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
INDEX = DATA / "rag_index.json"
DIMENSIONS = 2048
TOKEN_RE = re.compile(r"[a-z0-9]{2,}", re.I)
STOP = {"the","and","for","with","from","that","this","are","was","were","has","have","had","will","into","after","over","under","says","said","its","their","about","today","latest","news","update","india","indian"}

def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default

def tokens(text):
    words=[w.lower() for w in TOKEN_RE.findall(str(text or "")) if w.lower() not in STOP]
    return words + [words[i]+"_"+words[i+1] for i in range(len(words)-1)]

def vectorize(text):
    counts={}
    for token in tokens(text):
        h=2166136261
        for byte in token.encode("utf-8"):
            h=((h ^ byte) * 16777619) & 0xffffffff
        idx=h % DIMENSIONS
        counts[idx]=counts.get(idx,0)+1
    norm=math.sqrt(sum(v*v for v in counts.values())) or 1.0
    return {str(k):round(v/norm,6) for k,v in counts.items()}

def get_issue_list(payload):
    if isinstance(payload,list): return payload
    if isinstance(payload,dict):
        for key in ("issues","items","archive"):
            if isinstance(payload.get(key),list): return payload[key]
        if all(isinstance(v,dict) for v in payload.values()):
            return list(payload.values())
    return []

def main():
    latest=read_json(DATA/"issues.json",{})
    archive=read_json(DATA/"issue_archive.json",{})
    by_id={}
    for item in get_issue_list(archive)+get_issue_list(latest):
        if not isinstance(item,dict): continue
        title=str(item.get("title") or "").strip()
        if not title: continue
        ident=str(item.get("id") or hashlib.sha1(title.lower().encode()).hexdigest()[:12])
        prev=by_id.get(ident,{})
        # Prefer the more recently updated representation while retaining a usable summary.
        merged=dict(prev); merged.update({k:v for k,v in item.items() if v not in (None,"",[])})
        by_id[ident]=merged
    docs=[]
    for ident,item in by_id.items():
        timeline=item.get("timeline") or []
        sources=item.get("sources") or []
        evidence=[]
        for ev in timeline[:80]:
            if not isinstance(ev,dict): continue
            evidence.append({"time":ev.get("time") or ev.get("date") or "",
                             "title":ev.get("title") or "",
                             "description":ev.get("description") or "",
                             "source":ev.get("source") or ev.get("publisher") or "",
                             "url":ev.get("url") or ""})
        source_links=[]
        for s in sources[:30]:
            if isinstance(s,dict) and s.get("url"):
                source_links.append({"name":s.get("source") or s.get("publisher") or "",
                                     "url":s["url"]})
            elif isinstance(s,str) and s.startswith("http"):
                source_links.append({"name":"","url":s})
        text=" ".join([item.get("title",""),item.get("brief_summary",""),item.get("summary_100",""),item.get("category","")]+[e["title"]+" "+e["description"] for e in evidence[:20]])
        docs.append({"id":ident,"title":item.get("title",""),"summary":item.get("brief_summary") or item.get("summary_100") or "",
                     "category":item.get("category") or "Uncategorised","status":item.get("status") or "",
                     "first_observed":item.get("first_observed") or "","last_updated":item.get("last_updated") or "",
                     "url":source_links[0]["url"] if source_links else "",
                     "sources":source_links[:12],"timeline":evidence[:20],"vector":vectorize(text)})
    docs.sort(key=lambda d:(d.get("last_updated",""),d["id"]),reverse=True)
    payload={"schema_version":1,"generated_at":datetime.now(timezone.utc).isoformat(),
             "method":"hashed TF-IDF-style sparse term+bigram vectors; cosine similarity",
             "dimensions":DIMENSIONS,"document_count":len(docs),"documents":docs}
    INDEX.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(f"RAG index built: {len(docs)} issue documents; {DIMENSIONS} hash dimensions; {INDEX.stat().st_size} bytes")

if __name__=="__main__": main()
