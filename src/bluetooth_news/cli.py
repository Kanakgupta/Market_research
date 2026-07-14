"""CLI: aggregate IoT wireless news and emit a multi-page HTML site."""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .aggregator import process
from .fetcher import fetch_all
from .report import render
from .enrichment import enrich
from .cache import record_history
from .github_pulse import fetch_pulse
from .external_data import fetch_patents, fetch_edgar
from .briefing import write_inputs, synthesize_outputs
from .auto_update import auto_update_from_articles


# Deleted old helper functions since we now write directly to docs/ without duplication.


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Aggregate IoT wireless news into a multi-page HTML site.")
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=int(os.getenv("NEWS_LOOKBACK_DAYS", "30")),
        help="Max age for kept articles (default 30 days; override with NEWS_LOOKBACK_DAYS)",
    )
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--output-dir", type=Path, default=Path("docs"))
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--keep-old", action="store_true")
    parser.add_argument("--no-enrich", action="store_true",
                        help="Skip article body extraction (faster, less coverage)")
    parser.add_argument("--no-external", action="store_true",
                        help="Skip GitHub pulse + patents + EDGAR (offline mode)")
    parser.add_argument("--refresh-llm", action="store_true",
                        help="Regenerate briefing/roadmap LLM outputs even if cached")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    print("Fetching feeds...")
    raw = fetch_all()
    print(f"  raw entries: {len(raw)}")
    articles = process(raw, max_age_days=args.max_age_days, limit=args.limit, verbose=args.verbose)
    print(f"  after dedup/filter: {len(articles)}")

    if not args.no_enrich:
        print("Enriching articles (body extraction)...")
        articles = enrich(articles)

    # Record into history (for week-over-week deltas)
    today = datetime.now().strftime("%Y-%m-%d")
    record_history(today, articles)

    # Auto-update customers.json + competitors.json from live articles (LLM-powered)
    print("Auto-updating product catalog from live articles...")
    try:
        au = auto_update_from_articles(articles, force=args.refresh_llm)
        if au.get("skipped"):
            print(f"  skipped ({au.get('reason')})")
        else:
            print(f"  customers updated: {au['customers_updated']} ({au['customer_products_added']} products added)")
            print(f"  competitors updated: {au['competitors_updated']} ({au['competitor_press_added']} press releases added)")
            if au.get("errors"):
                for err in au["errors"]:
                    print(f"  warning: {err}")
    except Exception as e:
        print(f"  auto-update failed (site still generated): {e}")

    pulse, patents, filings = [], [], []
    if not args.no_external:
        print("GitHub pulse...")
        try: pulse = fetch_pulse()
        except Exception as e: print(f"  github pulse failed: {e}")
        print("USPTO patents...")
        try: patents = fetch_patents()
        except Exception as e: print(f"  patents failed: {e}")
        print("EDGAR filings...")
        try: filings = fetch_edgar()
        except Exception as e: print(f"  edgar failed: {e}")

    # Write LLM input snapshots (for chat-driven synthesis)
    try:
        write_inputs(articles, pulse, patents, filings)
        print("Wrote data/briefing_input.json + data/roadmap_input.json")
        synth = synthesize_outputs(force=args.refresh_llm)
        if synth.get("ok"):
            print("LLM synthesis ready: data/briefing_output.json + data/roadmap_output.json")
        else:
            print("  LLM synthesis partial/failed (site still generated):")
        for name, info in (synth.get("files") or {}).items():
            prefix = "  -"
            print(f"{prefix} {name}: {info.get('status')}")
    except Exception as e:
        print(f"  briefing inputs failed: {e}")

    index = render(articles, args.output_dir, pulse=pulse, patents=patents, filings=filings)
    print(f"Site generated successfully in {args.output_dir}: {index}")

    if args.open:
        webbrowser.open(index.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
