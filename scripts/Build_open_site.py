"""Build the latest HTML site and serve it on localhost.

Usage:
    python scripts/Build_open_site.py
    python scripts/Build_open_site.py --port 8888 --page index.html --no-browser
"""
from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DOCS_ROOT = ROOT / "docs"

sys.path.insert(0, str(SRC))


def _build_site(args: argparse.Namespace) -> Path:
    from bluetooth_news.cli import main as build_main

    build_args = [
        "--max-age-days",
        str(args.max_age_days),
        "--limit",
        str(args.limit),
    ]
    if args.no_enrich:
        build_args.append("--no-enrich")
    if args.no_external:
        build_args.append("--no-external")
    if args.refresh_llm:
        build_args.append("--refresh-llm")
    if args.verbose:
        build_args.append("--verbose")

    print("Building the latest site...")
    exit_code = build_main(build_args)
    if exit_code != 0:
        raise SystemExit(exit_code)

    index = DOCS_ROOT / "index.html"
    if not index.exists():
        raise FileNotFoundError(f"Expected generated site at {index}")
    return DOCS_ROOT


def _serve(site_dir: Path, host: str, port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site_dir))
    with socketserver.ThreadingTCPServer((host, port), handler) as httpd:
        httpd.daemon_threads = True
        url = f"http://{host}:{port}/index.html"
        print(f"Serving {site_dir} at {url}")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopping server...")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the latest site and open it on localhost.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument("--page", default="index.html", help="Page to open after serving (for example customers.html)")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--max-age-days", type=int, default=550)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--no-enrich", action="store_true")
    parser.add_argument("--no-external", action="store_true")
    parser.add_argument("--refresh-llm", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    site_dir = _build_site(args)
    url = f"http://{args.host}:{args.port}/{args.page.lstrip('/')}"

    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    _serve(site_dir, args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())