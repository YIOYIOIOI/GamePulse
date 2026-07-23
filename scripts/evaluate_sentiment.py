"""用 Steam vote_up 弱标签实测情感输出的一致率（整体 + 按语言）。

用法:
    .venv\\Scripts\\python.exe scripts\\evaluate_sentiment.py \
        --input data\\results\\DOTA2_100K_20260313_205835_cleaned_sentiment_topic.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src.analysis.evaluation import (  # noqa: E402
    evaluate_sentiment_against_votes,
    format_markdown,
    save_result,
)
from src.analysis.language import verify_language_tags  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="情感模型弱标签评测")
    parser.add_argument("--input", required=True, help="清洗+情感后的 CSV")
    parser.add_argument(
        "--output",
        default="data/results/sentiment_evaluation.json",
        help="评测结果 JSON 输出路径",
    )
    parser.add_argument(
        "--verify-language-tags",
        action="store_true",
        help="用 langdetect 抽验 Steam 语言标签可信度（较慢）",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    df = pd.read_csv(args.input)
    result = evaluate_sentiment_against_votes(df)

    if args.verify_language_tags:
        result["language_tag_verification"] = verify_language_tags(df)

    save_result(result, args.output)
    print(format_markdown(result))


if __name__ == "__main__":
    main()
