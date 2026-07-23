"""GamePulse 统一分析管线（单一事实源）。

背景：2026-07 的质量升级（语言分流、弱标签评测、主题质量指标、KMeans 分层）
最初以旁路脚本形式存在，导致仓库里出现两条互不为超集的链路：
- 旧链路 main.py：情绪 → LDA 主题 → 摘要/策略/报告，但没有语言过滤和任何评测；
- 新链路 API server：质量门槛 + 独立评测端点，但不跑情绪/主题模型。

本模块把两条链路合并：CLI（main.py）、本地 API（gamepulse_api_server.py）
和复现脚本共用这里的函数，保证口径一致。

步骤（run_full）：
    语言归一 → 情绪分析（DistilBERT/规则 fallback）→ vote_up 弱标签评测
    → 语言感知的主题建模（NPMI/多样性/NMI 诊断）→ KMeans 多特征分层
    → 质量门槛与分析包
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from src.analysis.evaluation import evaluate_sentiment_against_votes
from src.analysis.language import add_language_columns, language_distribution
from src.analysis.product_metrics import build_analysis_package
from src.analysis.segmentation.player_segmentation import segment_players
from src.analysis.topic.coherence import (
    npmi_coherence,
    topic_diversity,
    topic_language_association,
)

logger = logging.getLogger(__name__)

# 主语言子集小于该阈值时不做语言过滤（样本太少建模没意义），退回全量并给出诊断
DEFAULT_MIN_DOCS_FOR_LANGUAGE_FILTER = 200


@dataclass
class PipelineResult:
    """run_full 的产物：主 DataFrame + 各步骤的结构化工件。"""

    df: pd.DataFrame
    sentiment_stats: Optional[dict] = None
    sentiment_evaluation: Optional[dict] = None
    topics: Optional[dict] = None
    topic_metrics: Optional[dict] = None
    segmentation_meta: Optional[dict] = None
    quality_package: Optional[dict] = None
    notes: list = field(default_factory=list)


def enrich_language(df: pd.DataFrame) -> pd.DataFrame:
    """语言标签归一（schinese→zh 等），加 lang_code 列。无 language 列时原样返回。"""
    if "lang_code" in df.columns:
        return df
    if "language" not in df.columns:
        logger.warning("缺少 language 列，跳过语言归一（主题建模将无法做语言过滤）")
        return df
    return add_language_columns(df)


def run_sentiment(df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, dict]:
    """情绪分析：transformers 可用走 DistilBERT，否则规则 fallback（analyzer 内部自动降级）。"""
    from src.analysis.sentiment.sentiment_analyzer import SentimentAnalyzer

    analyzer = SentimentAnalyzer(config)
    df = analyzer.analyze_dataframe(df)
    stats = analyzer.get_sentiment_stats(df)
    return df, stats


def evaluate_sentiment_quality(df: pd.DataFrame) -> Optional[dict]:
    """用 vote_up 弱标签实测情绪输出一致率（整体 + 分语言）。缺列时返回 None 而不是中断管线。"""
    try:
        return evaluate_sentiment_against_votes(df)
    except (ValueError, KeyError) as exc:
        logger.warning("弱标签评测跳过：%s", exc)
        return None


def run_topics(
    df: pd.DataFrame,
    config: dict,
    text_column: str = "review_text_clean",
) -> tuple[pd.DataFrame, dict, dict]:
    """语言感知的主题建模。

    有 lang_code 且主语言样本足够 → 只在主语言子集上建模（修复"主题=语言聚类"），
    子集外的行 topic_id 为空；否则全量建模，并用 主题×语言 NMI 输出污染诊断。

    返回 (df, topics, metrics)。metrics 记录建模口径、NPMI、多样性和（全量时的）NMI 诊断。
    """
    from src.analysis.topic.topic_analyzer import TopicAnalyzer

    topic_cfg = config.get("topic_analysis", {})
    min_docs = int(topic_cfg.get("min_docs_for_language_filter", DEFAULT_MIN_DOCS_FOR_LANGUAGE_FILTER))
    filter_mode = str(topic_cfg.get("language_filter", "auto"))  # auto / off

    metrics: dict = {"language_filter": filter_mode}
    subset = df
    modeled_language = None

    if filter_mode != "off" and "lang_code" in df.columns:
        dist = language_distribution(df)
        metrics["language_distribution"] = {str(k): int(v) for k, v in dist.items()}
        if len(dist) > 0:
            dominant = str(dist.index[0])
            dominant_n = int(dist.iloc[0])
            if dominant_n >= min_docs:
                subset = df[df["lang_code"] == dominant]
                modeled_language = dominant
            else:
                metrics["filter_skipped_reason"] = (
                    f"主语言 {dominant} 仅 {dominant_n} 条（< {min_docs}），退回全量建模"
                )
    elif "lang_code" not in df.columns:
        metrics["filter_skipped_reason"] = "无 language/lang_code 列"

    analyzer = TopicAnalyzer(config)
    subset = subset.copy()
    subset, topics = analyzer.analyze_dataframe(subset, text_column=text_column)

    # 子集建模时把主题列写回全量 df（子集外为空）
    if modeled_language is not None:
        for col in ["topic_id", "topic_description"]:
            df[col] = subset[col].reindex(df.index)
    else:
        df = subset

    metrics["modeled_language"] = modeled_language or "all"
    metrics["n_docs_modeled"] = int(len(subset))

    texts = subset[text_column].fillna("").tolist()
    metrics["npmi"] = npmi_coherence(topics, texts)
    metrics["topic_diversity"] = topic_diversity(topics)

    # 全量（未过滤）建模时，主题可能在按语言聚类——用 NMI 直接诊断并告警
    if modeled_language is None and "lang_code" in df.columns:
        assoc = topic_language_association(
            df["topic_id"].fillna(-1).astype(int).tolist(),
            df["lang_code"].fillna("unknown").tolist(),
        )
        metrics["language_association"] = assoc
        if assoc["non_english_language_cluster_topics"] > 0:
            logger.warning(
                "检测到 %s 个语言簇主题（NMI=%s）：主题模型可能在按语言而非内容聚类，"
                "建议提供 language 列以启用语言过滤",
                assoc["non_english_language_cluster_topics"],
                assoc["nmi_topic_vs_language"],
            )

    return df, topics, metrics


def run_segmentation(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """KMeans 多特征玩家分层（log1p+标准化、轮廓系数自动选 k；样本不足回退时长切分）。"""
    return segment_players(df)


def run_quality(df: pd.DataFrame) -> dict:
    """质量门槛 + 前端分析包（样本量/时间跨度/字段完整性，证据不足自动降级）。"""
    return build_analysis_package(df)


def run_full(
    df: pd.DataFrame,
    config: dict,
    *,
    with_models: bool = True,
) -> PipelineResult:
    """完整管线。with_models=False 时跳过情绪/主题模型（API 同步请求等轻量场景），
    只做语言归一、弱标签评测（若已有情绪列）、分层和质量包。"""
    result = PipelineResult(df=df)

    df = enrich_language(df)

    if with_models:
        df, result.sentiment_stats = run_sentiment(df, config)

    result.sentiment_evaluation = evaluate_sentiment_quality(df)
    if result.sentiment_evaluation is None:
        result.notes.append("弱标签评测未执行（缺 vote/sentiment 列）")

    if with_models:
        df, result.topics, result.topic_metrics = run_topics(df, config)

    try:
        df, result.segmentation_meta = run_segmentation(df)
    except Exception as exc:  # 分层失败不应中断整条管线
        logger.warning("玩家分层跳过：%s", exc)
        result.notes.append(f"玩家分层未执行：{exc}")

    result.quality_package = run_quality(df)
    result.df = df
    return result
