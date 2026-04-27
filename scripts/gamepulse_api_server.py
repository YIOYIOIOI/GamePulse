"""Lightweight local API for the React GamePulse frontend.

Run:
    python scripts/gamepulse_api_server.py --port 8765

Endpoints:
    GET  /api/health
    GET  /api/steam/search?q=dota%202
    POST /api/steam/reviews
    POST /api/analyze
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analysis.product_metrics import build_analysis_package  # noqa: E402
from src.data_collection.steam_light_collector import (  # noqa: E402
    safe_fetch_steam_reviews,
    search_steam_apps,
)


def _json_default(obj):
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    try:
        import numpy as np

        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
    except Exception:
        pass
    return str(obj)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quieter console
        print("[gamepulse-api] " + fmt % args)

    def _send(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, default=_json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send({"ok": True})

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send({"ok": True, "service": "gamepulse-api"})
            return
        if parsed.path == "/api/steam/search":
            qs = parse_qs(parsed.query)
            query = qs.get("q", [""])[0]
            limit = int(qs.get("limit", ["10"])[0])
            results, status = search_steam_apps(query, limit=limit)
            self._send({"status": status, "results": results}, status=200 if status.get("ok") else 502)
            return
        self._send({"ok": False, "message": "Not found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
        except Exception as exc:
            self._send({"ok": False, "message": f"Invalid JSON: {exc}"}, status=400)
            return

        if parsed.path == "/api/steam/reviews":
            df, status = safe_fetch_steam_reviews(
                app_id=int(payload.get("appId") or payload.get("app_id") or 0),
                game_name=str(payload.get("gameName") or payload.get("game_name") or "Steam Game"),
                max_reviews=int(payload.get("count") or payload.get("max_reviews") or 1000),
                language=str(payload.get("language") or "all"),
                review_type=str(payload.get("reviewType") or payload.get("review_type") or "all"),
            )
            self._send({"status": status, "reviews": df.to_dict("records")}, status=200 if status.get("ok") else 502)
            return

        if parsed.path == "/api/analyze":
            rows = payload.get("reviews") or payload.get("data") or []
            df = pd.DataFrame(rows)
            package = build_analysis_package(df)
            self._send({"ok": True, "package": package})
            return

        self._send({"ok": False, "message": "Not found"}, status=404)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"GamePulse API listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
