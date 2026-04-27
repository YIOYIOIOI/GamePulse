"""Lightweight Steam review collector used by the product console.

This module intentionally depends only on requests + pandas so the dashboard can
collect real Steam data even when heavyweight NLP packages (torch/transformers)
are not installed.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import pandas as pd
import requests


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
