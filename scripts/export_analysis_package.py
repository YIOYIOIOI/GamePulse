"""Export GamePulse analysis package as JSON and Markdown.

Run:
    python scripts/export_analysis_package.py --input data/results/gamepulse_demo_competitor_dataset.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analysis.product_metrics import build_analysis_package  # noqa: E402


def _json_default(obj):
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    try:
        import numpy as np

        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
    except Exception:
        pass
    return str(obj)


def render_markdown(package: dict, source_name: str) -> str:
    summary = package["summary"]
    quality = package["quality"]
    lines = [
        f"# GamePulse 分析报告",
        "",
        f"数据源：`{source_name}`",
        "",
        "## 1. 总览",
        "",
        f"- 样本量：{summary.get('sample_size'):,}",
        f"- 游戏数量：{summary.get('games_count')}",
        f"- 数据评级：{summary.get('quality_grade')}",
        f"- 健康分：{summary.get('health_score')}",
        f"- 正向口碑：{summary.get('positive_rate'):.1%}" if summary.get("positive_rate") is not None else "- 正向口碑：N/A",
        f"- 负向口碑：{summary.get('negative_rate'):.1%}" if summary.get("negative_rate") is not None else "- 负向口碑：N/A",
        "",
        "## 2. 数据质量",
        "",
        f"- 时间跨度：{quality.date_span_days if quality.date_span_days is not None else 'N/A'} 天",
        f"- 可支持模块：{', '.join(quality.supported_modules)}",
        "",
        "限制：",
    ]
    lines.extend([f"- {x}" for x in quality.limitations])

    lines += ["", "## 3. 优先动作", ""]
    for action in package.get("actions", []):
        lines += [
            f"### {action['title']}",
            f"- 依据：{action['evidence']}",
            f"- 建议：{action['action']}",
            f"- 注意：{action['risk']}",
            "",
        ]

    lines += ["", "## 4. 触达策略", ""]
    for card in package.get("campaign_cards", []):
        neg = card.get("negative_rate")
        lines += [
            f"### {card['segment']}",
            f"- 样本量：{card['sample_size']:,}",
            f"- 负向占比：{neg:.1%}" if neg is not None else "- 负向占比：N/A",
            f"- 高频主题：{card['top_topic']}",
            f"- 平均游玩时长：{card['avg_playtime_hours']} 小时",
            f"- 目标：{card['goal']}",
            f"- 内容方向：{card['content_direction']}",
            f"- 运营建议：{card['operating_move']}",
            f"- 参考文案：{card['sample_copy']}",
            f"- 审核提醒：{card['audit_note']}",
            "",
        ]

    lines += ["", "## 5. 竞品摘要", ""]
    for row in package.get("competitors", []):
        pos = row.get("positive_rate")
        neg = row.get("negative_rate")
        lines += [
            f"### {row.get('game_name')}",
            f"- 评论数：{row.get('records'):,}",
            f"- 正向口碑：{pos:.1%}" if pos is not None else "- 正向口碑：N/A",
            f"- 负向口碑：{neg:.1%}" if neg is not None else "- 负向口碑：N/A",
            f"- 高频主题：{row.get('top_topic')}",
            "",
        ]

    lines += [
        "", "## 6. 口径说明", "",
        "公开 Steam 评论可以支持口碑结构、痛点排序、主题变化、时长分层和竞品口碑对比。",
        "真实 LTV、付费转化、留存、流失和 ROI 需要公司内部日志、充值、活动曝光和触达回流数据，不能由公开评论直接证明。",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/results/gamepulse_demo_competitor_dataset.csv")
    parser.add_argument("--output-dir", default="data/results")
    args = parser.parse_args()

    input_path = Path(args.input)
    df = pd.read_csv(input_path)
    package = build_analysis_package(df)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    json_path = out_dir / f"{stem}_analysis_package.json"
    md_path = out_dir / f"{stem}_analysis_report.md"

    json_path.write_text(json.dumps(package, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    md_path.write_text(render_markdown(package, input_path.name), encoding="utf-8")

    print(f"json={json_path}")
    print(f"markdown={md_path}")


if __name__ == "__main__":
    main()
