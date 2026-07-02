"""Convenience launcher.

Usage:
  python run.py             # build the IoT Wireless Intel site
  python run.py ai          # start the AIROC AI chat server (http://localhost:5005)
  python run.py ai --reindex
  python run.py ai-index    # rebuild the AI doc index then exit
  python run.py ai-enrich   # pull fresh web snippets into the index
  python run.py ai-nightly  # local reindex + web enrichment (scheduled task)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

def _ai(argv):
    from bluetooth_news.ai_server import serve
    from bluetooth_news import ai_assistant as A
    import argparse
    p = argparse.ArgumentParser(prog="run.py ai")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5005)
    p.add_argument("--no-open", action="store_true")
    p.add_argument("--reindex", action="store_true")
    a = p.parse_args(argv)
    if a.reindex:
        A.build_index(verbose=True)
    serve(a.host, a.port, open_browser=not a.no_open)

def _ai_index(_argv):
    from bluetooth_news import ai_assistant as A
    A.build_index(verbose=True)

def _ai_enrich(argv):
    from bluetooth_news import ai_assistant as A
    import argparse
    p = argparse.ArgumentParser(prog="run.py ai-enrich")
    p.add_argument("--per-query", type=int, default=3,
                   help="Web results to pull per seed query")
    a = p.parse_args(argv)
    res = A.enrich_from_web(per_query=a.per_query, verbose=True)
    print(f"[ai-enrich] DONE - queries={res['queries']} fetched={res['chunks_fetched']} "
          f"added={res['chunks_added']} failures={res['failures']}")

def _ai_nightly(_argv):
    from bluetooth_news import ai_assistant as A
    print("[nightly] step 1/2 - rebuilding local document index...")
    res1 = A.build_index(verbose=True)
    print(f"[nightly] local index: {res1['count']} chunks")
    print("[nightly] step 2/2 - enriching from the web...")
    res2 = A.enrich_from_web(per_query=3, verbose=True)
    print(f"[nightly] DONE - local={res1['count']} added_from_web={res2['chunks_added']} "
          f"web_failures={res2['failures']}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "ai":
        _ai(sys.argv[2:])
    elif len(sys.argv) > 1 and sys.argv[1] == "ai-index":
        _ai_index(sys.argv[2:])
        sys.exit(0)
    elif len(sys.argv) > 1 and sys.argv[1] == "ai-enrich":
        _ai_enrich(sys.argv[2:])
        sys.exit(0)
    elif len(sys.argv) > 1 and sys.argv[1] == "ai-nightly":
        _ai_nightly(sys.argv[2:])
        sys.exit(0)
    else:
        from bluetooth_news.cli import main
        sys.exit(main())

