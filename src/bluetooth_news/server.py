"""Flask server for interactive site with refresh capability."""
from __future__ import annotations

import json
import logging
import threading
import os
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory

# Lock for thread-safe refresh operations
_refresh_lock = threading.Lock()
_last_refresh = None
_refresh_in_progress = False

logger = logging.getLogger(__name__)


def _lookback_days() -> int:
    """Read processing horizon from env with safe fallback."""
    try:
        return max(7, int(os.getenv("NEWS_LOOKBACK_DAYS", "60")))
    except ValueError:
        return 60


def _load_cached_non_news_inputs(root: Path) -> tuple[list, list, list]:
    """Load cached pulse/patents/filings so news refresh can stay lightweight."""
    briefing_path = root / "data" / "briefing_input.json"
    if not briefing_path.exists():
        return [], [], []

    try:
        payload = json.loads(briefing_path.read_text(encoding="utf-8"))
    except Exception:
        return [], [], []

    pulse = payload.get("github_pulse", []) or []
    patents = payload.get("patents", []) or []
    filings = payload.get("edgar_filings", []) or []
    return pulse, patents, filings


def create_app(docs_dir: Path | str = "docs") -> Flask:
    """Create and configure Flask app."""
    app = Flask(__name__)
    docs_path = Path(docs_dir)

    @app.route("/api/news", methods=["GET"])
    def api_news():
        """Return the current cached top news articles for dynamic page loads."""
        cache_path = docs_path.parent / "data" / "news_cache.json"
        if not cache_path.exists():
            return jsonify([]), 200

        try:
            items = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to read news cache: {e}")
            return jsonify([]), 200

        bucket = (request.args.get("bucket") or "").strip()
        if bucket:
            items = [it for it in items if bucket in (it.get("buckets") or [])]

        try:
            limit = int(request.args.get("limit", 2000))
        except ValueError:
            limit = 2000
        limit = max(1, min(limit, 5000))

        return jsonify(items[:limit]), 200

    @app.route("/")
    def index():
        """Serve index.html."""
        return send_from_directory(docs_path, "index.html")

    @app.route("/<path:filename>")
    def serve_file(filename):
        """Serve static files."""
        return send_from_directory(docs_path, filename)

    @app.route("/api/refresh", methods=["POST"])
    def api_refresh():
        """Refresh all news and documents on demand."""
        global _refresh_in_progress, _last_refresh

        with _refresh_lock:
            if _refresh_in_progress:
                return jsonify({
                    "ok": False,
                    "message": "Refresh already in progress",
                    "last_refresh": _last_refresh.isoformat() if _last_refresh else None
                }), 202

            _refresh_in_progress = True

        try:
            # Import here to avoid circular imports
            from .cli import main as cli_main
            from .fetcher import fetch_all
            from .aggregator import process
            from .enrichment import enrich
            from .cache import record_history
            from .github_pulse import fetch_pulse
            from .external_data import fetch_patents, fetch_edgar
            from .briefing import write_inputs, synthesize_outputs
            from .auto_update import auto_update_from_articles
            from .report import render

            logger.info("Starting refresh...")

            # Fetch raw articles
            raw = fetch_all()
            logger.info(f"Fetched {len(raw)} raw articles")

            # Deduplicate and process
            lookback_days = _lookback_days()
            articles = process(raw, max_age_days=lookback_days, limit=1500, verbose=False)
            logger.info(f"After dedup/filter: {len(articles)} articles")

            # Enrich
            articles = enrich(articles)
            logger.info(f"After enrichment: {len(articles)} articles")

            # Record history
            today = datetime.now().strftime("%Y-%m-%d")
            record_history(today, articles)

            # Auto-update catalogs
            try:
                au = auto_update_from_articles(articles, force=False)
                logger.info(f"Auto-update: {au}")
            except Exception as e:
                logger.warning(f"Auto-update failed: {e}")

            # Fetch external data
            pulse, patents, filings = [], [], []
            try:
                pulse = fetch_pulse()
                logger.info(f"Fetched {len(pulse)} GitHub pulse items")
            except Exception as e:
                logger.warning(f"GitHub pulse failed: {e}")

            try:
                patents = fetch_patents()
                logger.info(f"Fetched {len(patents)} patents")
            except Exception as e:
                logger.warning(f"Patents failed: {e}")

            try:
                filings = fetch_edgar()
                logger.info(f"Fetched {len(filings)} EDGAR filings")
            except Exception as e:
                logger.warning(f"EDGAR failed: {e}")

            # Write inputs and synthesize
            try:
                write_inputs(articles, pulse, patents, filings)
                synth = synthesize_outputs(force=False)
                logger.info(f"LLM synthesis: {synth}")
            except Exception as e:
                logger.warning(f"Briefing synthesis failed: {e}")

            # Render HTML
            index_path = render(articles, docs_path, pulse=pulse, patents=patents, filings=filings)
            logger.info(f"Site rendered: {index_path}")

            _last_refresh = datetime.now()
            return jsonify({
                "ok": True,
                "message": "Refresh completed successfully",
                "articles_count": len(articles),
                "lookback_days": lookback_days,
                "timestamp": _last_refresh.isoformat()
            }), 200

        except Exception as e:
            logger.exception(f"Refresh failed: {e}")
            return jsonify({
                "ok": False,
                "message": str(e),
                "last_refresh": _last_refresh.isoformat() if _last_refresh else None
            }), 500

        finally:
            with _refresh_lock:
                _refresh_in_progress = False

    @app.route("/api/status", methods=["GET"])
    def api_status():
        """Get refresh status."""
        return jsonify({
            "in_progress": _refresh_in_progress,
            "last_refresh": _last_refresh.isoformat() if _last_refresh else None
        }), 200

    @app.route("/api/refresh-news", methods=["POST"])
    def api_refresh_news():
        """Refresh only news dynamically; reuse cached non-news datasets."""
        global _refresh_in_progress, _last_refresh

        with _refresh_lock:
            if _refresh_in_progress:
                return jsonify({
                    "ok": False,
                    "message": "Refresh already in progress",
                    "last_refresh": _last_refresh.isoformat() if _last_refresh else None
                }), 202

            _refresh_in_progress = True

        try:
            from .fetcher import fetch_all
            from .aggregator import process
            from .enrichment import enrich
            from .cache import record_history
            from .briefing import write_inputs
            from .report import render

            logger.info("Starting news-only refresh...")

            raw = fetch_all()
            logger.info(f"Fetched {len(raw)} raw articles")

            lookback_days = _lookback_days()
            articles = process(raw, max_age_days=lookback_days, limit=1500, verbose=False)
            logger.info(f"After dedup/filter: {len(articles)} articles")

            articles = enrich(articles)
            logger.info(f"After enrichment: {len(articles)} articles")

            today = datetime.now().strftime("%Y-%m-%d")
            record_history(today, articles)

            pulse, patents, filings = _load_cached_non_news_inputs(docs_path.parent)
            write_inputs(articles, pulse, patents, filings)

            index_path = render(articles, docs_path, pulse=pulse, patents=patents, filings=filings)
            logger.info(f"Site rendered after news refresh: {index_path}")

            _last_refresh = datetime.now()
            return jsonify({
                "ok": True,
                "message": "News refreshed successfully",
                "articles_count": len(articles),
                "lookback_days": lookback_days,
                "timestamp": _last_refresh.isoformat()
            }), 200
        except Exception as e:
            logger.exception(f"News refresh failed: {e}")
            return jsonify({
                "ok": False,
                "message": str(e),
                "last_refresh": _last_refresh.isoformat() if _last_refresh else None
            }), 500
        finally:
            with _refresh_lock:
                _refresh_in_progress = False

    return app


def run_server(host: str = "127.0.0.1", port: int = 5005, docs_dir: str = "docs", debug: bool = False):
    """Run the Flask development server."""
    app = create_app(docs_dir)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logger.info(f"Starting server at http://{host}:{port} serving {docs_dir}/")
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run interactive news server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5005)
    parser.add_argument("--docs-dir", default="docs")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    run_server(host=args.host, port=args.port, docs_dir=args.docs_dir, debug=args.debug)
