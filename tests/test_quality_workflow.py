"""Business invariants and failure injection; source fixtures are actual API captures.

Mutated fields below are adversarial test input, never demonstration/production data.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.quality.agent import command_args
from src.quality.agent_contracts import AgentAnswer, AgentRequest, ToolCall
from src.quality.agent_tools import build_packet, execute_tool, packet_hash, verify_answer
from src.quality.analytics import bh_adjust, compare_rates, language_standardized, rate_summary
from src.quality.api import create_app
from src.quality.connectors import Collector, SourceError
from src.quality.contracts import Product, SteamReview
from src.quality.pipeline import normalize, publish, replay
from src.quality.store import ConflictError, Store
from src.quality.taxonomy import find_mentions, mask_issue_template

FIXTURE_DIR = Path(__file__).parent / "fixtures"
CAPTURE = json.loads((FIXTURE_DIR / "public-source-capture.json").read_text(encoding="utf-8"))
WINDOW = json.loads((FIXTURE_DIR / "complete-steam-window.json").read_text(encoding="utf-8"))
END = datetime.fromtimestamp(WINDOW["input"]["date_range_end"], timezone.utc)
START = datetime.fromtimestamp(WINDOW["input"]["date_range_start"], timezone.utc)
# The captures above come from this game's public Steam reviews and GitHub repository.
GAME = Product(key="mindustry", name="Mindustry", app_id=1127400, repo="Anuken/Mindustry")


def save_page(store, run_id, source, payload, sequence=1):
    return store.save_page(
        run_id,
        "mindustry",
        source,
        sequence,
        "https://api.steampowered.com/captured"
        if source == "steam"
        else "https://api.github.com/captured",
        json.dumps(payload, ensure_ascii=False).encode(),
        200,
        {},
        {},
    )


@pytest.fixture
def populated(tmp_path):
    store = Store(tmp_path / "quality")
    config = {
        "products": ["mindustry"],
        "days": 3,
        "games": {GAME.key: GAME.model_dump()},
        "max_reviews": 6000,
        "max_issue_pages": 4,
        "window_start": START.isoformat().replace("+00:00", "Z"),
        "window_end": END.isoformat().replace("+00:00", "Z"),
    }
    run_id = store.new_run(config)
    first = save_page(store, run_id, "steam", WINDOW["first"])
    save_page(store, run_id, "steam", WINDOW["tail"], 2)
    issues = save_page(store, run_id, "github_issues", CAPTURE["issues"])
    releases = save_page(store, run_id, "github_releases", CAPTURE["releases"])
    sources = {
        "mindustry": {
            "steam": [
                (row, first, f"/response/reviews/{i}")
                for i, row in enumerate(WINDOW["first"]["response"]["reviews"])
            ],
            "github_issues": [(row, issues, f"/{i}") for i, row in enumerate(CAPTURE["issues"])],
            "github_releases": [
                (row, releases, f"/{i}") for i, row in enumerate(CAPTURE["releases"])
            ],
        }
    }
    # Test-only metadata describes this small captured window, not a business production snapshot.
    coverage = {
        "mindustry": {
            s: {
                "source": s,
                "pages": 2 if s == "steam" else 1,
                "raw_rows": len(sources["mindustry"][s]),
                "complete": True,
                "stop_reason": "test_capture_end",
                "scope": "真实API小样本，用于离线故障/契约验收",
                "reported_matching": WINDOW["first"]["response"]["total_matching"],
            }
            for s in sources["mindustry"]
        }
    }
    identity = {
        "mindustry": {
            "store_url": "https://store.steampowered.com/app/1127400/",
            "official_identity_url": "https://mindustrygame.github.io/",
            "developers": ["AnukenDev"],
        }
    }
    publish(store, run_id, config, sources, coverage, identity)
    return store, run_id


def test_strict_boolean_cannot_turn_false_string_into_true():
    row = copy.deepcopy(CAPTURE["reviews"][0])
    row["voted_up"] = "false"
    with pytest.raises(ValidationError):
        SteamReview.model_validate(row)


def test_unknown_playtime_is_not_zero_or_a_new_player():
    row = copy.deepcopy(CAPTURE["reviews"][0])
    row["author"].pop("playtime_at_review", None)
    page = {"id": "test-source-page"}
    evidence, _, quarantine, _ = normalize(
        "unit", GAME, "steam", [(row, page, "/response/reviews/0")], END
    )
    assert not quarantine
    assert evidence[0]["playtime_at_review_minutes"] is None
    assert evidence[0]["playtime_minutes"] == row["author"]["playtime_forever"]


def test_missing_recommendation_is_quarantined_with_source_pointer():
    row = copy.deepcopy(CAPTURE["reviews"][0])
    row.pop("voted_up")
    evidence, _, quarantine, _ = normalize(
        "unit", GAME, "steam", [(row, {"id": "raw-1"}, "/response/reviews/0")], END
    )
    assert not evidence
    assert quarantine[0]["page_id"] == "raw-1"
    assert quarantine[0]["json_pointer"] == "/response/reviews/0"
    assert "voted_up" in quarantine[0]["reason"]


def test_future_timestamp_and_changed_units_are_rejected():
    row = copy.deepcopy(CAPTURE["reviews"][0])
    row["timestamp_created"] = int((END + timedelta(days=1)).timestamp())
    row["timestamp_updated"] = row["timestamp_created"]
    evidence, _, quarantine, _ = normalize(
        "unit", GAME, "steam", [(row, {"id": "raw"}, "/0")], END
    )
    assert not evidence and quarantine
    row = copy.deepcopy(CAPTURE["reviews"][0])
    row["author"]["playtime_forever"] = 1.5
    with pytest.raises(ValidationError):
        SteamReview.model_validate(row)


def test_duplicate_review_id_cannot_inflate_the_denominator():
    row = CAPTURE["reviews"][0]
    rows = [(row, {"id": "raw"}, "/0"), (row, {"id": "raw"}, "/1")]
    evidence, _, _, diag = normalize("unit", GAME, "steam", rows, END)
    assert len(evidence) == 1
    assert diag["deduplicated"] == 1


def test_github_pull_requests_never_become_defect_tickets():
    assert CAPTURE["pull_request"]
    e, _, _, diag = normalize(
        "unit",
        GAME,
        "github_issues",
        [(CAPTURE["pull_request"], {"id": "raw"}, "/0")],
        END + timedelta(hours=1),
    )
    assert not e and diag["excluded_prs"] == 1


def test_real_terminal_page_can_omit_reviews_array(tmp_path):
    calls = []

    def transport(request):
        inputs = json.loads(request.url.params["input_json"])
        calls.append(inputs)
        body = WINDOW["first"] if inputs["cursor"] == "*" else WINDOW["tail"]
        return httpx.Response(200, json=body)

    store = Store(tmp_path)
    run_id = store.new_run({})
    client = httpx.Client(transport=httpx.MockTransport(transport))
    collector = Collector(store, run_id, client=client, delay=0)
    rows, coverage = collector.steam(GAME, START, END, 6000)
    assert coverage["complete"] and coverage["count_matches"]
    assert len(rows) == WINDOW["first"]["response"]["total_matching"]
    assert len(calls) == 2 and calls[0]["filter"] == 1 and calls[0]["purchase_type"] == 1


def test_empty_invalid_payload_is_not_silently_a_zero_population(tmp_path):
    store = Store(tmp_path)
    collector = Collector(
        store,
        store.new_run({}),
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"response": {}}))
        ),
        delay=0,
    )
    with pytest.raises(SourceError, match="schema changed"):
        collector.steam(GAME, START, END, 6000)


def test_silent_truncation_disables_complete_coverage(tmp_path):
    first = copy.deepcopy(WINDOW["first"])
    first["response"]["reviews"].pop()

    def handler(request):
        body = (
            first
            if json.loads(request.url.params["input_json"])["cursor"] == "*"
            else WINDOW["tail"]
        )
        return httpx.Response(200, json=body)

    store = Store(tmp_path)
    collector = Collector(
        store,
        store.new_run({}),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        delay=0,
    )
    _, coverage = collector.steam(GAME, START, END, 6000)
    assert not coverage["complete"] and coverage["stop_reason"] == "count_mismatch"


def test_repeated_cursor_cannot_fake_completion(tmp_path):
    first = copy.deepcopy(WINDOW["first"])
    first["response"]["cursor"] = "*"
    store = Store(tmp_path)
    collector = Collector(
        store,
        store.new_run({}),
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=first))
        ),
        delay=0,
    )
    _, coverage = collector.steam(GAME, START, END, 6000)
    assert not coverage["complete"] and coverage["stop_reason"] == "repeated_or_missing_cursor"


def test_wilson_interval_does_not_hide_uncertainty_with_zero_negative():
    small = rate_summary(0, 5)
    assert small["rate"] == 0
    assert small["ci_high"] > 0.4
    assert rate_summary(0, 0)["rate"] is None


def test_comparison_with_insufficient_sample_has_no_significance_claim():
    result = compare_rates(rate_summary(0, 5), rate_summary(5, 5))
    assert result["delta"] == 1
    assert result["p_value"] is None and result["ci_low"] is None


def test_language_composition_change_is_not_a_within_language_effect():
    before = [
        {"language": "english", "n": 1000, "negative": 100},
        {"language": "russian", "n": 100, "negative": 90},
    ]
    after = [
        {"language": "english", "n": 100, "negative": 10},
        {"language": "russian", "n": 1000, "negative": 900},
    ]
    result = language_standardized(before, after)
    assert result["delta"] == pytest.approx(0)
    assert result["ci_low"] < 0 < result["ci_high"]


def test_multiple_testing_adjustment_keeps_original_event_order():
    assert bh_adjust([0.03, 0.001, 0.02]) == pytest.approx([0.03, 0.003, 0.03])


def test_offline_replay_preserves_source_fingerprint_and_counts(populated):
    store, original = populated
    previous = store.run(original)
    report = replay(store, original)
    assert report["fingerprint"] == previous["fingerprint"]
    assert (
        report["products"][0]["recommendation"]
        == previous["report"]["products"][0]["recommendation"]
    )
    assert report["products"][0]["quality"]["trend_allowed"]
    assert not report["products"][0]["monitor"]["alert"]  # captured window is only three days


def test_tampered_raw_page_fails_and_keeps_previous_snapshot(populated):
    store, original = populated
    page = next(p for p in store.pages(original) if p["source"] == "steam")
    (store.root / page["path"]).write_bytes(b"{}")
    with pytest.raises(ValueError, match="SHA-256"):
        replay(store, original)
    assert store.latest()["id"] == original
    assert store.list_runs()[0]["status"] == "failed"


def test_channels_are_not_merged_and_short_comments_are_not_discarded(populated):
    store, original = populated
    p = store.run(original)["report"]["products"][0]
    assert p["recommendation"]["n"] == len(WINDOW["first"]["response"]["reviews"])
    assert p["recommendation"]["n"] != len(WINDOW["first"]["response"]["reviews"]) + len(
        CAPTURE["issues"]
    )
    assert sum(language["n"] for language in p["languages"]) == p["recommendation"]["n"]
    assert sum(w["n"] for w in p["weekly"]) == p["recommendation"]["n"]


def test_source_pointer_resolves_to_exact_original_record(populated):
    store, original = populated
    app = create_app(store, serve_frontend=False)
    with TestClient(app) as client:
        page = client.get("/api/quality/evidence", params={"source": "steam"}).json()
        eid = page["rows"][0]["id"]
        detail = client.get("/api/quality/evidence/" + eid).json()
        assert detail["lineage"]["record"]["recommendationid"] == detail["evidence"]["remote_id"]
        assert detail["lineage"]["record"]["voted_up"] == bool(detail["evidence"]["recommended"])
        assert len(detail["lineage"]["sha256"]) == 64
        assert client.get("/api/quality/export?format=csv").text.startswith("\ufeffid,")


def test_triage_requires_evidence_in_product_and_audits_revision(populated):
    store, original = populated
    eid = store.query("SELECT id FROM evidence WHERE run_id=? LIMIT 1", (original,))[0]["id"]
    with pytest.raises(ValueError, match="不属于"):
        store.create_triage(original, "openttd", "故障注入测试事项", [eid], "", "")
    item = store.create_triage(
        original, "mindustry", "契约验收测试事项", [eid], "", "测试数据库内建立事项"
    )
    with pytest.raises(ValueError, match="调查"):
        store.update_triage(item["id"], 1, "confirmed", "测试执行者", "跳过调查的故障注入")
    updated = store.update_triage(item["id"], 1, "investigating", "测试执行者", "核对原始页与字段")
    assert updated["revision"] == 2 and len(updated["history"]) == 2
    with pytest.raises(ConflictError):
        store.update_triage(item["id"], 1, "closed", "测试执行者", "模拟过时页面保存")


def test_api_rejects_cross_site_writes_and_unknown_products(populated):
    store, _ = populated
    with TestClient(create_app(store, serve_frontend=False)) as client:
        assert client.post("/api/quality/sync", json={"products": ["unknown"]}).status_code == 422
        assert (
            client.post(
                "/api/quality/triage", json={}, headers={"Origin": "https://untrusted.example"}
            ).status_code
            == 403
        )
        assert client.get("/api/quality/evidence?limit=1001").status_code == 422
        assert client.get("/api/quality/evidence?search=%27%20OR%201=1--").json()["total"] == 0


def agent_call(**overrides):
    return ToolCall.model_validate({"tool": "review_breakdown", "group_by": "language", "language": None, "category": None, "recommended": None, "start": None, "end": None, **overrides})


def test_agent_packet_is_bound_to_product_and_completed_snapshot(populated):
    store, run_id = populated
    with pytest.raises(ValueError, match="产品"):
        build_packet(store, AgentRequest(run_id=run_id, product="openttd", message="test"))
    queued = store.new_run({})
    with pytest.raises(ValueError, match="完成"):
        build_packet(store, AgentRequest(run_id=queued, product="mindustry", message="test"))


def test_agent_selection_cannot_reference_unprovided_evidence(populated):
    store, run_id = populated
    with pytest.raises(ValueError, match="证据"):
        build_packet(store, AgentRequest(run_id=run_id, product="mindustry", message="test", evidence_ids=["fabricated"]))
    with pytest.raises(ValueError, match="版本"):
        build_packet(store, AgentRequest(run_id=run_id, product="mindustry", message="test", release_id="fabricated"))


def test_agent_queries_reconcile_and_leave_warehouse_unchanged(populated):
    store, run_id = populated
    packet = build_packet(store, AgentRequest(run_id=run_id, product="mindustry", message="test"))
    original_count = store.query("SELECT COUNT(*) AS n FROM evidence")[0]["n"]
    previous = packet_hash(packet)
    trace = execute_tool(store, packet, agent_call(), 0)
    assert trace["result"]["total"] == packet["facts"]["recommendation.n"]
    assert sum(r["negative"] for r in trace["result"]["rows"]) == packet["facts"]["recommendation.negative"]
    assert "run_id=?" in trace["sql"] and "product=?" in trace["sql"]
    assert packet_hash(packet) != previous
    assert store.query("SELECT COUNT(*) AS n FROM evidence")[0]["n"] == original_count


def test_agent_query_injection_is_a_literal_filter(populated):
    store, run_id = populated
    packet = build_packet(store, AgentRequest(run_id=run_id, product="mindustry", message="test"))
    trace = execute_tool(store, packet, agent_call(language="english' OR 1=1 --"), 0)
    assert trace["result"]["total"] == 0
    assert "OR 1=1" not in trace["sql"]


def test_agent_query_time_scope_and_naive_dates_are_rejected(populated):
    store, run_id = populated
    packet = build_packet(store, AgentRequest(run_id=run_id, product="mindustry", message="test"))
    for start in ["1900-01-01T00:00:00Z", "2026-10-11T00:00:00", "not-a-date"]:
        with pytest.raises(ValueError, match="时间"):
            execute_tool(store, packet, agent_call(start=start), 0)
    with pytest.raises(ValueError, match="类型"):
        execute_tool(store, packet, agent_call(category="unknown"), 0)


def test_agent_answer_rejects_hallucinated_metrics_and_references(populated):
    store, run_id = populated
    packet = build_packet(store, AgentRequest(run_id=run_id, product="mindustry", message="test"))
    base = {"mode": "answer", "summary": "小样本描述", "claims": [{"text": "样本量", "status": "supported", "fact_ids": ["recommendation.n"], "evidence_ids": []}], "metrics": [{"fact_id": "recommendation.n", "value": packet["facts"]["recommendation.n"]}], "tool_calls": [], "limitations": ["不能推断收入"], "next_actions": []}
    assert verify_answer(packet, AgentAnswer.model_validate(base))["status"] == "passed"
    base["metrics"][0]["value"] += 1
    base["claims"][0]["evidence_ids"] = ["fabricated-review"]
    checked = verify_answer(packet, AgentAnswer.model_validate(base))
    assert checked["status"] == "failed" and len(checked["errors"]) == 2


def test_agent_context_checks_raw_hash_before_prompting(populated):
    store, run_id = populated
    page = store.query("SELECT p.* FROM pages p JOIN evidence e ON e.page_id=p.id WHERE e.run_id=? AND e.source='steam' LIMIT 1", (run_id,))[0]
    (store.root / page["path"]).write_bytes(b"tampered")
    with pytest.raises(ValueError):
        build_packet(store, AgentRequest(run_id=run_id, product="mindustry", message="test"))


def test_agent_command_never_contains_user_prompt_or_shell_permission(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    (tmp_path / "config.toml").write_text('model="configured-model"\nmodel_reasoning_effort="high"\n', encoding="utf-8")
    args = command_args(["codex"], tmp_path, tmp_path / "schema.json", tmp_path / "answer.json")
    assert "read-only" in args and "--ignore-user-config" in args
    assert "shell_tool" in args and "--dangerously-bypass-approvals-and-sandbox" not in args
    assert 'model="configured-model"' in args
    assert args[-1] == "-"


def test_agent_inference_gate_stops_additional_queries(populated):
    store, run_id = populated
    packet = build_packet(store, AgentRequest(run_id=run_id, product="mindustry", message="test"))
    packet["inference_gate"] = {"query_budget": 0, "reason": "未覆盖后窗"}
    with pytest.raises(ValueError, match="停止"):
        execute_tool(store, packet, agent_call(), 0)
    assert packet["tool_results"] == []


def test_replay_mismatch_is_rejected_before_publication(populated, monkeypatch):
    store, original = populated
    from src.quality import pipeline
    calls = []
    monkeypatch.setattr(pipeline, "snapshot_fingerprint", lambda *args: "changed-caliber")
    monkeypatch.setattr(store, "complete", lambda *args: calls.append(args))
    with pytest.raises(ValueError, match="fingerprint"):
        replay(store, original)
    assert calls == []
    assert store.latest()["id"] == original


def test_replay_under_new_rules_recomputes_and_records_the_change(populated, monkeypatch):
    store, original = populated
    from src.quality import pipeline

    monkeypatch.setattr(pipeline, "TAXONOMY_VERSION", "test-only-next-rules")
    report = replay(store, original)
    run = store.run(report["run_id"])
    assert run["status"] == "completed" and report["fingerprint"] != store.run(original)["fingerprint"]
    assert run["config"]["recomputed_rules"]["to"]["taxonomy_version"] == "test-only-next-rules"


def test_agent_default_query_includes_captured_final_second(populated):
    store, run_id = populated
    packet = build_packet(store, AgentRequest(run_id=run_id, product="mindustry", message="test"))
    row = store.query("SELECT id FROM evidence WHERE run_id=? AND source='steam' LIMIT 1", (run_id,))[0]
    # Boundary fault injection in tmp_path only, not a demonstration record.
    with store.connect() as conn:
        conn.execute("UPDATE evidence SET created_at=? WHERE run_id=? AND id=?", (packet["as_of"], run_id, row["id"]))
    trace = execute_tool(store, packet, agent_call(), 0)
    assert trace["result"]["total"] == packet["facts"]["recommendation.n"]


def test_issue_template_boilerplate_is_not_a_mention():
    # Shaped like a real issue form: the "(Crash) logs" heading is in every issue of the repository.
    body = "\n".join(
        [
            "### Platforms",
            "Windows",
            "### Issue",
            "Units stop moving after loading a save.",
            "### (Crash) logs",
            "_No response_",
            "### Submission",
            "- [x] I have searched the closed and open issues to make sure this has not crashed before.",
            "<!-- Please describe the crash in detail. -->",
        ]
    )
    text = "Units freeze after loading\n" + body
    masked = mask_issue_template(text)
    assert len(masked) == len(text) and "Units stop moving" in masked
    found = {m["category"]: m["cues"] for m in find_mentions(text, "english", "github_issues")}
    assert [c["text"] for c in found["stability"]] == ["freeze"]
    cue = found["stability"][0]
    assert text[cue["start"] : cue["end"]] == "freeze"
    # Steam reviews have no template, so headings there are the player's own words.
    assert find_mentions("### crash on start", "english", "steam")[0]["category"] == "stability"
