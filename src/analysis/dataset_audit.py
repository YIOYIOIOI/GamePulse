"""Audit local datasets for product-readiness.

This script helps decide whether a feature should be shown, degraded, or cut.
It does not call external APIs; it only inspects local CSV artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd

from src.analysis.product_metrics import evaluate_data_quality


def audit_file(path: Path) -> Dict[str, object]:
    df = pd.read_csv(path)
    q = evaluate_data_quality(df)
    cols = list(df.columns)
    return {
        "file": str(path),
        "rows": len(df),
        "columns": cols,
        "quality_grade": q.grade,
        "games_count": q.games_count,
        "date_span_days": q.date_span_days,
        "has_sentiment": q.has_sentiment,
        "has_topics": q.has_topics,
        "has_player_type": q.has_player_type,
        "has_playtime": q.has_playtime,
        "supported_modules": q.supported_modules,
        "limitations": q.limitations,
    }


def audit_dir(results_dir: Path) -> List[Dict[str, object]]:
    reports = []
    for path in sorted(results_dir.glob("*.csv")):
        try:
            reports.append(audit_file(path))
        except Exception as exc:  # pragma: no cover - diagnostic script
            reports.append({"file": str(path), "error": str(exc)})
    return reports


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="data/results")
    parser.add_argument("--output", default="data/results/dataset_audit.json")
    args = parser.parse_args()

    reports = audit_dir(Path(args.results_dir))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"audited_files={len(reports)}")
    for r in reports:
        if "error" in r:
            print(f"ERROR {Path(r['file']).name}: {r['error']}")
        else:
            print(f"{Path(r['file']).name}: rows={r['rows']} grade={r['quality_grade']} modules={len(r['supported_modules'])}")


if __name__ == "__main__":
    main()
