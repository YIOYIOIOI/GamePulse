"""Single metric definitions for CLI, API and UI. Observation is not causation."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import numpy as np
from scipy.stats import fisher_exact
from statsmodels.stats.proportion import confint_proportions_2indep, proportion_confint

from src.quality.contracts import Product, iso
from src.quality.store import Store
from src.quality.taxonomy import CATEGORIES, SUPPORTED_LANGUAGES, TAXONOMY_VERSION

METRIC_VERSION = "recommendation-quality-v2"
STAT_SEED = 20261013
STOP_REASONS = {
    "page_cap": "达到单次采集的分页上限",
    "record_cap": "达到单次采集的评论上限",
    "request_cap": "达到单次采集的请求上限",
    "count_mismatch": "采集数量与平台报告不一致",
    "search_1000_result_limit": "GitHub 搜索最多返回 1,000 条",
    "repeated_records_without_progress": "分页返回重复记录",
    "repeated_or_missing_cursor": "分页游标重复或缺失",
    "repeated_next_link": "分页链接重复",
}


def stop_reason_text(source_coverage: dict) -> str:
    return STOP_REASONS.get(source_coverage["stop_reason"], source_coverage["stop_reason"])


def rate_summary(negative: int, total: int) -> dict:
    if total == 0:
        return {"n": 0, "negative": 0, "rate": None, "ci_low": None, "ci_high": None}
    low, high = proportion_confint(negative, total, alpha=0.05, method="wilson")
    return {
        "n": total,
        "negative": negative,
        "rate": negative / total,
        "ci_low": float(low),
        "ci_high": float(high),
    }


def compare_rates(before: dict, after: dict, minimum=30) -> dict:
    result = {
        "before": before,
        "after": after,
        "delta": None,
        "ci_low": None,
        "ci_high": None,
        "p_value": None,
        "status": "insufficient_sample",
        "min_per_period": minimum,
    }
    if before["n"] and after["n"]:
        result["delta"] = after["rate"] - before["rate"]
    if min(before["n"], after["n"]) < minimum:
        return result
    low, high = confint_proportions_2indep(
        after["negative"],
        after["n"],
        before["negative"],
        before["n"],
        method="newcomb",
        compare="diff",
        alpha=0.05,
    )
    p = fisher_exact(
        [
            [after["negative"], after["n"] - after["negative"]],
            [before["negative"], before["n"] - before["negative"]],
        ]
    ).pvalue
    result.update(
        status="descriptive_comparison", ci_low=float(low), ci_high=float(high), p_value=float(p)
    )
    return result


def language_standardized(before: list[dict], after: list[dict], minimum=10) -> dict:
    left = {r["language"]: r for r in before}
    right = {r["language"]: r for r in after}
    common = [
        k for k in sorted(left.keys() & right.keys()) if min(left[k]["n"], right[k]["n"]) >= minimum
    ]
    if not common:
        return {
            "status": "insufficient_common_languages",
            "delta": None,
            "languages": [],
            "ci_low": None,
            "ci_high": None,
            "included_before": 0,
            "included_after": 0,
        }
    weights = np.array([left[k]["n"] + right[k]["n"] for k in common], dtype=float)
    weights /= weights.sum()
    p_before = np.array([left[k]["negative"] / left[k]["n"] for k in common])
    p_after = np.array([right[k]["negative"] / right[k]["n"] for k in common])
    rng = np.random.default_rng(STAT_SEED)
    draws = np.zeros(2000)
    for index, lang in enumerate(common):
        b, a = left[lang], right[lang]
        draws += weights[index] * (
            rng.binomial(a["n"], p_after[index], 2000) / a["n"]
            - rng.binomial(b["n"], p_before[index], 2000) / b["n"]
        )
    low, high = np.quantile(draws, [0.025, 0.975])
    return {
        "status": "common_language_standardization",
        "delta": float(weights @ (p_after - p_before)),
        "ci_low": float(low),
        "ci_high": float(high),
        "languages": [
            {
                "language": k,
                "weight": float(weights[i]),
                "before_n": left[k]["n"],
                "after_n": right[k]["n"],
            }
            for i, k in enumerate(common)
        ],
        "included_before": sum(left[k]["n"] for k in common),
        "included_after": sum(right[k]["n"] for k in common),
        "assumption": "按共同语言、两期合并样本权重标准化；二项抽样区间假设评论独立，未消除时间相关和评论自选择偏差",
    }


def bh_adjust(pvalues: list[float]) -> list[float]:
    if not pvalues:
        return []
    order = np.argsort(pvalues)
    values = np.array(pvalues)[order]
    adjusted = np.minimum.accumulate((values * len(values) / np.arange(1, len(values) + 1))[::-1])[
        ::-1
    ]
    out = np.empty(len(values))
    out[order] = np.minimum(adjusted, 1)
    return out.tolist()


def period_counts(store: Store, run_id: str, product: str, start: datetime, end: datetime) -> dict:
    row = store.query(
        "SELECT COUNT(*) AS n,COALESCE(SUM(recommended=0),0) AS negative "
        "FROM evidence WHERE run_id=? AND product=? AND source='steam' "
        "AND created_at>=? AND created_at<?",
        (run_id, product, iso(start), iso(end)),
    )[0]
    return rate_summary(row["negative"], row["n"])


def period_languages(store: Store, run_id: str, product: str, start: datetime, end: datetime):
    return store.query(
        "SELECT language,COUNT(*) AS n,SUM(recommended=0) AS negative FROM evidence "
        "WHERE run_id=? AND product=? AND source='steam' AND created_at>=? AND created_at<? "
        "GROUP BY language",
        (run_id, product, iso(start), iso(end)),
    )


def day_block_sensitivity(
    store: Store, run_id: str, product: str, start: datetime, boundary: datetime, end: datetime
) -> dict:
    """Circular 7-day block resampling: a sensitivity check, not causal identification."""
    arrays = []
    for left, right in ((start, boundary), (boundary, end)):
        rows = store.query(
            "SELECT substr(created_at,1,10) AS day,COUNT(*) AS n,SUM(recommended=0) AS negative "
            "FROM evidence WHERE run_id=? AND product=? AND source='steam' "
            "AND created_at>=? AND created_at<? GROUP BY day",
            (run_id, product, iso(left), iso(right)),
        )
        values = {r["day"]: (r["negative"], r["n"]) for r in rows}
        days = (right.date() - left.date()).days + 1
        arrays.append(
            np.array(
                [
                    values.get((left.date() + timedelta(days=i)).isoformat(), (0, 0))
                    for i in range(days)
                ],
                dtype=float,
            )
        )
    result = {
        "method": "UTC日计数的7日循环块重抽样",
        "replicates": 2000,
        "block_days": 7,
        "ci_low": None,
        "ci_high": None,
        "valid_replicates": 0,
        "status": "insufficient_sample",
        "seed": STAT_SEED,
    }
    if any(a[:, 1].sum() < 30 or len(a) < 14 for a in arrays):
        return result
    rng = np.random.default_rng(STAT_SEED)
    rates = []
    for array in arrays:
        n = len(array)
        anchors = rng.integers(0, n, size=(2000, (n + 6) // 7))
        indices = ((anchors[:, :, None] + np.arange(7)) % n).reshape(2000, -1)[:, :n]
        totals = array[indices].sum(axis=1)
        rate = np.divide(
            totals[:, 0], totals[:, 1], out=np.full(2000, np.nan), where=totals[:, 1] > 0
        )
        rates.append(rate)
    differences = rates[1] - rates[0]
    valid = differences[np.isfinite(differences)]
    result["valid_replicates"] = len(valid)
    if len(valid) >= 1600:
        low, high = np.quantile(valid, [0.025, 0.975])
        result.update(status="sensitivity_interval", ci_low=float(low), ci_high=float(high))
    return result


def build_report(
    store: Store,
    run_id: str,
    config: dict,
    coverage: dict,
    identities: dict,
) -> dict:
    end = datetime.fromisoformat(config["window_end"].replace("Z", "+00:00"))
    start = datetime.fromisoformat(config["window_start"].replace("Z", "+00:00"))
    products = []
    for key in config["products"]:
        product = Product(**config["games"][key])
        steam_coverage = coverage[key]["steam"]
        quarantined = store.query(
            "SELECT source,COUNT(*) AS n FROM quarantine WHERE run_id=? AND product=? GROUP BY source",
            (run_id, key),
        )
        quarantine_count = sum(r["n"] for r in quarantined)
        reliable = steam_coverage["complete"] and not any(
            r["source"] == "steam" for r in quarantined
        )
        total = period_counts(store, run_id, key, start, end + timedelta(seconds=1))
        languages = period_languages(store, run_id, key, start, end + timedelta(seconds=1))
        for row in languages:
            row.update(rate_summary(row["negative"], row["n"]))
        languages.sort(key=lambda r: -r["n"])
        weekly_rows = store.query(
            "SELECT date(created_at,'-6 days','weekday 1') AS week,COUNT(*) AS n,"
            "SUM(recommended=0) AS negative FROM evidence WHERE run_id=? AND product=? "
            "AND source='steam' GROUP BY week ORDER BY week",
            (run_id, key),
        )
        weekly = [{"week": r["week"], **rate_summary(r["negative"], r["n"])} for r in weekly_rows]
        daily_rows = store.query(
            "SELECT substr(created_at,1,10) AS day,COUNT(*) AS n,SUM(recommended=0) AS negative "
            "FROM evidence WHERE run_id=? AND product=? AND source='steam' GROUP BY day ORDER BY day",
            (run_id, key),
        )
        by_day = {r["day"]: r for r in daily_rows}
        daily = []
        day = start.date()
        while day <= end.date():
            date = day.isoformat()
            row = by_day.get(date)
            if row:
                daily.append(
                    {"day": date, **rate_summary(row["negative"], row["n"]), "observed": True}
                )
            else:
                daily.append(
                    {
                        "day": date,
                        "n": 0 if reliable else None,
                        "negative": 0 if reliable else None,
                        "rate": None,
                        "ci_low": None,
                        "ci_high": None,
                        "observed": reliable,
                    }
                )
            day += timedelta(days=1)
        recent_start = end - timedelta(days=30)
        baseline_start = end - timedelta(days=60)
        recent = period_counts(store, run_id, key, recent_start, end)
        baseline = period_counts(store, run_id, key, baseline_start, recent_start)
        monitor = compare_rates(baseline, recent, minimum=50)
        monitor["language_adjusted"] = language_standardized(
            period_languages(store, run_id, key, baseline_start, recent_start),
            period_languages(store, run_id, key, recent_start, end),
        )
        monitor["window"] = {
            "before_start": iso(baseline_start),
            "boundary": iso(recent_start),
            "end": iso(end),
        }
        monitor["day_block"] = day_block_sensitivity(
            store, run_id, key, baseline_start, recent_start, end
        )
        if not reliable or baseline_start < start:
            monitor["status"] = "incomplete_coverage"
            monitor["ci_low"] = monitor["ci_high"] = monitor["p_value"] = None
            monitor["day_block"].update(status="incomplete_coverage", ci_low=None, ci_high=None)
        adjusted = monitor["language_adjusted"]
        adjusted_coverage = (
            adjusted["included_before"] >= baseline["n"] * 0.8
            and adjusted["included_after"] >= recent["n"] * 0.8
        )
        monitor["alert"] = (
            monitor["status"] == "descriptive_comparison"
            and monitor["ci_low"] > 0
            and monitor["delta"] >= 0.05
            and adjusted_coverage
            and adjusted["ci_low"] is not None
            and adjusted["ci_low"] > 0
            and monitor["day_block"]["ci_low"] is not None
            and monitor["day_block"]["ci_low"] > 0
        )
        monitor["alert_policy"] = (
            "两期各≥50条、覆盖完整，差值≥5pp且Newcombe下界>0；共同语言各覆盖≥80%，标准化与7日块敏感性区间下界均>0；仅触发排查"
        )
        issues = store.query(
            "SELECT state,COUNT(*) AS n FROM evidence WHERE run_id=? AND product=? "
            "AND source='github_issues' GROUP BY state",
            (run_id, key),
        )
        categories = []
        recent_mentions = {
            (r["category"], r["period"]): r
            for r in store.query(
                "SELECT m.category,CASE WHEN e.created_at>=? THEN 'recent' ELSE 'previous' END AS period,"
                "COUNT(*) AS n,COALESCE(SUM(e.recommended=0),0) AS negative "
                "FROM mentions m JOIN evidence e ON e.run_id=m.run_id AND e.id=m.evidence_id "
                "WHERE m.run_id=? AND e.product=? AND e.source='steam' AND e.created_at>=? AND e.created_at<? "
                "GROUP BY m.category,period",
                (iso(recent_start), run_id, key, iso(baseline_start), iso(end)),
            )
        }
        for category, label in CATEGORIES.items():
            counts = store.query(
                "SELECT e.source,COUNT(*) AS n,COALESCE(SUM(e.source='steam' AND e.recommended=0),0) AS negative,"
                "COALESCE(SUM(e.source='github_issues' AND e.state='open'),0) AS open_issues "
                "FROM mentions m JOIN evidence e ON e.run_id=m.run_id AND e.id=m.evidence_id "
                "WHERE m.run_id=? AND e.product=? AND m.category=? GROUP BY e.source",
                (run_id, key, category),
            )
            cnt = {r["source"]: r for r in counts}
            review_n = cnt.get("steam", {}).get("n", 0)
            negative = cnt.get("steam", {}).get("negative", 0)
            issue_n = cnt.get("github_issues", {}).get("n", 0)
            examples = store.query(
                "SELECT e.id,e.source,e.title,e.text,e.source_url,e.recommended,e.language,e.helpful_votes,"
                "m.cues_json FROM mentions m JOIN evidence e ON e.run_id=m.run_id AND e.id=m.evidence_id "
                "WHERE m.run_id=? AND e.product=? AND m.category=? "
                "ORDER BY (e.source='steam' AND e.recommended=0) DESC,e.helpful_votes DESC,e.created_at DESC LIMIT 4",
                (run_id, key, category),
            )
            for example in examples:
                example["text"] = example["text"][:420]
                example["cues"] = json.loads(example.pop("cues_json"))
            categories.append(
                {
                    "key": category,
                    "label": label,
                    "review_mentions": review_n,
                    "negative_reviews": negative,
                    "review_denominator": total["n"],
                    "github_mentions": issue_n,
                    "open_issues": cnt.get("github_issues", {}).get("open_issues", 0),
                    # Steam review mentions in the monitor's two 30-day periods.
                    "trend": {
                        period: {
                            "mentions": recent_mentions.get((category, period), {}).get("n", 0),
                            "negative": recent_mentions.get((category, period), {}).get(
                                "negative", 0
                            ),
                            "reviews": (recent if period == "recent" else baseline)["n"],
                        }
                        for period in ("previous", "recent")
                    },
                    "examples": examples,
                    "classification": "词项提及筛选，需复核原文；不能等同于缺陷确认",
                }
            )
        categories.sort(key=lambda r: (-r["negative_reviews"], -r["open_issues"]))
        cohorts = store.query(
            "SELECT CASE WHEN playtime_at_review_minutes IS NULL THEN 'unknown' "
            "WHEN playtime_at_review_minutes<=120 THEN '0–2h' "
            "WHEN playtime_at_review_minutes<=1200 THEN '2–20h' ELSE '20h+' END AS cohort,"
            "COUNT(*) AS n,SUM(recommended=0) AS negative FROM evidence "
            "WHERE run_id=? AND product=? AND source='steam' GROUP BY cohort",
            (run_id, key),
        )
        for cohort in cohorts:
            cohort.update(rate_summary(cohort["negative"], cohort["n"]))
        releases = store.query(
            "SELECT * FROM releases WHERE run_id=? AND product=? ORDER BY published_at DESC",
            (run_id, key),
        )
        studies = []
        # Only releases whose 14-day after-window reaches into the collected reviews.
        in_window = [
            r
            for r in releases
            if datetime.fromisoformat(r["published_at"].replace("Z", "+00:00")) + timedelta(days=14)
            > start
        ]
        for release in in_window:
            boundary = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00"))
            before_start, after_end = boundary - timedelta(days=14), boundary + timedelta(days=14)
            before = period_counts(store, run_id, key, before_start, boundary)
            after = period_counts(store, run_id, key, boundary, min(after_end, end))
            study = compare_rates(before, after)
            study.update(
                release_id=release["id"],
                title=release["title"],
                tag=release["tag"],
                source_url=release["source_url"],
                published_at=release["published_at"],
                window_before_start=iso(before_start),
                window_after_end=iso(after_end),
                event_definition="GitHub公开版本发布时间，未验证Steam用户实际版本",
            )
            if before_start < start or after_end > end or not reliable:
                study["status"] = "incomplete_window"
                study["ci_low"] = study["ci_high"] = study["p_value"] = None
            study["language_adjusted"] = language_standardized(
                period_languages(store, run_id, key, before_start, boundary),
                period_languages(store, run_id, key, boundary, min(after_end, end)),
            )
            study["day_block"] = day_block_sensitivity(
                store, run_id, key, before_start, boundary, min(after_end, end)
            )
            if study["status"] == "incomplete_window":
                study["day_block"].update(status="incomplete_window", ci_low=None, ci_high=None)
            study["other_releases"] = [
                {"tag": r["tag"], "published_at": r["published_at"]}
                for r in releases
                if r["id"] != release["id"]
                and iso(before_start) <= r["published_at"] < iso(after_end)
            ]
            study["causal_claim_allowed"] = False
            studies.append(study)
        eligible = [s for s in studies if s["p_value"] is not None]
        for study, q in zip(eligible, bh_adjust([s["p_value"] for s in eligible])):
            study["q_value"] = q
        rules_covered = sum(r["n"] for r in languages if r["language"] in SUPPORTED_LANGUAGES)
        warnings = []
        if not steam_coverage["complete"]:
            warnings.append(
                f"Steam 评论未收齐（{stop_reason_text(steam_coverage)}），趋势告警和版本对比区间已关闭。"
            )
        if quarantine_count:
            warnings.append(f"{quarantine_count} 条记录未通过字段校验，已隔离并保留原始来源。")
        if not coverage[key]["github_issues"]["complete"]:
            warnings.append(
                f"GitHub issue 只采集了时间窗内的一部分（{stop_reason_text(coverage[key]['github_issues'])}），"
                "issue 数量偏少。"
            )
        if not coverage[key]["github_releases"]["complete"]:
            warnings.append("GitHub Release 列表不完整，版本对比中的「同期其他版本」可能有遗漏。")
        if total["n"] < 300:
            warnings.append("评论不足 300 条，分语言、分问题的比例波动较大，请结合原文判断。")
        products.append(
            {
                "key": key,
                "name": product.name,
                "app_id": product.app_id,
                "repo": product.repo,
                "identity": identities[key],
                "recommendation": total,
                "languages": languages,
                "daily": daily,
                "weekly": weekly,
                "monitor": monitor,
                "categories": categories,
                "cohorts": cohorts,
                "issues": {r["state"]: r["n"] for r in issues},
                "release_studies": studies,
                "releases_outside_window": len(releases) - len(in_window),
                "coverage": coverage[key],
                "quality": {
                    "trend_allowed": reliable,
                    "quarantined": quarantine_count,
                    "rules_language_covered": rules_covered,
                    "rule_denominator": total["n"],
                    "warnings": warnings,
                },
            }
        )
    return {
        "run_id": run_id,
        "as_of": config["window_end"],
        "window_start": config["window_start"],
        "metric_version": METRIC_VERSION,
        "taxonomy_version": TAXONOMY_VERSION,
        "seed": STAT_SEED,
        "products": products,
        "method": {
            "recommendation": "Steam voted_up；不推荐数/所采公开评论数，短评论保留；不是文本情绪或全体用户满意率",
            "interval": "推荐比例：Wilson 95%；两期差：Newcombe 95%；Fisher检验仅作观察性诊断，版本事件内BH校正",
            "releases": "版本前后各14天；样本各≥30且窗口覆盖完整才计算推断区间；其他版本和渠道差异单列",
            "cohorts": "评论发表时的游戏时长分档；缺失保持unknown；不是付费、留存或生命周期分层",
            "mentions": "可解释词项提及，英/中/俄评论支持；GitHub使用词项筛选；原文必须人工复核",
            "boundaries": [
                "写评论的玩家是主动发声的一部分人；置信区间只反映抽样误差，不能消除这种偏差。",
                "GitHub issue 主要来自开发者和核心玩家，与 Steam 评论是不同人群，两者的数量不合并计算。",
                "GitHub 发布时间不等于玩家在 Steam 上收到更新的时间；没有对照组，版本前后的变化不能当作版本造成的效果。",
                "问题分类基于可解释的关键词匹配，没有经过人工抽检验收，需结合原文判断。",
            ],
        },
    }
