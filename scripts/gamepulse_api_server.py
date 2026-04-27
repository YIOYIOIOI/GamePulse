"""Lightweight local API for the React GamePulse frontend.

Run:
    python scripts/gamepulse_api_server.py --port 8765

This server is local-only by default. It never stores model API keys; LLM calls
are made directly from the browser when the user enables local model settings.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analysis.product_metrics import build_analysis_package  # noqa: E402
from src.data_collection.steam_light_collector import (  # noqa: E402
    _steam_store_search_once,
    fetch_steam_reviews,
    safe_fetch_steam_reviews,
    search_steam_apps,
)


def _json_default(obj):
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
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


def _search_attempts(query: str):
    alias_queries = {
        "永劫无间": ["永劫无间", "NARAKA", "NARAKA BLADEPOINT", "bladepoint"],
        "永劫": ["永劫无间", "NARAKA", "NARAKA BLADEPOINT", "bladepoint"],
    }
    queries = alias_queries.get((query or "").strip(), [(query or "").strip()])
    locales = [("US", "english"), ("CN", "schinese")]
    seen = set()
    attempts = []
    for q in queries:
        for country, language in locales:
            key = (q, country, language)
            if key in seen:
                continue
            seen.add(key)
            attempts.append(key)
    return attempts


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

    def _begin_ndjson(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _event(self, payload):
        self.wfile.write((json.dumps(payload, ensure_ascii=False, default=_json_default) + "\n").encode("utf-8"))
        self.wfile.flush()

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

        if parsed.path == "/api/steam/search/stream":
            self._stream_search(payload)
            return

        if parsed.path == "/api/steam/reviews/stream":
            self._stream_reviews(payload)
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

    def _stream_search(self, payload):
        query = str(payload.get("q") or payload.get("query") or "").strip()
        limit = int(payload.get("limit") or 12)
        self._begin_ndjson()
        if not query:
            self._event({"done": True, "ok": False, "percent": 100, "message": "请输入游戏名称。", "error": "请输入游戏名称。"})
            return
        attempts = _search_attempts(query)
        merged = []
        seen_app_ids = set()
        total = max(1, len(attempts))
        self._event({"stage": "start", "percent": 5, "message": "开始搜索 Steam 商店。"})
        for idx, (q, country, language) in enumerate(attempts, start=1):
            percent = 5 + int((idx - 1) / total * 75)
            self._event({"stage": "attempt", "percent": percent, "message": f"正在查询 {country}/{language}：{q}"})
            try:
                batch = _steam_store_search_once(q, limit=limit, country=country, language=language)
            except Exception as exc:
                self._event({"stage": "attempt-error", "percent": percent, "message": f"该路径失败，继续尝试：{exc.__class__.__name__}"})
                continue
            for item in batch:
                app_id = item["app_id"]
                if app_id in seen_app_ids:
                    continue
                seen_app_ids.add(app_id)
                merged.append(item)
                self._event({"stage": "result", "percent": min(90, percent + 8), "rows": len(merged), "message": f"已找到 {len(merged)} 个候选游戏。"})
                if len(merged) >= limit:
                    break
            if len(merged) >= limit:
                break
        self._event({"done": True, "ok": True, "percent": 100, "rows": len(merged), "results": merged, "message": f"搜索完成：{len(merged)} 个候选游戏。"})

    def _stream_reviews(self, payload):
        self._begin_ndjson()
        app_id = int(payload.get("appId") or payload.get("app_id") or 0)
        game_name = str(payload.get("gameName") or payload.get("game_name") or "Steam Game")
        count = int(payload.get("count") or payload.get("max_reviews") or 1000)
        language = str(payload.get("language") or "all")
        review_type = str(payload.get("reviewType") or payload.get("review_type") or "all")
        if app_id <= 0:
            self._event({"done": True, "ok": False, "percent": 100, "message": "App ID 无效。", "error": "App ID 无效。"})
            return
        try:
            self._event({"stage": "connect", "percent": 3, "message": "正在连接 Steam 评论接口。"})
            df = fetch_steam_reviews(
                app_id=app_id,
                game_name=game_name,
                max_reviews=count,
                language=language,
                review_type=review_type,
                progress_callback=lambda info: self._event({
                    "stage": "collect",
                    "percent": min(88, 5 + int((info.get("collected", 0) / max(1, count)) * 80)),
                    "rows": info.get("collected", 0),
                    "message": f"已采集 {info.get('collected', 0)} / {count} 条评论。",
                }),
            )
            self._event({"stage": "normalize", "percent": 92, "rows": int(len(df)), "message": "正在标准化字段并去重。"})
            time.sleep(0.05)
            status = {"ok": not df.empty, "rows": int(len(df)), "message": f"已采集 {len(df):,} 条有效评论。" if not df.empty else "没有采集到有效评论。"}
            self._event({"done": True, "ok": not df.empty, "percent": 100, "rows": int(len(df)), "status": status, "reviews": df.to_dict("records"), "message": status["message"]})
        except requests.RequestException as exc:
            self._event({"done": True, "ok": False, "percent": 100, "message": f"Steam 接口请求失败：{exc.__class__.__name__}", "error": str(exc)})
        except Exception as exc:
            self._event({"done": True, "ok": False, "percent": 100, "message": f"采集失败：{exc.__class__.__name__}", "error": str(exc)})


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
