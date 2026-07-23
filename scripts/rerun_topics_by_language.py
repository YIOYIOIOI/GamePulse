"""按语言分流重跑主题模型，并用 NPMI 连贯性 + 主题多样性量化改进。

历史问题：主题模型直接跑在多语言混合语料上，LDA 按"语言"而非"主题"聚类，
产出西语/俄语停用词堆（如 topic0 = "muy, si, moba, es"）。

本脚本做 A/B 对比并落盘证据：
    A. baseline  —— 全语言混合（复现历史做法）
    B. filtered  —— 仅英文子集（语言分流后）
两组都计算 NPMI 连贯性与主题多样性，让"语言过滤带来的改进"成为可引用的数字。

用法:
    .venv\\Scripts\\python.exe scripts\\rerun_topics_by_language.py \
        --input data\\results\\DOTA2_100K_20260313_205835_cleaned_sentiment_topic.csv
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src.analysis.language import add_language_columns, language_distribution  # noqa: E402
from src.analysis.topic.coherence import (  # noqa: E402
    npmi_coherence,
    topic_diversity,
    topic_language_association,
)
from src.analysis.topic.topic_analyzer import TopicAnalyzer  # noqa: E402

# 说明：本脚本是研究/复现用的 A/B 对比工具。日常分析请走统一管线
# （src/analysis/pipeline.py，main.py --mode analyze 已内置语言过滤与指标）。

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "topic_analysis": {
        "method": "lda",
        "num_topics": 10,
        "max_features": 5000,
        "ngram_range": [1, 2],
        "min_df": 5,
        "max_df": 0.8,
    }
}


def run_condition(name: str, texts: list[str], config: dict) -> dict:
    """跑一组条件：建模 + 指标。每组用全新 analyzer，避免状态串扰。"""
    analyzer = TopicAnalyzer(config)
    doc_topic, _ = analyzer.fit_transform(texts)
    topics = analyzer.get_top_words_per_topic(n_words=10)

    coherence = npmi_coherence(topics, texts)
    diversity = topic_diversity(topics)

    logger.info("[%s] docs=%d mean_npmi=%s diversity=%s", name, len(texts), coherence["mean_npmi"], diversity)
    return {
        "condition": name,
        "n_docs": len(texts),
        "mean_npmi": coherence["mean_npmi"],
        "topic_diversity": diversity,
        "per_topic_npmi": coherence["per_topic"],
        "topics_top10": {str(k): v for k, v in topics.items()},
        "assignments": doc_topic.argmax(axis=1).tolist(),
    }


# topic_language_association 已上移至 src/analysis/topic/coherence.py（统一管线复用）


def main() -> None:
    parser = argparse.ArgumentParser(description="按语言分流重跑主题模型（A/B 对比）")
    parser.add_argument("--input", required=True, help="清洗后的 CSV（需含 review_text_clean / language）")
    parser.add_argument("--lang", default="en", help="过滤保留的语言桶（默认 en）")
    parser.add_argument(
        "--output",
        default="data/results/topic_language_ablation.json",
        help="对比结果 JSON 输出路径",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    df = pd.read_csv(args.input)
    df = add_language_columns(df)
    texts_all = df["review_text_clean"].fillna("").astype(str).tolist()
    df_lang = df[df["lang_code"] == args.lang]
    texts_lang = df_lang["review_text_clean"].fillna("").astype(str).tolist()

    baseline = run_condition("baseline_all_languages", texts_all, DEFAULT_CONFIG)
    filtered = run_condition(f"filtered_{args.lang}_only", texts_lang, DEFAULT_CONFIG)

    # 主题×语言混淆度：baseline 用全量语言标签；filtered 单语言下无意义（恒0）
    baseline["language_association"] = topic_language_association(
        baseline.pop("assignments"), df["lang_code"].tolist()
    )
    filtered.pop("assignments", None)

    result = {
        "input": str(args.input),
        "language_distribution": language_distribution(df).to_dict(),
        "baseline_all_languages": baseline,
        f"filtered_{args.lang}_only": filtered,
        "note": (
            "两组使用完全相同的建模配置（LDA/CountVectorizer/random_state=42），唯一变量是语言过滤。"
            "指标解读注意：NPMI 在多语言语料上会奖励语言聚类（同语言词天然强共现），"
            "因此 baseline 的 NPMI 可能虚高——需配合 nmi_topic_vs_language（主题×语言互信息）解读："
            "该值越高说明主题在编码语言而非内容；语言过滤后该混淆源被消除。"
        ),
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    a = result["baseline_all_languages"]
    b = result[f"filtered_{args.lang}_only"]
    print("\n===== 语言过滤 A/B 对比 =====")
    print(f"baseline (全语言, n={a['n_docs']}):  NPMI={a['mean_npmi']}  diversity={a['topic_diversity']}")
    print(f"filtered ({args.lang}, n={b['n_docs']}):  NPMI={b['mean_npmi']}  diversity={b['topic_diversity']}")
    print("\n--- baseline 主题示例（前3） ---")
    for tid in list(a["topics_top10"])[:3]:
        print(f"  topic {tid}: {', '.join(a['topics_top10'][tid][:5])}")
    print(f"\n--- filtered({args.lang}) 主题示例（前3） ---")
    for tid in list(b["topics_top10"])[:3]:
        print(f"  topic {tid}: {', '.join(b['topics_top10'][tid][:5])}")
    print(f"\n结果已保存: {out}")


if __name__ == "__main__":
    main()
