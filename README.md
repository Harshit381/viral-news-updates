# Viral News Updates

A free-first, issue-centric news tracker. The project groups public RSS/news signals into issues and keeps a chronological timeline so important stories can be followed after they stop trending.

## $0 architecture

- GitHub repository: source code and data
- GitHub Pages: static website
- GitHub Actions: scheduled RSS collection and deployment
- Python standard library only: RSS parsing, scoring, clustering and JSON generation
- Public RSS feeds: initial data sources
- No paid APIs, paid hosting, paid database, or paid AI API in V1

## Important cost rule

This repository intentionally avoids services that can introduce a bill. If a future feature needs a paid quota, billing account, credit card, or a service that can automatically charge money, do not implement that feature. Find a genuinely free alternative first and document the trade-off.

## V1 limitations

Social-media ingestion is not enabled yet. We will add public/free sources only when they can be used without paid API access or risky scraping.

AI APIs are also deliberately excluded from V1. The first ranking and grouping engine is deterministic so the project remains $0.

## Run locally

Requires Python 3.10+.

```bash
python scripts/update_news.py
```

Then serve the repository root with any local static server, or open `index.html`.

## GitHub Pages

1. Open Settings → Pages.
2. Set the source to GitHub Actions.
3. The `deploy.yml` workflow publishes the site.
4. The `update-news.yml` workflow refreshes the RSS data on schedule.

GitHub Actions is used only with standard runners in this public repository.

## Data model

An issue contains:
- title
- summary
- category
- status
- first/last observed timestamps
- responsible body, when identifiable from source text
- timeline events
- source links
- evidence notes

The system never treats a lack of reporting as proof that an issue is unresolved. It records the latest observed information and uncertainty.

## Roadmap

1. Free RSS ingestion
2. Deterministic issue clustering and Top 10 scoring
3. Better source normalization
4. Persistent issue history
5. Public official-source monitoring
6. Free social/public signals where legitimately accessible
7. Search and filters
8. Only later: evaluate upgrades based on user feedback, with cost approval before implementation
