"""BERTopic 对比实验（可选，依赖较重，默认不安装）

LDA 的局限：词袋模型，不理解语义（"lag" 和 "latency" 是两个无关的词）。
BERTopic 用 sentence embedding + HDBSCAN 聚类，能按语义聚主题，且对多语言
更稳（配多语言 embedding 模型时）。

依赖较重（sentence-transformers -> torch，约 2GB），因此作为可选实验脚本，
不进入主 requirements。安装：

    .venv\\Scripts\\python.exe -m pip install -r requirements-topic-extras.txt

运行（建议先用语言过滤后的英文子集，与 LDA 消融实验同口径对比）:
    .venv\\Scripts\\python.exe scripts\\rerun_topics_bertopic.py \
        --input data\\results\\DOTA2_100K_20260313_205835_cleaned_sentiment_topic.csv

输出与 rerun_topics_by_language.py 同结构（主题词 + NPMI + diversity），
可与 LDA 结果直接对比。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src.analysis.language import add_language_columns  # noqa: E402
from src.analysis.topic.coherence import npmi_coherence, topic_diversity  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="BERTopic 主题建模对比（可选重依赖）")
    parser.add_argument("--input", required=True)
    parser.add_argument("--lang", default="en")
    parser.add_argument("--output", default="data/results/topic_bertopic_comparison.json")
    args = parser.parse_args()

    try:
        from bertopic import BERTopic  # noqa: F401
    except ImportError:
        print(
            "BERTopic 未安装（可选重依赖，约 2GB）。\n"
            "如需运行: .venv\\Scripts\\python.exe -m pip install -r requirements-topic-extras.txt\n"
            "说明: 主管线的语言过滤 + LDA + NPMI/NMI 评测不依赖本脚本"
            "（见 scripts/rerun_topics_by_language.py）。"
        )
        raise SystemExit(1)

    df = add_language_columns(pd.read_csv(args.input))
    subset = df[df["lang_code"] == args.lang]
    texts = subset["review_text_clean"].fillna("").astype(str).tolist()

    model = BERTopic(language="english" if args.lang == "en" else "multilingual", calculate_probabilities=False)
    topics_assign, _ = model.fit_transform(texts)

    topic_words: dict[int, list[str]] = {}
    for topic_id in sorted(set(topics_assign)):
        if topic_id == -1:  # HDBSCAN 噪声簇
            continue
        topic_words[topic_id] = [w for w, _ in model.get_topic(topic_id)][:10]

    result = {
        "condition": f"bertopic_{args.lang}_only",
        "n_docs": len(texts),
        "n_topics_found": len(topic_words),
        "outliers": int(sum(1 for t in topics_assign if t == -1)),
        "mean_npmi": npmi_coherence(topic_words, texts)["mean_npmi"],
        "topic_diversity": topic_diversity(topic_words),
        "topics_top10": {str(k): v for k, v in topic_words.items()},
        "note": "与 rerun_topics_by_language.py 的 LDA 结果同口径（NPMI/diversity），可直接对比",
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "topics_top10"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
