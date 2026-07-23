"""
玩家分层：多特征 KMeans 聚类

历史做法是单维时长三段切分（pd.cut(playtime, [10h, 100h])），实现简单但有
两个问题：阈值是拍脑袋定的；只用时长一个维度，丢掉了社区认可度、表达强度、
评论者活跃度等信息。

本模块升级为：
  特征 = [log 时长, log 获赞数, log 评论长度, log 评论者历史评论数]
  -> StandardScaler 标准化
  -> KMeans（k 用轮廓系数在 2..6 里自动选，random_state=42 可复现）
  -> 簇按平均时长排序映射成可读标签（轻度/普通/核心/硬核...）

保留时长分位切分作为 fallback（sklearn 不可用或样本 < min_samples 时），
并在输出 metadata 里注明用了哪条路径——分层口径必须可追溯。

取 log 的原因：playtime/votes 是重尾分布（有 4000+ 小时的巨鲸），不取 log
的话 KMeans 的欧氏距离会被极端值主导。
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# 按簇的平均时长升序命名；k 超出映射时退化为"层级N"
TIER_NAMES = {
    2: ["轻度玩家", "核心玩家"],
    3: ["轻度玩家", "普通玩家", "核心玩家"],
    4: ["轻度玩家", "普通玩家", "核心玩家", "硬核玩家"],
    5: ["轻度玩家", "休闲玩家", "普通玩家", "核心玩家", "硬核玩家"],
    6: ["轻度玩家", "休闲玩家", "普通玩家", "投入玩家", "核心玩家", "硬核玩家"],
}

FEATURE_CANDIDATES = {
    "playtime_forever": "log_playtime",
    "votes_up": "log_votes_up",
    "review_length": "log_review_length",
    "num_reviews": "log_num_reviews",
}


def _fallback_playtime_cut(df: pd.DataFrame, reason: str) -> tuple[pd.DataFrame, dict]:
    """时长三段 fallback（与历史口径一致），metadata 里写明降级原因。"""
    out = df.copy()
    hours = out.get("playtime_forever", pd.Series(0, index=out.index)).fillna(0) / 60
    out["segment_label"] = pd.cut(
        hours, bins=[-0.1, 10, 100, float("inf")], labels=["轻度玩家", "普通玩家", "核心玩家"]
    ).astype(str)
    out["segment_cluster"] = out["segment_label"].map({"轻度玩家": 0, "普通玩家": 1, "核心玩家": 2})
    meta = {
        "method": "playtime_cut_fallback",
        "reason": reason,
        "k": 3,
        "note": "单维时长切分（10h/100h 阈值），仅在 KMeans 不可用时使用",
    }
    logger.warning("玩家分层降级为时长切分: %s", reason)
    return out, meta


def segment_players(
    df: pd.DataFrame,
    k_range: tuple[int, int] = (2, 6),
    min_samples: int = 100,
    random_state: int = 42,
) -> tuple[pd.DataFrame, dict]:
    """
    多特征 KMeans 玩家分层。

    Returns:
        (带 segment_cluster / segment_label 列的 DataFrame, metadata dict)
        metadata: method / k / silhouette / features / cluster_profiles / 或降级原因
    """
    if len(df) < min_samples:
        return _fallback_playtime_cut(df, f"样本量 {len(df)} < {min_samples}")

    try:
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return _fallback_playtime_cut(df, "scikit-learn 未安装")

    out = df.copy()

    # 前端行数据可能没带 review_length（标准化时被裁掉），从原文现算，保证特征可用
    if "review_length" not in out.columns and "review_text" in out.columns:
        out["review_length"] = out["review_text"].astype(str).str.len()

    # 1. 特征构造（重尾 -> log1p；缺列自动跳过并记录）
    features_used: list[str] = []
    matrix_cols: list[str] = []
    for source, target in FEATURE_CANDIDATES.items():
        if source in out.columns:
            out[target] = np.log1p(pd.to_numeric(out[source], errors="coerce").fillna(0).clip(lower=0))
            features_used.append(source)
            matrix_cols.append(target)

    if "playtime_forever" not in features_used:
        return _fallback_playtime_cut(df, "缺少 playtime_forever 特征列")

    X = StandardScaler().fit_transform(out[matrix_cols].to_numpy())

    # 2. 轮廓系数选 k（可复现：固定 random_state / n_init）
    best_k: Optional[int] = None
    best_score = -1.0
    best_labels = None
    for k in range(k_range[0], k_range[1] + 1):
        model = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        labels = model.fit_predict(X)
        score = silhouette_score(X, labels, random_state=random_state)
        logger.info("KMeans k=%d silhouette=%.4f", k, score)
        if score > best_score:
            best_k, best_score, best_labels = k, score, labels

    out["segment_cluster"] = best_labels

    # 3. 簇 -> 可读标签：按平均时长升序命名，保证标签语义稳定
    mean_playtime = out.groupby("segment_cluster")["playtime_forever"].mean().sort_values()
    names = TIER_NAMES.get(best_k, [f"层级{i+1}" for i in range(best_k)])
    label_map = {cluster: names[rank] for rank, cluster in enumerate(mean_playtime.index)}
    out["segment_label"] = out["segment_cluster"].map(label_map)

    # 4. 每簇画像（分层结果必须可解释，不能只给一个簇号）
    profiles = {}
    for cluster, group in out.groupby("segment_cluster"):
        profiles[str(label_map[cluster])] = {
            "n": int(len(group)),
            "share": round(len(group) / len(out), 4),
            "avg_playtime_hours": round(float(group["playtime_forever"].mean()) / 60, 1),
            "avg_votes_up": round(float(group["votes_up"].mean()), 2) if "votes_up" in group else None,
            "avg_review_length": round(float(group["review_length"].mean()), 1)
            if "review_length" in group
            else None,
        }

    meta = {
        "method": "kmeans_multifeature",
        "k": int(best_k),
        "silhouette": round(float(best_score), 4),
        "features": features_used,
        "scaling": "StandardScaler(log1p 特征)",
        "k_selection": f"silhouette 在 {k_range[0]}..{k_range[1]} 里取最高",
        "random_state": random_state,
        "cluster_profiles": profiles,
    }
    return out, meta


def main() -> None:
    """命令行入口：python -m src.analysis.segmentation.player_segmentation --input <csv>"""
    import argparse
    import json
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description="多特征 KMeans 玩家分层")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default=None, help="分层后 CSV 输出路径（默认在原名后加 _segmented）")
    parser.add_argument("--meta-output", default="data/results/player_segmentation_meta.json")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    df = pd.read_csv(args.input)
    segmented, meta = segment_players(df)

    from pathlib import Path

    out_path = Path(args.output) if args.output else Path(args.input).with_name(Path(args.input).stem + "_segmented.csv")
    segmented.to_csv(out_path, index=False, encoding="utf-8-sig")

    meta_path = Path(args.meta_output)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"\n分层结果: {out_path}")


if __name__ == "__main__":
    main()
