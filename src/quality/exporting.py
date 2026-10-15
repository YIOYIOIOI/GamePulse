"""Durable, source-linked CSV outputs shared by CLI and HTTP exports."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path


def csv_bytes(rows: list[dict], empty_fields: list[str] | None = None) -> bytes:
    fields = list(rows[0]) if rows else empty_fields or ["id"]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for original in rows:
        row = dict(original)
        for key, value in row.items():
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                # Protect spreadsheet opening; canonical text stays untouched in SQLite/raw JSON.
                row[key] = "'" + value
        writer.writerow(row)
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def evidence_rows(store, run_id: str, product: str | None = None) -> list[dict]:
    return store.query(
        "SELECT id,product,source,remote_id,created_at,updated_at,language,language_method,"
        "recommended,playtime_minutes,playtime_at_review_minutes,helpful_votes,state,title,text,"
        "source_url,page_id,json_pointer FROM evidence WHERE run_id=?"
        + (" AND product=?" if product else "")
        + " ORDER BY product,source,created_at,id",
        (run_id, product) if product else (run_id,),
    )


def write_outputs(store, report: dict, output: Path | None = None) -> Path:
    target = output or store.root / "reports" / report["run_id"]
    target.mkdir(parents=True, exist_ok=True)
    (target / "evidence.csv").write_bytes(csv_bytes(evidence_rows(store, report["run_id"])))
    marts, studies = [], []
    for product in report["products"]:
        collections = [
            ("window_total", [{"bucket": "all", **product["recommendation"]}]),
            ("language", [{"bucket": r["language"], **r} for r in product["languages"]]),
            ("weekly", [{"bucket": r["week"], **r} for r in product["weekly"]]),
            ("review_playtime", [{"bucket": r["cohort"], **r} for r in product["cohorts"]]),
        ]
        for kind, rows in collections:
            for row in rows:
                marts.append(
                    {
                        "product": product["key"],
                        "kind": kind,
                        "bucket": row["bucket"],
                        "window_start": report["window_start"],
                        "as_of": report["as_of"],
                        "n": row["n"],
                        "not_recommended": row["negative"],
                        "rate": row["rate"],
                        "ci95_low": row["ci_low"],
                        "ci95_high": row["ci_high"],
                        "metric_version": report["metric_version"],
                    }
                )
        for study in product["release_studies"]:
            studies.append(
                {
                    "product": product["key"],
                    "tag": study["tag"],
                    "github_published_at": study["published_at"],
                    "source_url": study["source_url"],
                    "status": study["status"],
                    "before_n": study["before"]["n"],
                    "after_n": study["after"]["n"],
                    "before_rate": study["before"]["rate"],
                    "after_rate": study["after"]["rate"],
                    "delta": study["delta"],
                    "newcombe_ci95_low": study["ci_low"],
                    "newcombe_ci95_high": study["ci_high"],
                    "day_block_ci95_low": study["day_block"]["ci_low"],
                    "day_block_ci95_high": study["day_block"]["ci_high"],
                    "fisher_p": study["p_value"],
                    "bh_q": study.get("q_value"),
                    "known_other_releases": ";".join(r["tag"] for r in study["other_releases"]),
                    "causal_claim_allowed": False,
                }
            )
    (target / "metric-marts.csv").write_bytes(csv_bytes(marts))
    (target / "release-studies.csv").write_bytes(csv_bytes(studies))
    pages = store.pages(report["run_id"])
    manifest = {
        "run_id": report["run_id"],
        "dataset_fingerprint": report["fingerprint"],
        "as_of": report["as_of"],
        "window_start": report["window_start"],
        "metric_version": report["metric_version"],
        "taxonomy_version": report["taxonomy_version"],
        "pages": [
            {
                key: p[key]
                for key in ("id", "product", "source", "url", "fetched_at", "sha256", "path")
            }
            for p in pages
        ],
        "coverage": {p["key"]: p["coverage"] for p in report["products"]},
        "csv_note": "字符串以=,+,-,@开头时添加单引号防公式执行；原始文本以raw JSON/SQLite为准。",
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target
