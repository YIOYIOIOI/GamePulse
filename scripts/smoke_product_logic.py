"""Smoke test for GamePulse product logic.

Run:
    python scripts/smoke_product_logic.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analysis.product_metrics import (  # noqa: E402
    build_lifecycle_proxy,
    build_product_readiness,
    competitor_summary,
    evaluate_data_quality,
    evidence_backed_actions,
    normalized_topic_series,
)


def main() -> None:
    path = ROOT / "data" / "results" / "gamepulse_demo_competitor_dataset.csv"
    if not path.exists():
        raise SystemExit(f"missing demo dataset: {path}")
    df = pd.read_csv(path)

    q = evaluate_data_quality(df)
    assert q.sample_size == len(df)
    assert q.games_count >= 2
    assert q.has_sentiment
    assert q.has_topics
    assert q.has_playtime

    topics = normalized_topic_series(df)
    assert topics is not None
    assert topics.nunique() > 1, "topics should not collapse into one word-bag label"
    assert not topics.astype(str).str.contains("muy, si", regex=False).any(), "raw LDA word bags leaked"

    lifecycle = build_lifecycle_proxy(df)
    for col in ["player_type", "value_potential_score", "churn_risk_proxy", "crm_priority"]:
        assert col in lifecycle.columns
    assert set(lifecycle["player_type"].dropna().unique()).issubset({"新手玩家", "普通玩家", "核心玩家"})

    actions = evidence_backed_actions(df)
    assert actions
    assert all({"title", "evidence", "action", "risk"}.issubset(a) for a in actions)

    comp = competitor_summary(df)
    assert len(comp) >= 2
    assert {"game_name", "records", "positive_rate", "negative_rate", "top_topic"}.issubset(comp.columns)

    readiness = build_product_readiness(df)
    assert readiness["gates"]["workspace"]["enabled"]
    assert readiness["gates"]["competitors"]["enabled"]

    print("product_logic_smoke=ok")
    print(f"rows={len(df)} games={q.games_count} topics={topics.nunique()} actions={len(actions)}")


if __name__ == "__main__":
    main()
