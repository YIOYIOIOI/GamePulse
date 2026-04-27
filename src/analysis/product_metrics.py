"""Product analytics helpers for GamePulse.

This module keeps the product honest:
- Steam/public review data can support sentiment, topic, player feedback, and
  competitor comparison.
- It cannot support true LTV, payment conversion, retention, churn, or ROI
  without internal telemetry and payment/event logs.

Functions here return plain Python / pandas objects so the UI layer can present
results without inventing business claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd


SENTIMENT_POSITIVE = {"positive", "pos", "好评", "推荐", "recommend", "recommended", "true", "1", "yes"}
SENTIMENT_NEGATIVE = {"negative", "neg", "差评", "不推荐", "not recommended", "false", "0", "no"}
GENERIC_TOPICS = {"泛体验反馈/未分类", "待归类主题", "unknown", "none", "nan", ""}

TOPIC_RULES = {
    "匹配与公平性": ["match", "rank", "mmr", "teammate", "balance", "fair", "smurf", "cheat", "hack"],
    "性能与稳定性": ["server", "lag", "fps", "crash", "bug", "disconnect", "stutter", "performance"],
    "新手体验": ["tutorial", "new player", "learn", "hard", "beginner", "complex", "confusing"],
    "内容与版本": ["update", "patch", "hero", "map", "mode", "content", "event", "meta"],
    "付费感知": ["pay", "price", "skin", "battle pass", "money", "expensive", "microtransaction"],
    "社区氛围": ["toxic", "community", "friend", "team", "chat", "report", "russian", "china", "online"],
}

PLAYER_TYPE_MAP = {
    "new_player": "新手玩家",
    "newbie": "新手玩家",
    "beginner": "新手玩家",
    "casual_player": "普通玩家",
    "casual": "普通玩家",
    "regular_player": "普通玩家",
    "normal": "普通玩家",
    "hardcore_player": "核心玩家",
    "hardcore": "核心玩家",
    "core_player": "核心玩家",
}


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


def _find_first_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    lowered = {str(c).lower(): c for c in df.columns}
    for cand in candidates:
        if cand in df.columns:
            return cand
        if cand.lower() in lowered:
            return lowered[cand.lower()]
    return None


def _find_game_column(df: pd.DataFrame) -> str | None:
    return _find_first_column(df, ["game_name", "game", "app_name", "name", "appid", "app_id"])


def _find_text_column(df: pd.DataFrame) -> str | None:
    return _find_first_column(df, ["review_text", "review", "content", "text", "comment", "评论", "评论内容"])


def _find_topic_column(df: pd.DataFrame) -> str | None:
    return _find_first_column(df, ["topic_description", "topic", "topic_label", "theme", "pain_point", "主题"])


def _find_playtime_column(df: pd.DataFrame) -> str | None:
    return _find_first_column(df, ["playtime_forever", "playtime_at_review", "playtime_hours", "hours_played", "游玩时长"])


def _find_date_column(df: pd.DataFrame) -> str | None:
    return _find_first_column(df, ["timestamp_created", "created_at", "timestamp_updated", "date", "datetime", "time", "评论时间"])


def canonical_sentiment_series(df: pd.DataFrame) -> pd.Series | None:
    """Return normalized positive/negative/neutral sentiment if possible."""
    sentiment_col = _find_first_column(df, ["sentiment", "sentiment_label", "label", "情绪", "口碑"])
    if sentiment_col:
        raw = df[sentiment_col].astype(str).str.strip().str.lower()
        return raw.map(
            lambda x: "positive" if x in SENTIMENT_POSITIVE else "negative" if x in SENTIMENT_NEGATIVE else "neutral"
        )
    vote_col = _find_first_column(df, ["vote_up", "voted_up", "recommended", "is_positive"])
    if vote_col:
        return df[vote_col].astype(bool).map({True: "positive", False: "negative"})
    return None


def playtime_hours_series(df: pd.DataFrame) -> pd.Series:
    play_col = _find_playtime_column(df)
    if not play_col:
        return pd.Series(0.0, index=df.index)
    play = pd.to_numeric(df[play_col], errors="coerce").fillna(0)
    # Steam raw API usually returns minutes. Existing light collector stores hours.
    return play / 60 if play.quantile(0.8) > 500 else play


def classify_topic_from_text(text: object) -> str:
    text_l = str(text or "").lower()
    scores = {topic: sum(1 for kw in kws if kw in text_l) for topic, kws in TOPIC_RULES.items()}
    best, score = max(scores.items(), key=lambda x: x[1])
    return best if score else "泛体验反馈/未分类"


def humanize_topic(value: object, fallback_text: object | None = None) -> str:
    text = str(value or "").strip()
    text_l = text.lower()
    if not text or text_l in GENERIC_TOPICS:
        return classify_topic_from_text(fallback_text) if fallback_text is not None else "泛体验反馈/未分类"
    for topic, keywords in TOPIC_RULES.items():
        if any(kw in text_l for kw in keywords):
            return topic
    # Old LDA output often appears as a short comma-separated word bag.
    # Convert it via review text when available, otherwise keep a safe label.
    if "," in text and len(text) < 120:
        return classify_topic_from_text(fallback_text) if fallback_text is not None else "待归类主题"
    return text


def normalize_player_type_value(value: object) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "unknown"}:
        return "普通玩家"
    return PLAYER_TYPE_MAP.get(text.lower(), text)


def normalized_topic_series(df: pd.DataFrame) -> pd.Series | None:
    topic_col = _find_topic_column(df)
    text_col = _find_text_column(df)
    if topic_col:
        if text_col:
            return df.apply(lambda row: humanize_topic(row.get(topic_col), row.get(text_col)), axis=1)
        return df[topic_col].map(humanize_topic)
    if text_col:
        return df[text_col].map(classify_topic_from_text)
    return None


def select_actionable_topic(series: pd.Series | None) -> str | None:
    if series is None or series.empty:
        return None
    counts = series.fillna("泛体验反馈/未分类").astype(str).str.strip().value_counts()
    useful = counts.drop(labels=[x for x in GENERIC_TOPICS if x in counts.index], errors="ignore")
    if len(useful):
        return str(useful.idxmax())
    return str(counts.idxmax()) if len(counts) else None


def ensure_player_type(df: pd.DataFrame) -> pd.Series:
    if "player_type" in df.columns:
        return df["player_type"].map(normalize_player_type_value)
    hours = playtime_hours_series(df)
    bins = [-1, 10, 100, float("inf")]
    labels = ["新手玩家", "普通玩家", "核心玩家"]
    return pd.cut(hours, bins=bins, labels=labels).astype(str)


def evaluate_data_quality(df: pd.DataFrame) -> DataQualityResult:
    sample_size = len(df)
    sentiment = canonical_sentiment_series(df)
    topics = normalized_topic_series(df)
    play_col = _find_playtime_column(df)
    text_col = _find_text_column(df)

    has_sentiment = sentiment is not None
    has_topics = topics is not None or text_col is not None
    has_player_type = "player_type" in df.columns or play_col is not None
    has_playtime = play_col is not None

    date_span_days = None
    date_col = _find_date_column(df)
    if date_col:
        dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
        if len(dates) >= 2:
            date_span_days = max(0, int((dates.max() - dates.min()).days))

    game_col = _find_game_column(df)
    games_count = int(df[game_col].nunique()) if game_col else 1

    supported = ["基础数据概览"]
    limitations: List[str] = []

    if sample_size >= 300 and has_sentiment:
        supported.append("口碑结构分析")
    else:
        limitations.append("样本量或口碑字段不足，只能做基础预览")

    if sample_size >= 300 and has_topics:
        supported.append("主题/痛点分析")
        if topics is None and text_col is not None:
            limitations.append("主题来自评论文本的轻量归类，正式报告前需要抽样复核")
    else:
        limitations.append("主题字段或评论文本不足，主题洞察需要降级")

    if sample_size >= 300 and has_playtime:
        supported.append("玩家分层与触达优先级")
    else:
        limitations.append("缺少游玩时长，玩家分层只能使用弱规则或隐藏")

    if games_count >= 2 and sample_size >= 300:
        supported.append("竞品/多游戏对比")
    else:
        limitations.append("至少需要两款游戏数据，竞品对比才有意义")

    if date_span_days is not None and date_span_days >= 14:
        supported.append("趋势观察")
    else:
        limitations.append("时间跨度不足 14 天，不建议输出趋势结论")

    limitations.append("公开评论不能证明真实 LTV、付费转化、留存、流失或活动 ROI")

    if sample_size >= 1000 and has_sentiment and has_topics:
        grade = "可用于运营分析"
    elif sample_size >= 300:
        grade = "可做描述性分析"
    elif sample_size > 0:
        grade = "仅可预览"
    else:
        grade = "无数据"

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
        limitations=list(dict.fromkeys(limitations)),
    )


def build_lifecycle_proxy(df: pd.DataFrame) -> pd.DataFrame:
    """Create transparent proxy scores, not real LTV/churn/payment metrics."""
    out = df.copy()
    sentiment = canonical_sentiment_series(out)
    play_hours = playtime_hours_series(out)
    player_type = ensure_player_type(out)

    out["player_type"] = player_type
    out["playtime_hours_proxy"] = play_hours.round(2)

    play_score = (play_hours.rank(pct=True) * 55).fillna(0)
    helpful_col = _find_first_column(out, ["votes_helpful", "votes_up", "weighted_vote_score"])
    if helpful_col:
        helpful = pd.to_numeric(out[helpful_col], errors="coerce").fillna(0)
        influence_score = helpful.rank(pct=True).fillna(0) * 15
    else:
        influence_score = pd.Series(0.0, index=out.index)

    if sentiment is not None:
        sentiment_value = sentiment.map({"positive": 25, "neutral": 8, "negative": -18}).fillna(0)
        risk_base = sentiment.map({"positive": 8, "neutral": 28, "negative": 62}).fillna(25)
    else:
        sentiment_value = pd.Series(0.0, index=out.index)
        risk_base = pd.Series(25.0, index=out.index)

    value = (play_score + influence_score + sentiment_value).clip(0, 100).round(1)
    risk = (risk_base + (100 - value) * 0.22).clip(0, 100).round(1)

    out["value_potential_score"] = value
    out["churn_risk_proxy"] = risk

    def priority(row) -> str:
        if row["churn_risk_proxy"] >= 62 and row["value_potential_score"] >= 45:
            return "高价值风险玩家"
        if row["value_potential_score"] >= 72:
            return "核心玩家维护"
        if row["churn_risk_proxy"] >= 58:
            return "风险安抚"
        if row["player_type"] == "新手玩家":
            return "新手引导"
        return "常规运营"

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
    sentiment = canonical_sentiment_series(df)
    if sentiment is not None and len(df):
        share = sentiment.value_counts(normalize=True).to_dict()
        positive = float(share.get("positive", 0))
        negative = float(share.get("negative", 0))
        summary["positive_rate"] = positive
        summary["negative_rate"] = negative
        summary["health_score"] = round((positive - negative + 1) * 50, 1)
    else:
        summary["positive_rate"] = None
        summary["negative_rate"] = None
        summary["health_score"] = None
    return summary


def evidence_backed_actions(df: pd.DataFrame) -> List[Dict[str, str]]:
    actions: List[Dict[str, str]] = []
    if df.empty:
        return actions

    sentiment = canonical_sentiment_series(df)
    topics = normalized_topic_series(df)
    main_topic = select_actionable_topic(topics)

    if sentiment is not None:
        neg_rate = float((sentiment == "negative").mean())
        if neg_rate >= 0.45:
            actions.append({
                "title": "优先处理负向口碑",
                "evidence": f"差评占比 {neg_rate:.1%}" + (f"，主要集中在「{main_topic}」" if main_topic else ""),
                "action": "先整理玩家最集中的问题，形成 FAQ、修复节奏说明和客服口径。",
                "risk": "如果没有确认真实问题，不要直接发布补偿或承诺修复时间。",
            })
        elif neg_rate >= 0.25:
            actions.append({
                "title": "控制负向扩散",
                "evidence": f"差评占比 {neg_rate:.1%}，存在可见负面反馈",
                "action": "挑选高频主题做解释型内容，并在社区入口引导玩家反馈具体场景。",
                "risk": "解释内容需要和真实版本计划一致，避免被玩家认为是在搪塞。",
            })
        else:
            actions.append({
                "title": "放大正向口碑",
                "evidence": f"差评占比 {neg_rate:.1%}，整体口碑风险较低",
                "action": "提炼好评中的高频亮点，用于商店页、社区贴、短视频脚本或活动预热。",
                "risk": "传播内容仍需人工审核，不能夸大公开评论无法证明的经营效果。",
            })

    player_type = ensure_player_type(df)
    if len(player_type):
        top_segment = str(player_type.value_counts().idxmax())
        actions.append({
            "title": "按玩家阶段拆分触达",
            "evidence": f"当前最大玩家群体是「{top_segment}」",
            "action": "新手强调上手解释，普通玩家强调阶段目标，核心玩家强调版本深度和参与感。",
            "risk": "公开评论只能粗略分层，不能替代内部用户生命周期标签。",
        })

    if main_topic:
        actions.append({
            "title": "围绕高频主题建立运营专题",
            "evidence": f"最高频可行动主题是「{main_topic}」",
            "action": "将该主题拆成问题解释、处理进度、玩家反馈入口和后续内容计划。",
            "risk": "如果主题来自关键词归类，正式对外前需要抽样复核评论原文。",
        })

    return actions


def competitor_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Return per-game summary for competitor comparison."""
    if df.empty:
        return pd.DataFrame()
    game_col = _find_game_column(df)
    if not game_col:
        return pd.DataFrame()

    work = df.copy()
    sentiment = canonical_sentiment_series(work)
    if sentiment is not None:
        work["_sentiment_norm"] = sentiment
    topics = normalized_topic_series(work)
    if topics is not None:
        work["_topic_norm"] = topics

    rows = []
    for game, part in work.groupby(game_col):
        row: Dict[str, object] = {"game_name": game, "records": len(part)}
        if "_sentiment_norm" in part.columns:
            row["positive_rate"] = float((part["_sentiment_norm"] == "positive").mean())
            row["negative_rate"] = float((part["_sentiment_norm"] == "negative").mean())
        else:
            row["positive_rate"] = None
            row["negative_rate"] = None
        row["top_topic"] = select_actionable_topic(part["_topic_norm"]) if "_topic_norm" in part.columns else None
        rows.append(row)
    return pd.DataFrame(rows).sort_values("records", ascending=False)



