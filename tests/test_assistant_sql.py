"""The assistant's read-only SQL tool: scoped to one snapshot and product, bounded in time and size."""

from __future__ import annotations

import time

import pytest
from test_quality_workflow import populated as populated

from src.quality.agent_contracts import AgentRequest, ToolCall
from src.quality.agent_tools import build_packet, execute_tool
from src.quality.readonly_sql import ReadOnlySQL, SQLRequest


def test_sql_scope_and_window_functions(populated):
    store, rid = populated
    engine = ReadOnlySQL(store)
    sql = "WITH daily AS (SELECT date(created_at) AS day,COUNT(*) AS n FROM reviews GROUP BY day) SELECT day,n,SUM(n) OVER (ORDER BY day) AS cumulative FROM daily ORDER BY day"
    result = engine.query(SQLRequest(run_id=rid, product="mindustry", sql=sql))
    expected = store.query(
        "SELECT COUNT(*) AS n FROM evidence WHERE run_id=? AND source='steam'", (rid,)
    )[0]["n"]
    assert sum(r["n"] for r in result["rows"]) == expected
    assert result["rows"][-1]["cumulative"] == expected
    assert result["fingerprint"] == store.run(rid)["fingerprint"]
    with pytest.raises(ValueError):
        engine.schema(rid, "openttd")


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM reviews",
        "UPDATE reviews SET recommended=1",
        "CREATE TABLE a(x)",
        "PRAGMA table_info(reviews)",
        "ATTACH DATABASE 'warehouse.sqlite3' AS main2",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM access_identities",
        "SELECT load_extension('bad')",
    ],
)
def test_sql_cannot_escape_or_exhaust_result(populated, sql):
    store, rid = populated
    with pytest.raises(ValueError):
        ReadOnlySQL(store).query(SQLRequest(run_id=rid, product="mindustry", sql=sql))
    assert store.latest()["id"] == rid


def test_sql_deadline_stops_unbounded_recursion(populated):
    store, rid = populated
    start = time.monotonic()
    with pytest.raises(ValueError, match="3秒"):
        ReadOnlySQL(store).query(
            SQLRequest(
                run_id=rid,
                product="mindustry",
                sql="WITH RECURSIVE x(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM x) SELECT SUM(n) FROM x",
            )
        )
    assert time.monotonic() - start < 6


def test_sql_function_output_is_bounded_even_without_progress_callback(populated):
    store, rid = populated
    result = ReadOnlySQL(store).query(
        SQLRequest(run_id=rid, product="mindustry", sql="SELECT printf('%999999999s','x') AS large")
    )
    # SQLite itself returns NULL when its per-value limit is exceeded.
    assert result["rows"] == [{"large": None}]


def test_assistant_sql_tools_read_the_same_snapshot(populated):
    store, rid = populated
    packet = build_packet(store, AgentRequest(run_id=rid, product="mindustry", message="test"))
    base = {"group_by": "language", "language": None, "category": None, "recommended": None}
    base |= {"start": None, "end": None}
    schema = execute_tool(store, packet, ToolCall(tool="query_schema", sql=None, **base), 0)
    assert "reviews" in schema["result"]["tables"]
    sql = "SELECT COUNT(*) AS n FROM reviews"
    trace = execute_tool(store, packet, ToolCall(tool="read_only_sql", sql=sql, **base), 1)
    assert trace["result"]["rows"] == [{"n": packet["facts"]["recommendation.n"]}]
    assert packet["facts"]["tool.1.row.0.n"] == packet["facts"]["recommendation.n"]
