"""升级模块的离线测试：语言归一 / 弱标签评测 / KMeans 分层 / 主题指标 / LLM 链路。

全部离线可跑（不访问网络、不依赖 torch），是 CI 的主门槛。
"""

import numpy as np
import pandas as pd
import pytest

from src.analysis.evaluation import evaluate_sentiment_against_votes
from src.analysis.language import add_language_columns, filter_language, normalize_steam_language
from src.analysis.segmentation.player_segmentation import segment_players
from src.analysis.topic.coherence import npmi_coherence, topic_diversity


# ---------- 语言归一 ----------

def test_normalize_steam_language_buckets():
    assert normalize_steam_language("english") == "en"
    assert normalize_steam_language("latam") == "es"      # 拉美西语并入 es
    assert normalize_steam_language("brazilian") == "pt"
    assert normalize_steam_language("schinese") == "zh"
    assert normalize_steam_language("tchinese") == "zh"
    assert normalize_steam_language("klingon") == "other"  # 未知标签 fail-safe
    assert normalize_steam_language(None) == "other"
    assert normalize_steam_language("") == "other"


def test_add_language_columns_and_filter():
    df = pd.DataFrame({"language": ["english", "russian", "english"], "x": [1, 2, 3]})
    out = add_language_columns(df)
    assert list(out["lang_code"]) == ["en", "ru", "en"]
    assert len(filter_language(out, "en")) == 2
    # 缺 language 列不炸，全部 other
    no_col = add_language_columns(pd.DataFrame({"x": [1]}))
    assert list(no_col["lang_code"]) == ["other"]


# ---------- 弱标签评测 ----------

def test_evaluation_metrics_known_confusion():
    # 构造已知混淆矩阵: TP=2 FP=1 FN=1 TN=2 -> agreement 4/6
    df = pd.DataFrame(
        {
            "sentiment": ["positive", "positive", "positive", "negative", "negative", "negative"],
            "vote_up": [True, True, False, True, False, False],
            "language": ["english"] * 6,
        }
    )
    result = evaluate_sentiment_against_votes(df, min_group_size=1)
    m = result["overall"]
    assert m["confusion"] == {"tp": 2, "fp": 1, "fn": 1, "tn": 2}
    assert m["agreement"] == pytest.approx(4 / 6, abs=1e-4)
    assert m["precision_pos"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["recall_pos"] == pytest.approx(2 / 3, abs=1e-4)
    # 口径说明必须随结果携带（防止数字被断章取义）
    assert result["caveats"]


def test_evaluation_requires_columns():
    with pytest.raises(ValueError):
        evaluate_sentiment_against_votes(pd.DataFrame({"sentiment": ["positive"]}))


def test_evaluation_per_language_split():
    rng = np.random.default_rng(42)
    n = 200
    df = pd.DataFrame(
        {
            "sentiment": rng.choice(["positive", "negative"], n),
            "vote_up": rng.choice([True, False], n),
            "language": ["english"] * 100 + ["russian"] * 100,
        }
    )
    result = evaluate_sentiment_against_votes(df, min_group_size=50)
    assert set(result["by_language"]) == {"en", "ru"}
    assert "non_english_overall" in result


# ---------- KMeans 分层 ----------

def _synthetic_players(n=300, seed=42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # 三个天然簇：轻度 / 普通 / 高影响力长评者
    light = pd.DataFrame(
        {
            "playtime_forever": rng.uniform(10, 500, n // 3),
            "votes_up": rng.poisson(0.2, n // 3),
            "review_length": rng.uniform(20, 150, n // 3),
            "num_reviews": rng.poisson(1, n // 3),
        }
    )
    mid = pd.DataFrame(
        {
            "playtime_forever": rng.uniform(2000, 6000, n // 3),
            "votes_up": rng.poisson(0.3, n // 3),
            "review_length": rng.uniform(50, 250, n // 3),
            "num_reviews": rng.poisson(2, n // 3),
        }
    )
    heavy = pd.DataFrame(
        {
            "playtime_forever": rng.uniform(4000, 9000, n - 2 * (n // 3)),
            "votes_up": rng.poisson(30, n - 2 * (n // 3)),
            "review_length": rng.uniform(300, 900, n - 2 * (n // 3)),
            "num_reviews": rng.poisson(8, n - 2 * (n // 3)),
        }
    )
    return pd.concat([light, mid, heavy], ignore_index=True)


def test_segment_players_kmeans_path():
    df = _synthetic_players()
    out, meta = segment_players(df)
    assert meta["method"] == "kmeans_multifeature"
    assert 2 <= meta["k"] <= 6
    assert meta["silhouette"] > 0
    assert set(out["segment_label"].unique()) == set(meta["cluster_profiles"].keys())
    # 可复现：同输入同参数必须同结果
    out2, meta2 = segment_players(df)
    assert meta2["k"] == meta["k"]
    assert (out2["segment_cluster"] == out["segment_cluster"]).all()


def test_segment_players_fallback_small_sample():
    df = _synthetic_players(n=30)
    out, meta = segment_players(df, min_samples=100)
    assert meta["method"] == "playtime_cut_fallback"
    assert "reason" in meta
    assert set(out["segment_label"].unique()) <= {"轻度玩家", "普通玩家", "核心玩家"}


def test_segment_players_derives_review_length_from_text():
    df = _synthetic_players().drop(columns=["review_length"])
    df["review_text"] = "some review text"
    _, meta = segment_players(df)
    assert "review_length" in meta["features"]


# ---------- 主题指标 ----------

def test_npmi_rewards_cooccurring_topic_words():
    # 词对总是共现的语料 vs 从不共现的主题词
    texts = ["apple banana", "apple banana", "apple banana", "cat dog", "cat dog", "bird fish"]
    good = {0: ["apple", "banana"]}
    bad = {0: ["apple", "fish"]}  # 从不共现
    good_score = npmi_coherence(good, texts)["mean_npmi"]
    bad_score = npmi_coherence(bad, texts)["mean_npmi"]
    assert good_score > bad_score
    assert bad_score == -1.0


def test_topic_diversity():
    assert topic_diversity({0: ["a", "b"], 1: ["c", "d"]}) == 1.0
    assert topic_diversity({0: ["a", "b"], 1: ["a", "b"]}) == 0.5


# ---------- LLM 链路（离线 mock） ----------

def test_strategy_generator_with_mock_client():
    from src.ai_modules.llm_client import MockLLMClient
    from src.ai_modules.strategy.strategy_generator import StrategyGenerator

    mock = MockLLMClient("[MOCK] ok")
    gen = StrategyGenerator({}, client=mock)
    out = gen.generate_strategies({"sentiment_stats": {"positive": 10, "negative": 20}})
    assert out == "[MOCK] ok"
    assert mock.calls and mock.calls[0]["system"]  # system prompt 已注入


def test_llm_from_env_degrades_without_key(monkeypatch):
    from src.ai_modules import llm_client

    for key in ("GAMEPULSE_LLM_API_KEY", "OPENAI_API_KEY", "ARK_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    assert llm_client.from_env({}) is None
