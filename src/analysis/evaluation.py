"""
情感模型弱标签评测

问题：此前引用的 "90%+ 准确率" 是 DistilBERT 在 SST-2 公开基准上的数字，
不是模型在本数据集上的实测表现。

方案：Steam 每条评论自带 `vote_up`（作者是否推荐该游戏）。它不是完美的
情绪 ground truth（"推荐但骂骂咧咧"的评论真实存在，DOTA2 尤甚），但作为
**弱标签**足以回答两个关键问题：
  1) 模型输出与玩家真实立场的一致率有多少？
  2) 一致率在不同语言子集上差多少？（英文模型硬套多语言文本的代价）

输出按语言分组的 agreement / precision / recall / F1，并显式携带口径说明，
供报告与前端引用。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from src.analysis.language import add_language_columns

logger = logging.getLogger(__name__)

# 结果里必须携带的口径说明：这是弱标签一致性，不是严格准确率
WEAK_LABEL_CAVEATS = [
    "vote_up 是『是否推荐游戏』的立场标签，不是评论文本情绪的严格 ground truth；"
    "『推荐但吐槽』类评论会被计为不一致。",
    "该指标应解读为『模型输出与玩家推荐立场的一致率』，用于横向对比语言子集、"
    "版本迭代，不用于宣称绝对准确率。",
    "情感模型为英文 SST-2 微调的 DistilBERT，非英文子集的表现衡量的是"
    "『错误套用』的代价，而非模型本身能力。",
]


def _binary_metrics(y_true: pd.Series, y_pred: pd.Series) -> dict:
    """正类=positive/推荐。手算混淆矩阵，避免为四个数字引入额外依赖。"""
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    total = tp + fp + fn + tn

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "n": total,
        "agreement": round((tp + tn) / total, 4) if total else None,
        "precision_pos": round(precision, 4),
        "recall_pos": round(recall, 4),
        "f1_pos": round(f1, 4),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


def evaluate_sentiment_against_votes(
    df: pd.DataFrame,
    sentiment_column: str = "sentiment",
    vote_column: str = "vote_up",
    min_group_size: int = 50,
) -> dict:
    """
    以 vote_up 为弱标签评测情感输出：整体 + 按语言分组。

    Returns: {'overall': {...}, 'by_language': {lang: {...}}, 'caveats': [...]}
    """
    required = {sentiment_column, vote_column}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"缺少评测所需列: {sorted(missing)}")

    data = add_language_columns(df)
    data = data.dropna(subset=[sentiment_column, vote_column])

    y_true = data[vote_column].astype(bool).astype(int)
    y_pred = (data[sentiment_column].astype(str).str.lower() == "positive").astype(int)

    result = {
        "overall": _binary_metrics(y_true, y_pred),
        "by_language": {},
        "caveats": WEAK_LABEL_CAVEATS,
    }

    for lang, group in data.groupby("lang_code"):
        if len(group) < min_group_size:
            continue
        gt = group[vote_column].astype(bool).astype(int)
        gp = (group[sentiment_column].astype(str).str.lower() == "positive").astype(int)
        result["by_language"][lang] = _binary_metrics(gt, gp)

    # 一个直接可引用的对比数字：英文 vs 非英文的一致率差
    en = result["by_language"].get("en")
    non_en_rows = data[data["lang_code"] != "en"]
    if en and len(non_en_rows) >= min_group_size:
        gt = non_en_rows[vote_column].astype(bool).astype(int)
        gp = (non_en_rows[sentiment_column].astype(str).str.lower() == "positive").astype(int)
        result["non_english_overall"] = _binary_metrics(gt, gp)
        result["en_minus_non_en_agreement"] = round(
            en["agreement"] - result["non_english_overall"]["agreement"], 4
        )

    return result


def format_markdown(result: dict) -> str:
    """把评测结果排成 markdown 表，报告直接引用。"""
    lines = [
        "| 子集 | n | 一致率 | P(pos) | R(pos) | F1(pos) |",
        "|---|---|---|---|---|---|",
    ]

    def _row(name: str, m: dict) -> str:
        return (
            f"| {name} | {m['n']} | {m['agreement']} | {m['precision_pos']} "
            f"| {m['recall_pos']} | {m['f1_pos']} |"
        )

    lines.append(_row("整体", result["overall"]))
    for lang, m in sorted(result["by_language"].items(), key=lambda kv: -kv[1]["n"]):
        lines.append(_row(lang, m))
    if "non_english_overall" in result:
        lines.append(_row("非英文合计", result["non_english_overall"]))

    lines.append("")
    lines.append("口径说明：")
    for c in result["caveats"]:
        lines.append(f"- {c}")
    return "\n".join(lines)


def save_result(result: dict, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("评测结果已保存: %s", path)
    return path