def build_product_readiness(df: pd.DataFrame) -> Dict[str, object]:
    """Single contract for frontend product gating and walkthrough state."""
    q = evaluate_data_quality(df)
    summary = executive_summary(df)
    sentiment = canonical_sentiment_series(df)
    topics = normalized_topic_series(df)
    game_col = _find_game_column(df)
    text_col = _find_text_column(df)

    gates = {
        "workspace": {"enabled": q.sample_size > 0, "reason": "需要先接入数据" if q.sample_size == 0 else "可查看概览"},
        "quality": {"enabled": q.sample_size > 0, "reason": "需要先接入数据" if q.sample_size == 0 else "可查看数据体检"},
        "voice": {"enabled": sentiment is not None or topics is not None, "reason": "需要口碑字段或评论文本"},
        "segments": {"enabled": q.has_playtime and q.sample_size >= 300, "reason": "需要游玩时长且样本量不少于 300"},
        "campaigns": {"enabled": q.sample_size >= 300 and (sentiment is not None or topics is not None), "reason": "需要至少 300 条评论和口碑/主题信号"},
        "competitors": {"enabled": q.games_count >= 2, "reason": "需要至少两款游戏数据"},
        "trend": {"enabled": q.date_span_days is not None and q.date_span_days >= 14, "reason": "需要至少 14 天时间跨度"},
    }

    field_status = {
        "game": game_col is not None,
        "review_text": text_col is not None,
        "sentiment": sentiment is not None,
        "topic": topics is not None,
        "player_type": q.has_player_type,
        "playtime": q.has_playtime,
        "date": q.date_span_days is not None,
    }

    next_steps: List[str] = []
    if q.sample_size == 0:
        next_steps.append("先在数据中心采集 Steam 评论或加载 CSV")
    if q.sample_size and q.sample_size < 300:
        next_steps.append("样本量低于 300，建议继续采集后再输出策略")
    if q.games_count < 2:
        next_steps.append("如需竞品对比，请追加采集另一款游戏")
    if not q.has_playtime:
        next_steps.append("如需玩家分层，请补充游玩时长字段")
    if sentiment is None:
        next_steps.append("如需口碑分析，请补充 sentiment 或 vote_up 字段")
    if not next_steps:
        next_steps.append("数据已可支持完整演示流程")

    return {
        "quality": q,
        "summary": summary,
        "gates": gates,
        "field_status": field_status,
        "next_steps": next_steps,
    }



