"""Validated snapshot publication and deterministic replay from immutable raw pages."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from src.quality.analytics import METRIC_VERSION, build_report
from src.quality.connectors import Collector
from src.quality.contracts import GithubIssue, GithubRelease, Product, SteamReview, iso, utc_now
from src.quality.games import Games
from src.quality.store import Store
from src.quality.taxonomy import TAXONOMY_VERSION, find_mentions


def normalize(run_id: str, product: Product, source: str, rows: list, end: datetime):
    key = product.key
    evidence = {}
    releases = {}
    quarantine = []
    duplicates = 0
    excluded_prs = 0
    excluded_releases = 0
    for raw, page, pointer in rows:
        try:
            if source == "steam":
                item = SteamReview.model_validate(raw)
                created = datetime.fromtimestamp(item.timestamp_created, timezone.utc)
                updated = datetime.fromtimestamp(item.timestamp_updated, timezone.utc)
                if (
                    created > end + timedelta(minutes=5)
                    or updated > end + timedelta(minutes=5)
                    or updated < created
                ):
                    raise ValueError("timestamp inconsistent with snapshot")
                row = dict(
                    run_id=run_id,
                    id=f"steam:{key}:{item.recommendationid}",
                    product=key,
                    source=source,
                    remote_id=item.recommendationid,
                    title="Steam公开评论",
                    text=item.review,
                    language=item.language,
                    language_method="Steam平台标签",
                    created_at=iso(created),
                    updated_at=iso(updated),
                    recommended=int(item.voted_up),
                    playtime_minutes=item.author.playtime_forever,
                    playtime_at_review_minutes=item.author.playtime_at_review,
                    helpful_votes=item.votes_up,
                    state=None,
                    closed_at=None,
                    labels_json="[]",
                    source_url=f"https://steamcommunity.com/profiles/{item.author.steamid}/recommended/{product.app_id}/",
                    page_id=page["id"],
                    json_pointer=pointer,
                )
            elif source == "github_issues":
                item = GithubIssue.model_validate(raw)
                if item.pull_request is not None:
                    excluded_prs += 1
                    continue
                expected = f"https://github.com/{product.repo}/issues/".lower()
                if not item.html_url.lower().startswith(expected):
                    raise ValueError("issue does not belong to registered product")
                if (
                    item.created_at > end + timedelta(minutes=5)
                    or item.updated_at < item.created_at
                ):
                    raise ValueError("issue timestamp inconsistent")
                row = dict(
                    run_id=run_id,
                    id=f"github:{key}:{item.id}",
                    product=key,
                    source=source,
                    remote_id=str(item.id),
                    title=item.title,
                    text=(item.body or "")[:100000],
                    language="unknown",
                    language_method="GitHub无语言标签，词项探索不作为语言真值",
                    created_at=iso(item.created_at),
                    updated_at=iso(item.updated_at),
                    recommended=None,
                    playtime_minutes=None,
                    playtime_at_review_minutes=None,
                    helpful_votes=None,
                    state=item.state,
                    closed_at=iso(item.closed_at) if item.closed_at else None,
                    labels_json=json.dumps(
                        [x.get("name", "") for x in item.labels], ensure_ascii=False
                    ),
                    source_url=item.html_url,
                    page_id=page["id"],
                    json_pointer=pointer,
                )
            else:
                item = GithubRelease.model_validate(raw)
                if item.draft or item.prerelease or not item.published_at:
                    excluded_releases += 1
                    continue
                if item.published_at.tzinfo is None or item.published_at > end + timedelta(
                    minutes=5
                ):
                    raise ValueError("release timezone/future timestamp")
                expected = f"https://github.com/{product.repo}/releases/".lower()
                if not item.html_url.lower().startswith(expected):
                    raise ValueError("release does not belong to registered product")
                row = dict(
                    run_id=run_id,
                    id=f"release:{key}:{item.id}",
                    product=key,
                    title=item.name or item.tag_name,
                    tag=item.tag_name,
                    published_at=iso(item.published_at),
                    body=item.body or "",
                    source_url=item.html_url,
                    page_id=page["id"],
                    json_pointer=pointer,
                )
                releases[row["id"]] = row
                continue
            existing = evidence.get(row["id"])
            if existing:
                duplicates += 1
                if existing["updated_at"] > row["updated_at"]:
                    continue
            evidence[row["id"]] = row
        except (ValidationError, ValueError, TypeError, OverflowError) as exc:
            reason = (
                json.dumps(exc.errors(include_input=False), ensure_ascii=False, default=str)
                if isinstance(exc, ValidationError)
                else str(exc)
            )
            quarantine.append(
                dict(
                    run_id=run_id,
                    product=key,
                    source=source,
                    page_id=page["id"],
                    json_pointer=pointer,
                    reason=reason[:5000],
                )
            )
    return (
        list(evidence.values()),
        list(releases.values()),
        quarantine,
        {
            "accepted": len(evidence) + len(releases),
            "quarantined": len(quarantine),
            "deduplicated": duplicates,
            "excluded_prs": excluded_prs,
            "excluded_releases": excluded_releases,
        },
    )


def snapshot_fingerprint(evidence: list[dict], releases: list[dict], config: dict) -> str:
    ignored = {"run_id", "page_id", "json_pointer"}
    normalized = {
        "evidence": [
            {k: v for k, v in row.items() if k not in ignored}
            for row in sorted(evidence, key=lambda x: x["id"])
        ],
        "releases": [
            {k: v for k, v in row.items() if k not in ignored}
            for row in sorted(releases, key=lambda x: x["id"])
        ],
        "window_start": config["window_start"],
        "window_end": config["window_end"],
        "taxonomy_version": TAXONOMY_VERSION,
        "metric_version": METRIC_VERSION,
    }
    return hashlib.sha256(
        json.dumps(normalized, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def publish(
    store: Store,
    run_id: str,
    config: dict,
    source_rows: dict,
    coverage: dict,
    identities: dict,
    expected_fingerprint: str | None = None,
):
    end = datetime.fromisoformat(config["window_end"].replace("Z", "+00:00"))
    evidence, releases, quarantine, mentions = [], [], [], []
    for key in config["products"]:
        product = Product(**config["games"][key])
        for source in ("steam", "github_issues", "github_releases"):
            e, r, q, diagnostics = normalize(run_id, product, source, source_rows[key][source], end)
            coverage[key][source].update(diagnostics)
            evidence.extend(e)
            releases.extend(r)
            quarantine.extend(q)
    for row in evidence:
        text = (
            row["title"] + "\n" + row["text"] if row["source"] == "github_issues" else row["text"]
        )
        for mention in find_mentions(text, row["language"], row["source"]):
            mentions.append(
                dict(
                    run_id=run_id,
                    evidence_id=row["id"],
                    category=mention["category"],
                    cues_json=json.dumps(mention["cues"], ensure_ascii=False),
                )
            )
    store.progress(
        run_id,
        source="analysis",
        records=len(evidence),
        message="契约校验完成；计算统一指标",
    )
    store.publish_rows(run_id, evidence, releases, mentions, quarantine)
    report = build_report(store, run_id, config, coverage, identities)
    fingerprint = snapshot_fingerprint(evidence, releases, config)
    report["fingerprint"] = fingerprint
    report["raw_page_count"] = len(store.pages(run_id))
    if expected_fingerprint is not None and fingerprint != expected_fingerprint:
        raise ValueError("replay fingerprint differs; source or transformation has changed")
    store.complete(run_id, report, fingerprint)
    return report


def not_linked(source: str) -> dict:
    """Coverage of a GitHub source for a game that has no repository linked."""
    return {
        "source": source,
        "pages": 0,
        "raw_rows": 0,
        "complete": True,
        "stop_reason": "not_linked",
        "scope": "未关联 GitHub 仓库",
    }


def sync(store: Store, run_id: str, requested: dict, collector_factory=Collector):
    end = utc_now().replace(microsecond=0)
    try:
        games = Games(store)
        keys = requested["products"] or [g["key"] for g in games.list()]
        if not keys:
            raise ValueError("还没有添加游戏")
        config = {
            **requested,
            "products": keys,
            # Each snapshot keeps the game definitions it was collected with.
            "games": {key: games.get(key).model_dump() for key in keys},
            "window_start": iso(end - timedelta(days=requested["days"])),
            "window_end": iso(end),
            "pipeline_version": "0.2.0",
        }
    except Exception as exc:
        store.fail(run_id, f"{type(exc).__name__}: {exc}")
        raise
    with store.connect() as conn:
        conn.execute("UPDATE runs SET config_json=? WHERE id=?", (json.dumps(config), run_id))
    source_rows, coverage, identities = {}, {}, {}
    collector = collector_factory(store, run_id, progress=lambda **x: store.progress(run_id, **x))
    try:
        start = datetime.fromisoformat(config["window_start"].replace("Z", "+00:00"))
        for key in keys:
            product = Product(**config["games"][key])
            source_rows[key], coverage[key] = {}, {}
            identities[key] = collector.identity(product)
            source_rows[key]["steam"], coverage[key]["steam"] = collector.steam(
                product, start, end, requested["max_reviews"]
            )
            if not product.repo:
                for source in ("github_issues", "github_releases"):
                    source_rows[key][source], coverage[key][source] = [], not_linked(source)
                continue
            source_rows[key]["github_issues"], coverage[key]["github_issues"] = collector.github(
                product, "github_issues", start, requested["max_issue_pages"]
            )
            source_rows[key]["github_releases"], coverage[key]["github_releases"] = (
                collector.github(product, "github_releases", start, 2)
            )
        return publish(store, run_id, config, source_rows, coverage, identities)
    except Exception as exc:
        store.fail(run_id, f"{type(exc).__name__}: {exc}")
        raise
    finally:
        collector.close()


def replay(store: Store, original_id: str, run_id: str | None = None) -> dict:
    original = store.run(original_id)
    if not original or original["status"] != "completed":
        raise ValueError("only a completed source snapshot can be replayed")
    config = {**original["config"], "replayed_from": original_id}
    report = original["report"]
    rules = {"taxonomy_version": TAXONOMY_VERSION, "metric_version": METRIC_VERSION}
    previous_rules = {k: report.get(k) for k in rules}
    # Same rules: the replay must reproduce the snapshot exactly. Changed rules: it recomputes
    # the same verified raw pages under the new rules, so the fingerprint is expected to change.
    expected = original["fingerprint"] if previous_rules == rules else None
    if expected is None:
        config["recomputed_rules"] = {"from": previous_rules, "to": rules}
    run_id = run_id or store.new_run(config)
    source_rows = {
        k: {s: [] for s in ("steam", "github_issues", "github_releases")}
        for k in config["products"]
    }
    coverage = {p["key"]: p["coverage"] for p in original["report"]["products"]}
    identities = {p["key"]: p["identity"] for p in original["report"]["products"]}
    try:
        for original_page in store.pages(original_id):
            if original_page["http_status"] not in (200, 304):
                continue
            content = store.read_raw(original_page["path"], original_page["sha256"])
            metadata = {
                **json.loads(original_page["metadata_json"]),
                "replayed_from": original_page["id"],
                "original_fetched_at": json.loads(original_page["metadata_json"]).get(
                    "original_fetched_at", original_page["fetched_at"]
                ),
                "transport": "offline_replay",
                "original_http_status": original_page["http_status"],
            }
            page = store.save_page(
                run_id,
                original_page["product"],
                original_page["source"],
                original_page["sequence"],
                original_page["url"],
                content,
                original_page["http_status"],
                json.loads(original_page["headers_json"]),
                metadata,
            )
            payload = json.loads(content)
            source, key = page["source"], page["product"]
            if source == "steam":
                steam_body = payload["response"]
                if (
                    "reviews" not in steam_body
                    and steam_body.get("query_summary", {}).get("num_reviews") != 0
                ):
                    raise ValueError("replay Steam page lacks a valid reviews array")
                source_rows[key][source].extend(
                    (item, page, f"/response/reviews/{i}")
                    for i, item in enumerate(steam_body.get("reviews", []))
                )
            elif source in ("github_issues", "github_releases"):
                if isinstance(payload, dict) and "items" in payload:
                    source_rows[key][source].extend(
                        (item, page, f"/items/{i}") for i, item in enumerate(payload["items"])
                    )
                    continue
                source_rows[key][source].extend(
                    (item, page, f"/{i}") for i, item in enumerate(payload)
                )
        return publish(
            store,
            run_id,
            config,
            source_rows,
            coverage,
            identities,
            expected_fingerprint=expected,
        )
    except Exception as exc:
        store.fail(run_id, f"Replay failed: {exc}")
        raise
