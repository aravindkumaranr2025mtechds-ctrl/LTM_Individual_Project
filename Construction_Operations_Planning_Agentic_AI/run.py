#!/usr/bin/env python3
"""Offline launcher. Requires Python 3.10+ and no third-party packages."""
import argparse
import sys
import threading
import webbrowser


def main():
    if sys.version_info < (3, 10):
        print("BuildPlan requires Python 3.10 or newer. Python 3.11 is recommended.")
        return 1
    parser = argparse.ArgumentParser(description="Start the BuildPlan local dashboard.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    from app.server import make_server
    from app.service import ROOT
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        print("Bundled dashboard is missing. Extract the complete ZIP before launching.")
        return 1
    try:
        server = make_server(args.port)
    except OSError as exc:
        print(f"Unable to start: {exc}\nTry: python run.py --port 8766")
        return 1
    url = f"http://127.0.0.1:{args.port}"
    print(f"\nBuildPlan | Construction Operations Planning\nOpen {url}\nKeep this window open. Press Ctrl+C to stop.\n", flush=True)
    if not args.no_browser:
        timer = threading.Timer(0.7, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBuildPlan stopped. Saved projects remain in data/buildplan.sqlite3.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
