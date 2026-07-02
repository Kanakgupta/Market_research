# Bluetooth News Aggregator

Aggregates Bluetooth-related news from across the internet (RSS feeds, Google News, Bing News, and optionally NewsAPI), deduplicates entries, and produces a timestamped HTML report.

## Features

- Pulls from multiple curated sources (Bluetooth SIG, Bluetooth.com, vendor blogs, Google News RSS, Bing News RSS).
- Optional [NewsAPI](https://newsapi.org/) integration when an API key is provided.
- Deduplicates by URL and normalized title.
- Sorts by published date (newest first).
- Generates a self-contained HTML report under `output/`.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # then edit .env if you have a NEWSAPI_KEY
```

## Run

```powershell
python -m bluetooth_news.cli
```

To rebuild the latest site and serve it on localhost:

```powershell
python scripts/serve_latest_site.py
```

Optional flags:

```powershell
python -m bluetooth_news.cli --max-age-days 14 --limit 200 --open
```

- `--max-age-days N` — only include articles newer than N days (default 30).
- `--limit N` — cap total articles in the report (default 500).
- `--open` — open the generated report in your default browser.

## Project layout

```
src/bluetooth_news/
  sources.py      # RSS feed + Google/Bing News query definitions
  fetcher.py      # Network fetching (RSS + NewsAPI)
  aggregator.py   # Normalization, dedup, sort
  report.py       # HTML report rendering
  cli.py          # Command-line entry point
output/           # Generated HTML reports (gitignored)
```

## Extending

Add new RSS feeds to `RSS_FEEDS` in [src/bluetooth_news/sources.py](src/bluetooth_news/sources.py). Add new search terms to `SEARCH_QUERIES` to expand Google/Bing News coverage.
