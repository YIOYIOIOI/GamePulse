"""Lightweight Steam review collector used by the product console.

This module intentionally depends only on requests + pandas so the dashboard can
collect real Steam data even when heavyweight NLP packages (torch/transformers)
are not installed.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd
import requests



def search_steam_apps(query: str, limit: int = 10, country: str = "US", language: str = "english") -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    """Search Steam Store apps by game name.

    Returns a list of candidate apps with stable fields:
    app_id, name, price, tiny_image, metacritic_score.
    """
    status: Dict[str, object] = {"ok": False, "query": query, "message": "", "rows": 0}
    query = (query or "").strip()
    if not query:
        status["message"] = "请输入游戏名称。"
        return [], status

    url = "https://store.steampowered.com/api/storesearch/"
    params = {
        "term": query,
        "l": language,
        "cc": country,
    }
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        status["message"] = f"Steam 搜索请求失败：{exc.__class__.__name__}"
        status["error_detail"] = str(exc)
        return [], status
    except ValueError as exc:
        status["message"] = "Steam 搜索返回内容无法解析。"
        status["error_detail"] = str(exc)
        return [], status

    items = payload.get("items", []) or []
    results: List[Dict[str, object]] = []
    for item in items[:limit]:
        app_id = item.get("id")
        name = item.get("name")
        if not app_id or not name:
            continue
        results.append({
            "app_id": int(app_id),
            "name": str(name),
            "price": item.get("price", {}).get("final_formatted") if isinstance(item.get("price"), dict) else item.get("price"),
            "tiny_image": item.get("tiny_image", ""),
            "metacritic_score": item.get("metacritic", {}).get("score") if isinstance(item.get("metacritic"), dict) else None,
        })

    status["ok"] = True
    status["rows"] = len(results)
    status["message"] = f"找到 {len(results)} 个候选游戏。" if results else "没有找到匹配游戏，请换一个关键词。"
    return results, status


def fetch_steam_reviews(
    app_id: int,
    game_name: str,
    max_reviews: int = 1000,
    language: str = "all",
    review_type: str = "all",
    delay_seconds: float = 0.6,
    timeout: int = 30,
) -> pd.DataFrame:
    reviews: List[Dict] = []
    cursor = "*"
    session = requests.Session()

    while len(reviews) < max_reviews:
        url = f"https://store.steampowered.com/appreviews/{app_id}"
        params = {
            "json": 1,
            "cursor": cursor,
            "language": language,
            "filter": "recent",
            "review_type": review_type,
            "purchase_type": "all",
            "num_per_page": min(100, max_reviews - len(reviews)),
        }
        last_error = None
        for attempt in range(3):
            try:
                response = session.get(url, params=params, timeout=timeout)
                response.raise_for_status()
                payload = response.json()
                break
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        else:
            raise last_error
        batch = payload.get("reviews", [])
        if not batch:
            break
        reviews.extend(batch)
        next_cursor = payload.get("cursor")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(delay_seconds)

    rows = []
    for r in reviews[:max_reviews]:
        author = r.get("author", {}) or {}
        rows.append({
            "game_name": game_name,
            "app_id": app_id,
            "review_id": r.get("recommendationid", ""),
            "author_steamid": author.get("steamid", ""),
            "review_text": r.get("review", ""),
            "vote_up": bool(r.get("voted_up", False)),
            "sentiment": "positive" if r.get("voted_up", False) else "negative",
            "votes_up": r.get("votes_up", 0),
            "votes_funny": r.get("votes_funny", 0),
            "weighted_vote_score": r.get("weighted_vote_score", 0),
            "playtime_forever": (author.get("playtime_forever", 0) or 0) / 60,
            "playtime_at_review": (author.get("playtime_at_review", 0) or 0) / 60,
            "timestamp_created": datetime.fromtimestamp(r.get("timestamp_created", 0) or 0),
            "timestamp_updated": datetime.fromtimestamp(r.get("timestamp_updated", 0) or 0),
            "language": r.get("language", ""),
            "num_games_owned": author.get("num_games_owned", 0),
            "num_reviews": author.get("num_reviews", 0),
            "steam_purchase": r.get("steam_purchase", True),
            "received_for_free": r.get("received_for_free", False),
            "written_during_early_access": r.get("written_during_early_access", False),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["review_length"] = df["review_text"].fillna("").astype(str).str.len()
        # Keep all non-empty real reviews. Data quality gates decide whether the
        # sample is sufficient for strategy conclusions; collection should not
        # silently discard too much evidence.
        df = df[df["review_length"] > 0].drop_duplicates(subset=["review_id", "review_text"])
        bins = [-1, 10, 100, 999999]
        labels = ["新手玩家", "普通玩家", "核心玩家"]
        df["player_type"] = pd.cut(df["playtime_forever"], bins=bins, labels=labels).astype(str)
    return df


def save_collected_reviews(df: pd.DataFrame, game_name: str, output_dir: str = "data/results") -> Path:
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in game_name).strip("_") or "steam_game"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = Path(output_dir) / f"{safe_name}_{timestamp}_steam_light.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False, encoding="utf-8-sig")
    return output



def safe_fetch_steam_reviews(
    app_id: int,
    game_name: str,
    max_reviews: int = 1000,
    language: str = "all",
    review_type: str = "all",
) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """Fetch Steam reviews and return a frontend-friendly status object.

    This wrapper prevents the product UI from crashing on transient network,
    SSL, region, or Steam throttling errors. The caller can show status["message"]
    and decide whether to retry.
    """
    status: Dict[str, object] = {
        "ok": False,
        "app_id": app_id,
        "game_name": game_name,
        "requested_reviews": max_reviews,
        "language": language,
        "review_type": review_type,
        "message": "",
        "rows": 0,
    }
    try:
        df = fetch_steam_reviews(
            app_id=app_id,
            game_name=game_name,
            max_reviews=max_reviews,
            language=language,
            review_type=review_type,
        )
    except requests.RequestException as exc:
        status["message"] = f"Steam 接口请求失败：{exc.__class__.__name__}"
        status["error_detail"] = str(exc)
        return pd.DataFrame(), status
    except Exception as exc:  # defensive wrapper for UI stability
        status["message"] = f"采集失败：{exc.__class__.__name__}"
        status["error_detail"] = str(exc)
        return pd.DataFrame(), status

    status["rows"] = int(len(df))
    if df.empty:
        status["message"] = "没有采集到有效评论。请检查 App ID、语言、评论类型或稍后重试。"
        return df, status

    status["ok"] = True
    status["message"] = f"已采集 {len(df):,} 条有效评论。"
    if "timestamp_created" in df.columns and len(df):
        status["date_min"] = str(pd.to_datetime(df["timestamp_created"], errors="coerce").min())
        status["date_max"] = str(pd.to_datetime(df["timestamp_created"], errors="coerce").max())
    if "sentiment" in df.columns:
        status["sentiment_counts"] = df["sentiment"].value_counts().to_dict()
    return df, status
