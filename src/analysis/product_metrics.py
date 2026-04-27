"""Product-grade analytics helpers for the AI strategy operations console.

The functions in this module intentionally separate *real business metrics* from
*public-data proxy metrics*. Steam review data can support sentiment/topic/risk
signals, but it cannot honestly support true LTV, payment conversion or retention
without internal telemetry and payment logs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd


@dataclass
class DataQualityResult:
    sample_size: int
    date_span_days: int | None
    games_count: int
    has_sentiment: bool
    has_topics: bool
    has_player_type: bool
    has_playtime: bool
    grade: str
    supported_modules: List[str]
    limitations: List[str]


def _find_game_column(df: pd.DataFrame) -> str | None:
    for col in ["game_name", "game", "app_name", "appid", "app_id"]:
        if col in df.columns:
            return col
    return None


def evaluate_data_quality(df: pd.DataFrame) -> DataQualityResult:
    sample_size = len(df)
    has_sentiment = "sentiment" in df.columns
    has_topics = "topic_description" in df.columns or "topic" in df.columns
    has_player_type = "player_type" in df.columns
    has_playtime = "playtime_forever" in df.columns or "playtime_at_review" in df.columns

    date_span_days = None
    for col in ["timestamp_created", "created_at", "date"]:
        if col in df.columns:
            dates = pd.to_datetime(df[col], errors="coerce").dropna()
            if len(dates) >= 2:
                date_span_days = int((dates.max() - dates.min()).days)
            break

    game_col = _find_game_column(df)
    games_count = int(df[game_col].nunique()) if game_col else 1

    supported = ["样本浏览"]
    limitations: List[str] = []

    if sample_size >= 300 and has_sentiment:
        supported.append("情绪与口碑分析")
    else:
        limitations.append("样本量或情绪字段不足，不输出情绪策略结论")

    if sample_size >= 1000 and has_topics:
        supported.append("主题/痛点洞察")
    else:
        limitations.append("主题字段或样本量不足，主题策略需降级")

    if sample_size >= 1000 and has_player_type and has_playtime:
        supported.append("玩家分群与生命周期代理分析")
    else:
        limitations.append("缺少玩家分群/时长或样本不足，不做生命周期代理结论")

    if games_count >= 2 and sample_size >= 1000:
        supported.append("竞品/多游戏对比")
    else:
        limitations.append("竞品数据不足，竞品监控仅展示补采建议")

    if date_span_days is None or date_span_days < 14:
        limitations.append("时间跨度不足，不输出趋势性结论")
    else:
        supported.append("趋势监测")

    limitations.append("Steam公开评论不包含真实充值、登录和活动曝光数据；LTV/付费/留存只能做代理指标")

    if sample_size >= 1000 and has_sentiment:
        grade = "可用于运营分析"
    elif sample_size >= 300:
        grade = "仅可做描述性分析"
    else:
        grade = "样本不足"

    return DataQualityResult(
        sample_size=sample_size,
        date_span_days=date_span_days,
        games_count=games_count,
        has_sentiment=has_sentiment,
        has_topics=has_topics,
        has_player_type=has_player_type,
        has_playtime=has_playtime,
        grade=grade,
        supported_modules=supported,
        limitations=limitations,
    )


def build_lifecycle_proxy(df: pd.DataFrame) -> pd.DataFrame:
    """Create evidence-backed proxy scores, not real LTV/churn/payment metrics."""
    out = df.copy()
    play_col = "playtime_forever" if "playtime_forever" in out.columns else "playtime_at_review" if "playtime_at_review" in out.columns else None

    if play_col:
        play = pd.to_numeric(out[play_col], errors="coerce").fillna(0)
        # Steam often stores minutes. If values look large, convert to hours for scoring.
        play_hours = play / 60 if play.quantile(0.8) > 500 else play
        out["playtime_hours_proxy"] = play_hours
        out["value_potential_score"] = (play_hours.rank(pct=True) * 60).round(1)
    else:
        out["playtime_hours_proxy"] = 0
        out["value_potential_score"] = 0

    if "sentiment" in out.columns:
        sentiment_score = out["sentiment"].map({"positive": 25, "neutral": 10, "negative": -20}).fillna(0)
        churn_score = out["sentiment"].map({"negative": 60, "neutral": 25, "positive": 5}).fillna(20)
    elif "vote_up" in out.columns:
        sentiment_score = out["vote_up"].astype(bool).map({True: 20, False: -20})
        churn_score = out["vote_up"].astype(bool).map({True: 8, False: 55})
    else:
        sentiment_score = 0
        churn_score = 20

    helpful = pd.to_numeric(out.get("votes_helpful", 0), errors="coerce").fillna(0)
    influence = helpful.rank(pct=True).fillna(0) * 15

    out["value_potential_score"] = (out["value_potential_score"] + sentiment_score + influence).clip(0, 100).round(1)
    out["churn_risk_proxy"] = (churn_score + (100 - out["value_potential_score"]) * 0.25).clip(0, 100).round(1)

    def priority(row):
        if row["churn_risk_proxy"] >= 60 and row["value_potential_score"] >= 50:
            return "高价值挽留"
        if row["value_potential_score"] >= 70:
            return "核心玩家激活"
        if row["churn_risk_proxy"] >= 55:
            return "风险安抚"
        return "常规培育"

    out["crm_priority"] = out.apply(priority, axis=1)
    return out


def executive_summary(df: pd.DataFrame) -> Dict[str, object]:
    q = evaluate_data_quality(df)
    summary: Dict[str, object] = {
        "sample_size": q.sample_size,
        "quality_grade": q.grade,
        "games_count": q.games_count,
        "date_span_days": q.date_span_days,
        "supported_modules": q.supported_modules,
        "limitations": q.limitations,
    }
    if "sentiment" in df.columns and len(df):
        sentiment_share = df["sentiment"].value_counts(normalize=True).to_dict()
        summary["positive_rate"] = float(sentiment_share.get("positive", 0))
        summary["negative_rate"] = float(sentiment_share.get("negative", 0))
        summary["health_score"] = round((summary["positive_rate"] - summary["negative_rate"] + 1) * 50, 1)
    elif "vote_up" in df.columns and len(df):
        positive = pd.to_numeric(df["vote_up"], errors="coerce").fillna(0).astype(bool).mean()
        summary["positive_rate"] = float(positive)
        summary["negative_rate"] = float(1 - positive)
        summary["health_score"] = round(positive * 100, 1)
    else:
        summary["positive_rate"] = None
        summary["negative_rate"] = None
        summary["health_score"] = None
    return summary


def evidence_backed_actions(df: pd.DataFrame) -> List[Dict[str, str]]:
    actions: List[Dict[str, str]] = []
    if df.empty:
        return actions

    if "sentiment" in df.columns:
        neg_rate = (df["sentiment"] == "negative").mean()
        if neg_rate >= 0.35:
            actions.append({
                "title": "优先处理负面口碑主题",
                "evidence": f"负面评论占比 {neg_rate:.1%}",
                "action": "把Top负面主题拆成客服话术、版本修复公告和社区FAQ。",
                "risk": "若没有定位到具体主题，不应直接投放泛化安抚文案。",
            })
        else:
            actions.append({
                "title": "放大正向卖点，做轻量裂变",
                "evidence": f"负面评论占比 {neg_rate:.1%}，口碑风险可控",
                "action": "提炼正向高频主题，生成短视频脚本/社区话题/好友召回文案。",
                "risk": "仍需人工审核，避免AI文案与游戏真实体验不一致。",
            })

    if "player_type" in df.columns:
        top_segment = df["player_type"].value_counts().idxmax()
        actions.append({
            "title": "按玩家阶段拆分触达",
            "evidence": f"当前最大样本分群：{top_segment}",
            "action": "新手强调上手引导，普通玩家强调目标与活动，核心玩家强调版本深度和社区身份。",
            "risk": "该分群基于游玩时长代理，不能替代真实生命周期标签。",
        })

    if "topic_description" in df.columns:
        topic = df["topic_description"].value_counts().idxmax()
        actions.append({
            "title": "围绕最高频主题建立运营任务池",
            "evidence": f"最高频主题：{topic}",
            "action": "将该主题转为运营看板：问题解释、修复进度、玩家补偿或内容传播。",
            "risk": "LDA主题需要抽样人工校验，避免机器主题误读。",
        })

    return actions
