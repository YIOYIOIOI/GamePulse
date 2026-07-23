"""
主题质量量化指标（无重依赖，基于文档共现手算）

为什么需要：主题模型的输出不能靠"看着像不像话"来验收。本模块提供两个
可自动跑的指标，用于对比不同建模配置（如：是否语言过滤）：

1. NPMI 主题连贯性 (Normalized PMI coherence)
   对每个主题的 top-N 词计算两两 NPMI（基于文档级共现），值域 [-1, 1]，
   越高表示主题词越倾向于在同一篇文档共同出现（主题越连贯）。

2. 主题多样性 (topic diversity)
   所有主题 top-N 词的去重比例，值域 (0, 1]，越高表示主题间重叠越少。

实现说明：直接用 sklearn 的 CountVectorizer 词表 + scipy 稀疏矩阵算共现，
不引入 gensim（重依赖），结果与 gensim 的 c_npmi 同一口径。
"""

from __future__ import annotations

import logging
from itertools import combinations
from math import log

import numpy as np

logger = logging.getLogger(__name__)


def _document_frequencies(texts: list[str], vocabulary: list[str], stop_words=None):
    """对给定词表构建二值文档-词矩阵，返回 (单词文档频次, 成对共现频次, 文档数)。"""
    from sklearn.feature_extraction.text import CountVectorizer

    vectorizer = CountVectorizer(
        vocabulary=vocabulary,
        binary=True,
        ngram_range=(1, 2),  # 与主题模型一致，词表里可能有 bigram
        stop_words=list(stop_words) if stop_words else None,
    )
    matrix = vectorizer.fit_transform(texts)  # docs x vocab, binary
    doc_freq = np.asarray(matrix.sum(axis=0)).ravel()  # 每个词出现的文档数
    co_occurrence = (matrix.T @ matrix).toarray()  # vocab x vocab 共现文档数
    return doc_freq, co_occurrence, matrix.shape[0]


def npmi_coherence(
    topics: dict[int, list[str]],
    texts: list[str],
    top_n: int = 10,
    epsilon: float = 1e-12,
) -> dict:
    """
    计算每个主题的 NPMI 连贯性与全模型均值。

    Args:
        topics: {topic_id: [top words]}（来自 TopicAnalyzer.get_top_words_per_topic）
        texts:  与建模同源的文本列表（同一预处理口径）
        top_n:  每个主题取前 N 个词参与计算

    Returns:
        {'per_topic': {id: npmi}, 'mean_npmi': float, 'top_n': int}
    """
    vocabulary = sorted({w for words in topics.values() for w in words[:top_n]})
    if not vocabulary:
        return {"per_topic": {}, "mean_npmi": None, "top_n": top_n}

    index = {w: i for i, w in enumerate(vocabulary)}
    doc_freq, co_occurrence, n_docs = _document_frequencies(texts, vocabulary)

    per_topic: dict[int, float] = {}
    for topic_id, words in topics.items():
        pairs = list(combinations([w for w in words[:top_n] if w in index], 2))
        if not pairs:
            per_topic[topic_id] = 0.0
            continue

        scores = []
        for w1, w2 in pairs:
            i, j = index[w1], index[w2]
            p_i = doc_freq[i] / n_docs
            p_j = doc_freq[j] / n_docs
            p_ij = co_occurrence[i, j] / n_docs
            if p_ij <= 0 or p_i <= 0 or p_j <= 0:
                scores.append(-1.0)  # 从不共现，按最不连贯计
                continue
            pmi = log(p_ij / (p_i * p_j) + epsilon)
            scores.append(pmi / (-log(p_ij + epsilon)))
        per_topic[topic_id] = round(float(np.mean(scores)), 4)

    mean = round(float(np.mean(list(per_topic.values()))), 4) if per_topic else None
    return {"per_topic": per_topic, "mean_npmi": mean, "top_n": top_n}


def topic_diversity(topics: dict[int, list[str]], top_n: int = 10) -> float:
    """所有主题 top-N 词的去重比例：1.0 = 主题间完全不重叠。"""
    all_words = [w for words in topics.values() for w in words[:top_n]]
    if not all_words:
        return 0.0
    return round(len(set(all_words)) / len(all_words), 4)


def topic_language_association(assignments: list[int], langs: list[str]) -> dict:
    """
    量化"主题在多大程度上编码了语言而非内容"。

    重要背景：NPMI 这类共现指标在多语言语料上会**奖励**语言聚类
    （同语言词天然强共现），所以 baseline 的 NPMI 反而可能更高——
    不能只看单一指标。这里用 主题分配 × 语言标签 的归一化互信息(NMI)
    直接测量混淆：NMI 越高，说明"知道主题≈知道语言"，主题模型在
    分语言而不是分内容。

    另给出每个主题的主导语言与占比，便于人工核对哪些主题是语言簇。
    """
    from sklearn.metrics import normalized_mutual_info_score

    nmi = round(float(normalized_mutual_info_score(langs, assignments)), 4)

    import pandas as pd

    df = pd.DataFrame({"topic": assignments, "lang": langs})
    dominant = {}
    language_cluster_topics = 0
    for tid, group in df.groupby("topic"):
        counts = group["lang"].value_counts()
        top_lang = counts.index[0]
        share = round(float(counts.iloc[0] / len(group)), 4)
        dominant[str(tid)] = {"dominant_lang": top_lang, "share": share, "n": len(group)}
        if top_lang != "en" and share >= 0.5:
            language_cluster_topics += 1

    return {
        "nmi_topic_vs_language": nmi,
        "non_english_language_cluster_topics": language_cluster_topics,
        "per_topic_dominant_language": dominant,
    }