def campaign_strategy_cards(df: pd.DataFrame) -> List[Dict[str, object]]:
    """Build structured campaign strategy cards by player segment.

    The output is intentionally frontend-friendly and report-friendly. It is not
    a final publishing copy; every card contains an audit warning.
    """
    if df.empty:
        return []

    work = df.copy()
    sentiment = canonical_sentiment_series(work)
    if sentiment is not None:
        work["_sentiment_norm"] = sentiment
    topics = normalized_topic_series(work)
    if topics is not None:
        work["_topic_norm"] = topics
    work["_player_type_norm"] = ensure_player_type(work)
    work["_playtime_hours"] = playtime_hours_series(work)

    segment_defaults = {
        "新手玩家": {
            "goal": "降低首次挫败，让玩家尽快理解核心乐趣。",
            "content_direction": "上手任务、失败原因解释、低门槛奖励、3 分钟入门指南。",
            "tone": "清楚、耐心、少术语。",
        },
        "普通玩家": {
            "goal": "给出下一步目标，把零散活跃变成稳定参与。",
            "content_direction": "阶段目标、限时活动、版本亮点、好友组队奖励。",
            "tone": "直接、明确、强调收益和进度。",
        },
        "核心玩家": {
            "goal": "保留高投入玩家的参与感，减少负面扩散。",
            "content_direction": "版本解读、平衡性说明、高阶挑战、社区共创议题。",
            "tone": "尊重判断，给足背景和解释。",
        },
    }

    cards: List[Dict[str, object]] = []
    for segment, part in work.groupby("_player_type_norm", dropna=False):
        segment = normalize_player_type_value(segment)
        defaults = segment_defaults.get(segment, segment_defaults["普通玩家"])
        neg_rate = float((part["_sentiment_norm"] == "negative").mean()) if "_sentiment_norm" in part else None
        topic = select_actionable_topic(part["_topic_norm"]) if "_topic_norm" in part else "泛体验反馈"
        avg_play = float(part["_playtime_hours"].mean()) if len(part) else 0.0

        if neg_rate is not None and neg_rate >= 0.45:
            operating_move = f"先解释和安抚「{topic}」相关问题，再同步修复节奏或补偿安排。"
            sample_copy = f"我们看到最近关于「{topic}」的反馈比较集中，团队会优先同步处理进展。"
            priority = "高"
        elif avg_play >= 100:
            operating_move = f"把「{topic}」做成版本解读或社区讨论议题，邀请高投入玩家参与反馈。"
            sample_copy = f"你已经体验了很长时间，我们想邀请你一起讨论「{topic}」相关的版本调整。"
            priority = "中"
        else:
            operating_move = f"围绕「{topic}」设计轻量任务，给玩家一个继续体验的理由。"
            sample_copy = f"围绕「{topic}」，我们准备了一个轻量挑战，完成后可以解锁下一阶段奖励。"
            priority = "中"

        cards.append({
            "segment": segment,
            "sample_size": int(len(part)),
            "negative_rate": neg_rate,
            "top_topic": topic,
            "avg_playtime_hours": round(avg_play, 1),
            "priority": priority,
            "goal": defaults["goal"],
            "content_direction": defaults["content_direction"],
            "tone": defaults["tone"],
            "operating_move": operating_move,
            "sample_copy": sample_copy,
            "audit_note": "发布前必须由运营确认是否符合当前版本内容；关键词归类主题建议抽样复核。",
        })

    order = {"高": 0, "中": 1, "低": 2}
    return sorted(cards, key=lambda x: (order.get(str(x["priority"]), 9), -int(x["sample_size"])))


def build_analysis_package(df: pd.DataFrame) -> Dict[str, object]:
    """One-stop backend package for frontend pages, exports, and demos."""
    readiness = build_product_readiness(df)
    package: Dict[str, object] = {
        "summary": readiness["summary"],
        "quality": readiness["quality"],
        "gates": readiness["gates"],
        "field_status": readiness["field_status"],
        "next_steps": readiness["next_steps"],
        "actions": evidence_backed_actions(df),
        "campaign_cards": campaign_strategy_cards(df),
        "competitors": competitor_summary(df).to_dict("records"),
    }
    topics = normalized_topic_series(df)
    if topics is not None:
        package["top_topics"] = topics.value_counts().head(10).to_dict()
    sentiment = canonical_sentiment_series(df)
    if sentiment is not None:
        package["sentiment_counts"] = sentiment.value_counts().to_dict()
    return package
