"""Snapshot-isolated read-only SQL behind the assistant query tool."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from contextlib import closing

from pydantic import BaseModel, ConfigDict, Field

from src.quality.store import Store

FUNCTIONS = {
    "count",
    "sum",
    "avg",
    "min",
    "max",
    "round",
    "abs",
    "coalesce",
    "ifnull",
    "nullif",
    "date",
    "datetime",
    "strftime",
    "julianday",
    "substr",
    "length",
    "lower",
    "upper",
    "trim",
    "replace",
    "like",
    "instr",
    "row_number",
    "rank",
    "dense_rank",
    "lag",
    "lead",
    "total",
    "printf",
    "group_concat",
    "iif",
}
TABLES = {"reviews", "issues", "releases", "mentions"}


class SQLRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    product: str
    sql: str = Field(min_length=5, max_length=12000)
    limit: int = Field(default=200, ge=1, le=1000)


class ReadOnlySQL:
    def __init__(self, store: Store):
        self.store = store
        self.lock = threading.Lock()

    def database(self, run_id: str, product: str):
        run = self.store.run(run_id)
        if (
            not run
            or run["status"] != "completed"
            or product not in {p["key"] for p in run["report"]["products"]}
        ):
            raise ValueError("产品必须属于已完成快照")
        key = hashlib.sha256(f"{run_id}:{product}:sql-v1".encode()).hexdigest()
        path = self.store.root / "sql" / (key + ".sqlite3")
        with self.lock:
            if not path.exists():
                path.parent.mkdir(exist_ok=True)
                temporary = path.with_suffix(f".{uuid.uuid4().hex}.building.sqlite3")
                with closing(sqlite3.connect(temporary)) as conn, conn:
                    for table, query in {
                        "reviews": "SELECT id,created_at,language,recommended,playtime_at_review_minutes,helpful_votes,text,source_url FROM evidence WHERE run_id=? AND product=? AND source='steam'",
                        "issues": "SELECT id,created_at,updated_at,closed_at,state,title,text,source_url FROM evidence WHERE run_id=? AND product=? AND source='github_issues'",
                        "releases": "SELECT id,tag,title,published_at,body,source_url FROM releases WHERE run_id=? AND product=?",
                        "mentions": "SELECT m.evidence_id,m.category FROM mentions m JOIN evidence e ON m.run_id=e.run_id AND m.evidence_id=e.id WHERE e.run_id=? AND e.product=?",
                    }.items():
                        rows = self.store.query(query, (run_id, product))
                        if rows:
                            columns = list(rows[0])
                        else:
                            with self.store.connect() as source:
                                columns = [
                                    c[0]
                                    for c in source.execute(query, (run_id, product)).description
                                ]
                        conn.execute(f"CREATE TABLE {table}({','.join(columns)})")
                        if rows:
                            conn.executemany(
                                f"INSERT INTO {table} VALUES({','.join('?' for _ in columns)})",
                                [tuple(r[c] for c in columns) for r in rows],
                            )
                    conn.execute("CREATE INDEX review_time ON reviews(created_at)")
                    conn.execute("CREATE INDEX review_language ON reviews(language,recommended)")
                    conn.execute("CREATE INDEX mention_id ON mentions(evidence_id,category)")
                if path.exists():
                    temporary.unlink()
                else:
                    try:
                        temporary.rename(path)
                    except FileExistsError:
                        temporary.unlink()
        return path, run

    def schema(self, run_id: str, product: str):
        path, run = self.database(run_id, product)
        with closing(sqlite3.connect(path)) as conn:
            tables = {
                t: [
                    {"name": r[1], "type": "source value"}
                    for r in conn.execute(f"PRAGMA table_info({t})")
                ]
                for t in sorted(TABLES)
            }
        return {
            "tables": tables,
            "fingerprint": run["fingerprint"],
            "definitions": {
                "not_recommended_rate": "SUM(recommended=0)*1.0/COUNT(*)；分母只包含当前查询筛选的评论",
                "playtime": "评论时游玩分钟；缺失为 NULL",
                "issue_resolution": "公开 issue 的关闭时间，不是玩家缺陷恢复时间",
            },
        }

    def query(self, body: SQLRequest):
        path, run = self.database(body.run_id, body.product)
        start = time.monotonic()
        deadline = start + 3

        def authorize(action, one, two, _db, _view):
            if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_READ and one in TABLES:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_FUNCTION and str(two or one).lower() in FUNCTIONS:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        with closing(
            sqlite3.connect(f"file:{path.as_posix()}?mode=ro&immutable=1", uri=True)
        ) as conn:
            conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1024 * 1024)
            conn.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 100)
            conn.setlimit(sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 50)
            conn.setlimit(sqlite3.SQLITE_LIMIT_COMPOUND_SELECT, 20)
            conn.execute("PRAGMA query_only=ON")
            conn.set_authorizer(authorize)
            conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
            try:
                cursor = conn.execute(body.sql)
                columns = [c[0] for c in cursor.description or []]
                if len(columns) != len(set(columns)):
                    raise ValueError("结果列名重复，请为表达式设置不同别名")
                fetched = cursor.fetchmany(body.limit + 1)
            except sqlite3.Error as exc:
                raise ValueError(f"SQL 未通过只读权限/语法或3秒执行限制：{exc}") from exc
        rows = [dict(zip(columns, r)) for r in fetched[: body.limit]]
        result = {
            "columns": columns,
            "rows": rows,
            "truncated": len(fetched) > body.limit,
            "limit": body.limit,
            "duration_ms": round((time.monotonic() - start) * 1000, 2),
            "fingerprint": run["fingerprint"],
            "run_id": body.run_id,
            "product": body.product,
            "sql": body.sql,
        }
        if len(json.dumps(rows, ensure_ascii=False).encode()) > 1024 * 1024:
            raise ValueError("结果超过1MiB，请缩小字段、时间或行数")
        return result
