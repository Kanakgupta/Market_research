"""Run the local report server AND AIROC AI server continuously with daily 4 PM refresh.

This script:
1. Serves output/latest on http://127.0.0.1:8888/index.html (report server)
2. Starts the AIROC AI server on http://127.0.0.1:5005 (AI chat)
3. Rebuilds the site every day at 4:00 PM local time.
4. Restarts servers if they exit unexpectedly.

Run manually with:
  python scripts/loop.py
"""
from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import sys
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
OUTPUT_LATEST = ROOT / "output" / "latest"

sys.path.insert(0, str(SRC))

_build_lock = threading.Lock()
_server_lock = threading.Lock()
_server_stop = threading.Event()


class ReusableTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


def _build_site(max_age_days: int, limit: int, no_enrich: bool, no_external: bool, refresh_llm: bool, verbose: bool) -> None:
    from bluetooth_news.cli import main as build_main

    build_args = [
        "--max-age-days",
        str(max_age_days),
        "--limit",
        str(limit),
    ]
    if no_enrich:
        build_args.append("--no-enrich")
    if no_external:
        build_args.append("--no-external")
    if refresh_llm:
        build_args.append("--refresh-llm")
    if verbose:
        build_args.append("--verbose")

    print("[loop] rebuilding latest site...")
    exit_code = build_main(build_args)
    if exit_code != 0:
        raise SystemExit(exit_code)

    index = OUTPUT_LATEST / "index.html"
    if not index.exists():
        raise FileNotFoundError(f"Expected generated site at {index}")


def _serve_once(host: str, port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUTPUT_LATEST))
    with ReusableTCPServer((host, port), handler) as httpd:
        httpd.daemon_threads = True
        httpd.timeout = 1.0
        print(f"[loop] serving {OUTPUT_LATEST} at http://{host}:{port}/index.html")
        while not _server_stop.is_set():
            httpd.handle_request()


def _server_worker(host: str, port: int) -> None:
    while not _server_stop.is_set():
        try:
            _serve_once(host, port)
        except OSError as exc:
            if _server_stop.is_set():
                break
            print(f"[loop] server error: {exc}; restarting in 5 seconds")
            time.sleep(5)
        except Exception as exc:
            if _server_stop.is_set():
                break
            print(f"[loop] unexpected server error: {exc}; restarting in 5 seconds")
            time.sleep(5)


def _next_4pm(now: datetime) -> datetime:
    target = now.replace(hour=16, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
    return target


def _daily_refresh_loop(args: argparse.Namespace) -> None:
    next_run = _next_4pm(datetime.now())
    while not _server_stop.is_set():
        seconds = max(1.0, (next_run - datetime.now()).total_seconds())
        if _server_stop.wait(timeout=seconds):
            break

        with _build_lock:
            if _server_stop.is_set():
                break
            try:
                print("[loop] 4 PM refresh starting...")
                _build_site(
                    max_age_days=args.max_age_days,
                    limit=args.limit,
                    no_enrich=args.no_enrich,
                    no_external=args.no_external,
                    refresh_llm=args.refresh_llm,
                    verbose=args.verbose,
                )
                print("[loop] 4 PM refresh complete")
            except Exception as exc:
                print(f"[loop] 4 PM refresh failed: {exc}")

        next_run += timedelta(days=1)


def _ai_server_worker(ai_host: str, ai_port: int) -> None:
    from bluetooth_news.ai_server import serve

    while not _server_stop.is_set():
        try:
            print(f"[loop] starting AIROC AI server on {ai_host}:{ai_port}...")
            serve(ai_host, ai_port, open_browser=False)
        except Exception as exc:
            if _server_stop.is_set():
                break
            print(f"[loop] AI server error: {exc}; restarting in 5 seconds")
            time.sleep(5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local report server AND AIROC AI server continuously with daily 4 PM refresh.")
    parser.add_argument("--host", default="127.0.0.1", help="Report server host")
    parser.add_argument("--port", type=int, default=8888, help="Report server port")
    parser.add_argument("--ai-host", default="127.0.0.1", help="AI server host")
    parser.add_argument("--ai-port", type=int, default=5005, help="AI server port")
    parser.add_argument("--page", default="index.html", help="Page to open in the browser")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--skip-ai", action="store_true", help="Skip starting the AI server")
    parser.add_argument("--build-at-start", action="store_true", 
                        help="Rebuild the site at startup (default: skip and serve cached site)")
    parser.add_argument("--max-age-days", type=int, default=7)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--no-enrich", action="store_true")
    parser.add_argument("--no-external", action="store_true")
    parser.add_argument("--refresh-llm", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    if args.build_at_start:
        try:
            with _build_lock:
                _build_site(
                    max_age_days=args.max_age_days,
                    limit=args.limit,
                    no_enrich=args.no_enrich,
                    no_external=args.no_external,
                    refresh_llm=args.refresh_llm,
                    verbose=args.verbose,
                )
        except Exception as exc:
            print(f"[loop] startup build failed: {exc}")
            return 1
    else:
        if not (OUTPUT_LATEST / "index.html").exists():
            print(f"[loop] ERROR: no cached site at {OUTPUT_LATEST}, cannot start without building")
            return 1
        print(f"[loop] serving cached site from {OUTPUT_LATEST}")

    server_thread = threading.Thread(target=_server_worker, args=(args.host, args.port), daemon=True)
    refresh_thread = threading.Thread(target=_daily_refresh_loop, args=(args,), daemon=True)
    server_thread.start()
    refresh_thread.start()

    ai_thread = None
    if not args.skip_ai:
        ai_thread = threading.Thread(target=_ai_server_worker, args=(args.ai_host, args.ai_port), daemon=True)
        ai_thread.start()

    if not args.no_browser:
        url = f"http://{args.host}:{args.port}/{args.page.lstrip('/')}"
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    print("[loop] running; press Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[loop] stopping...")
        _server_stop.set()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())