#!/usr/bin/env python3
"""Validate the public news data and optional RAG index without network calls."""
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
def load(name):
    path=DATA/name
    if not path.exists(): raise ValueError(f"Missing required file: data/{name}")
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc: raise ValueError(f"Invalid JSON in data/{name}: {exc}")
def main():
    latest=load("issues.json")
    if not isinstance(latest,dict) or not isinstance(latest.get("issues"),list):
        raise ValueError("issues.json must contain an issues array")
    issues=latest["issues"]
    if not issues: raise ValueError("issues.json has no issues")
    missing=[x.get("title","<untitled>") for x in issues if not x.get("id") or not x.get("title")]
    if missing: raise ValueError(f"{len(missing)} issue(s) missing id/title")
    ids=[x["id"] for x in issues]
    if len(ids)!=len(set(ids)): raise ValueError("Duplicate issue IDs in issues.json")
    for issue in issues:
        if not isinstance(issue.get("timeline",[]),list): raise ValueError(f"Timeline is not a list: {issue['title']}")
    print(f"PASS: issues.json has {len(issues)} valid issues, unique IDs and list timelines")
    if (DATA/"rag_index.json").exists():
        idx=load("rag_index.json")
        docs=idx.get("documents",[])
        if not isinstance(docs,list): raise ValueError("rag_index.json documents must be a list")
        if idx.get("document_count")!=len(docs): raise ValueError("RAG document_count mismatch")
        for doc in docs:
            if not doc.get("id") or not isinstance(doc.get("vector"),dict):
                raise ValueError("RAG document missing id or sparse vector")
        print(f"PASS: rag_index.json has {len(docs)} documents")
    else:
        print("INFO: rag_index.json not present; run Build vector index")
    print("Validation completed.")
if __name__=="__main__":
    try: main()
    except ValueError as exc:
        print("VALIDATION FAILED:",exc); sys.exit(1)
