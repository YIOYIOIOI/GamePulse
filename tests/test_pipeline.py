"""统一管线（src/analysis/pipeline.py）的离线测试。

覆盖两条路径：
- run_full(with_models=True)：规则情绪 fallback + 语言过滤主题建模 + 评测 + 分层 + 质量包
- run_full(with_models=False)：API 轻量路径（跳过重模型）

不依赖 torch/transformers/网络：sentiment 用 use_transformer=False 的规则路径。
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analysis.pipeline import PipelineResult, run_full  # noqa: E402

EN_POS = ["good match today", "great game and fun team", "love the new update design",
          "best coop experience with friends", "nice balance patch this season"]
EN_NEG = ["bad matchmaking again", "terrible lag and toxic team", "worst update ever broke ranked",
          "awful servers keep crashing", "hate the new item system"]
RU_TEXT = ["очень плохая игра", "не работает сервер", "игра вылетает постоянно", "плохой матчмейкинг"]


def _make_df(n_en: int = 200, n_ru: int = 40) -> pd.DataFrame:
    rng = random.Random(42)
    rows = []
    for i in range(n_en):
        positive = i % 2 == 0
        text = rng.choice(EN_POS if positive else EN_NEG) + f" case {i}"
        rows.append({
            "review_text": text,
            "review_text_clean": text,
            "language": "english",
            "vote_up": positive,
            "voted_up": positive,
            "playtime_forever": rng.randint(10, 12000),
            "votes_up": rng.randint(0, 50),
            "timestamp_created": f"2026-06-{(i % 28) + 1:02d}",
        })
    for i in range(n_ru):
        text = rng.choice(RU_TEXT) + f" {i}"
        rows.append({
            "review_text": text,
            "review_text_clean": text,
            "language": "russian",
            "vote_up": False,
            "voted_up": False,
            "playtime_forever": rng.randint(10, 5000),
            "votes_up": rng.randint(0, 5),
            "timestamp_created": f"2026-06-{(i % 28) + 1:02d}",
        })
    return pd.DataFrame(rows)


CONFIG = {
    "sentiment_analysis": {"use_transformer": False},
    "topic_analysis": {
        "method": "lda",
        "num_topics": 2,
        "max_features": 200,
        "ngram_range": [1, 1],
        "min_df": 1,
        "max_df": 1.0,
        "language_filter": "auto",
        "min_docs_for_language_filter": 50,
    },
}


def test_run_full_with_models_end_to_end():
    df = _make_df()
    result = run_full(df, CONFIG)

    assert isinstance(result, PipelineResult)
    out = result.df

    # 语言归一
    assert "lang_code" in out.columns
    assert set(out["lang_code"].unique()) == {"en", "ru"}

    # 情绪（规则 fallback）
    assert "sentiment" in out.columns
    assert result.sentiment_stats is not None

    # 弱标签评测
    assert result.sentiment_evaluation is not None
    assert "overall" in result.sentiment_evaluation

    # 主题：en 子集(200) >= min_docs(50) → 只在英文子集建模
    assert result.topic_metrics is not None
    assert result.topic_metrics["modeled_language"] == "en"
    assert result.topic_metrics["n_docs_modeled"] == 200
    assert result.topics and len(result.topics) == 2
    assert result.topic_metrics["npmi"]["mean_npmi"] is not None
    # 俄语行不应有主题分配
    ru_topics = out.loc[out["lang_code"] == "ru", "topic_id"]
    assert ru_topics.isna().all()

    # 分层（240 行 ≥ min_samples=100 → KMeans 主路径）
    assert result.segmentation_meta is not None
    assert "segment_label" in out.columns

    # 质量包
    assert result.quality_package is not None
    assert "gates" in result.quality_package


def test_run_full_light_path_for_api():
    df = _make_df(n_en=60, n_ru=0)
    result = run_full(df, config={}, with_models=False)

    # 不跑模型：无情绪统计、无主题
    assert result.sentiment_stats is None
    assert result.topics is None
    # 但轻量步骤照常
    assert "lang_code" in result.df.columns
    assert result.quality_package is not None


def test_run_full_without_language_column_warns_not_crashes():
    df = _make_df(n_en=60, n_ru=0).drop(columns=["language"])
    result = run_full(df, CONFIG)
    assert result.topic_metrics is not None
    assert result.topic_metrics["modeled_language"] == "all"
    assert result.quality_package is not None


def test_playtime_hours_contract_fallback_cut():
    """回归：playtime_forever 已是小时，分层 fallback 不得再除 60。

    历史 bug：双重换算导致 8h/120h/600h 全被判成轻度玩家（评审冒烟用例）。
    """
    from src.analysis.segmentation.player_segmentation import segment_players

    df = pd.DataFrame({
        "playtime_forever": [8, 120, 600],
        "votes_up": [1, 5, 30],
        "review_text": ["a" * 50, "b" * 200, "c" * 400],
    })
    out, meta = segment_players(df)
    labels = out["segment_label"].tolist()
    assert meta["method"] == "playtime_cut_fallback"
    assert labels[0] == "轻度玩家"       # 8h < 10h
    assert labels[1] == "核心玩家"       # 120h > 100h（bug 时被判轻度）
    assert labels[2] == "核心玩家"       # 600h > 100h


def test_playtime_hours_contract_cluster_profiles():
    """回归：KMeans 簇画像的 avg_playtime_hours 不得再除 60。"""
    from src.analysis.segmentation.player_segmentation import segment_players

    rng = random.Random(7)
    df = pd.DataFrame({
        "playtime_forever": [rng.randint(100, 200) for _ in range(120)],
        "votes_up": [rng.randint(0, 10) for _ in range(120)],
        "review_text": ["x" * rng.randint(30, 300) for _ in range(120)],
    })
    _, meta = segment_players(df)
    avgs = [p["avg_playtime_hours"] for p in meta["cluster_profiles"].values()]
    # 输入全部在 100-200h，画像均值必须落在该区间（÷60 的话会 < 4）
    assert all(90 <= v <= 210 for v in avgs), avgs


def test_product_metrics_playtime_no_minute_misdetect():
    """回归：重度游戏（小时口径 q80>500）不得被误判成分钟再除 60。"""
    from src.analysis.product_metrics import playtime_hours_series

    hours = pd.Series([300, 800, 1500, 4000, 6000])
    df = pd.DataFrame({"playtime_forever": hours})
    out = playtime_hours_series(df)
    assert out.tolist() == hours.tolist()
