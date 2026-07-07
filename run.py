"""Convenience launcher.

Usage:
  python run.py             # build the IoT Wireless Intel site
    python run.py site-dev    # rebuild docs from local snapshot only (no fetch)
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))


def _site_dev(argv):
    """Render docs using local snapshots only (no feed/web fetch)."""
    import argparse

    from bluetooth_news.report import render

    p = argparse.ArgumentParser(prog="run.py site-dev")
    p.add_argument("--output-dir", default="docs")
    p.add_argument("--open", action="store_true")
    a = p.parse_args(argv)

    root = Path(__file__).parent
    briefing_path = root / "data" / "briefing_input.json"

    articles = []
    pulse = []
    patents = []
    filings = []

    if briefing_path.exists():
        try:
            payload = json.loads(briefing_path.read_text(encoding="utf-8"))
            articles = payload.get("headlines_last_7d", []) or []
            pulse = payload.get("github_pulse", []) or []
            patents = payload.get("patents", []) or []
            filings = payload.get("edgar_filings", []) or []
            print(f"[site-dev] loaded local snapshot from {briefing_path}")
        except Exception as exc:
            print(f"[site-dev] warning: could not parse {briefing_path}: {exc}")
    else:
        print(f"[site-dev] no snapshot found at {briefing_path}; rendering with empty local data")

    index = render(articles, Path(a.output_dir), pulse=pulse, patents=patents, filings=filings)
    print(f"[site-dev] site generated successfully in {a.output_dir}: {index}")

    if a.open:
        import webbrowser
        webbrowser.open(index.resolve().as_uri())

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "site-dev":
        _site_dev(sys.argv[2:])
        sys.exit(0)
    else:
        from bluetooth_news.cli import main
        sys.exit(main())

