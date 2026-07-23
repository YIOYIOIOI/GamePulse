"""Lightweight Steam review collector used by the product console.

This module intentionally depends only on requests + pandas so the local API server can
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



def _normalize_steam_search_item(item: Dict[str, object]) -> Dict[str, object] | None:
    app_id = item.get("id")
    name = item.get("name")
    if not app_id or not name:
        return None
    price = item.get("price")
    metacritic = item.get("metacritic")
    return {
        "app_id": int(app_id),
        "name": str(name),
        "price": price.get("final_formatted") if isinstance(price, dict) else price,
        "tiny_image": item.get("tiny_image", ""),
        "metacritic_score": metacritic.get("score") if isinstance(metacritic, dict) else None,
    }


def _steam_store_search_once(query: str, limit: int, country: str, language: str) -> List[Dict[str, object]]:
    url = "https://store.steampowered.com/api/storesearch/"
    params = {"term": query, "l": language, "cc": country}
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    payload = response.json()
    results: List[Dict[str, object]] = []
    for item in (payload.get("items", []) or []):
        normalized = _normalize_steam_search_item(item)
        if normalized:
            results.append(normalized)
        if len(results) >= limit:
            break
    return results


def search_steam_apps(query: str, limit: int = 10, country: str = "US", language: str = "english") -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    """Search Steam Store apps by game name with multilingual fallback.

    Steam's store search is locale-sensitive. Chinese titles such as "永劫无间"
    may not be found when the request is forced to english/US even though the
    game exists under an English title (NARAKA: BLADEPOINT). This helper tries
    the requested locale first, then common Chinese/English fallback locales,
    plus a small alias map for high-signal Chinese titles.
    """
    status: Dict[str, object] = {"ok": False, "query": query, "message": "", "rows": 0}
    query = (query or "").strip()
    if not query:
        status["message"] = "请输入游戏名称。"
        return [], status

    # Keep first search fast and predictable: do not expand aliases.
    # Query only the two high-value channels requested by the user:
    # Mainland China Simplified Chinese + US English.
    queries = [query]
    locale_attempts = []
    for cc, lang in [("CN", "schinese"), ("US", "english")]:
        if (cc, lang) not in locale_attempts:
            locale_attempts.append((cc, lang))

    merged: List[Dict[str, object]] = []
    seen_app_ids = set()
    attempts = []
    last_error = None
    for q in queries:
        for cc, lang in locale_attempts:
            attempts.append({"query": q, "country": cc, "language": lang})
            try:
                batch = _steam_store_search_once(q, limit=limit, country=cc, language=lang)
            except requests.RequestException as exc:
                last_error = exc
                continue
            except ValueError as exc:
                last_error = exc
                continue
            for rank, item in enumerate(batch):
                app_id = item["app_id"]
                if app_id in seen_app_ids:
                    continue
                item["_search_rank"] = rank
                item["_matched_query"] = q
                item["_matched_locale"] = f"{cc}/{lang}"
                seen_app_ids.add(app_id)
                merged.append(item)

    query_lower = query.lower()
    def score(item: Dict[str, object]) -> tuple:
        name = str(item.get("name", "")).lower()
        exact = 0 if name == query_lower else 1
        contains = 0 if query_lower and query_lower in name else 1
        return (exact, contains, int(item.get("_search_rank", 999)), str(item.get("name", "")))

    merged = sorted(merged, key=score)[:limit]

    status["attempts"] = attempts
    status["ok"] = True
    status["rows"] = len(merged)
    if merged:
        status["message"] = f"找到 {len(merged)} 个候选游戏。"
    elif last_error:
        status["ok"] = False
        status["message"] = f"Steam 搜索请求失败：{last_error.__class__.__name__}"
        status["error_detail"] = str(last_error)
    else:
        status["message"] = "没有找到匹配游戏，请换一个关键词。"
    return merged, status


def fetch_steam_reviews(
    app_id: int,
    game_name: str,
    max_reviews: int = 1000,
    language: str = "all",
    review_type: str = "all",
    delay_seconds: float = 0.6,
    timeout: int = 30,
    progress_callback=None,
    recent_days: int | None = None,
    safety_max_reviews: int = 50000,
) -> pd.DataFrame:
    reviews: List[Dict] = []
    cursor = "*"
    session = requests.Session()
    cutoff_ts = None
    if recent_days and recent_days > 0:
        cutoff_ts = int(time.time() - recent_days * 86400)
    target_limit = safety_max_reviews if cutoff_ts else max_reviews

    while len(reviews) < target_limit:
        url = f"https://store.steampowered.com/appreviews/{app_id}"
        params = {
            "json": 1,
            "cursor": cursor,
            "language": language,
            "filter": "recent",
            "review_type": review_type,
            "purchase_type": "all",
            "num_per_page": min(100, target_limit - len(reviews)),
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
        stop_for_window = False
        kept_batch = []
        for item in batch:
            created = int(item.get("timestamp_created", 0) or 0)
            if cutoff_ts and created and created < cutoff_ts:
                stop_for_window = True
                continue
            kept_batch.append(item)
        reviews.extend(kept_batch)
        if progress_callback:
            oldest_ts = min((int(r.get("timestamp_created", 0) or 0) for r in reviews), default=None)
            newest_ts = max((int(r.get("timestamp_created", 0) or 0) for r in reviews), default=None)
            progress_callback({
                "collected": len(reviews),
                "target": max_reviews,
                "batch_size": len(kept_batch),
                "recent_days": recent_days,
                "window_complete": stop_for_window,
                "oldest_ts": oldest_ts,
                "newest_ts": newest_ts,
            })
        if stop_for_window:
            break
        next_cursor = payload.get("cursor")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(delay_seconds)

    rows = []
    for r in reviews[:target_limit]:
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
    recent_days: int | None = None,
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
        "recent_days": recent_days,
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
            recent_days=recent_days,
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
    if recent_days and recent_days > 0:
        status["message"] = f"已采集最近 {recent_days} 天内 {len(df):,} 条有效评论。"
    else:
        status["message"] = f"已采集 {len(df):,} 条有效评论。"
    if "timestamp_created" in df.columns and len(df):
        status["date_min"] = str(pd.to_datetime(df["timestamp_created"], errors="coerce").min())
        status["date_max"] = str(pd.to_datetime(df["timestamp_created"], errors="coerce").max())
    if "sentiment" in df.columns:
        status["sentiment_counts"] = df["sentiment"].value_counts().to_dict()
    return df, status
