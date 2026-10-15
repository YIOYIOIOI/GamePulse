"""SQLite WAL snapshots, immutable source files, and auditable analyst decisions."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from src.quality.contracts import iso, utc_now

SCHEMA = """
CREATE TABLE IF NOT EXISTS task_leases(resource TEXT PRIMARY KEY,owner TEXT NOT NULL,task_id TEXT NOT NULL,expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS run_leases(run_id TEXT PRIMARY KEY,owner TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
 status TEXT NOT NULL, config_json TEXT NOT NULL, progress_json TEXT NOT NULL DEFAULT '{}',
 report_json TEXT, fingerprint TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS pages (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), product TEXT NOT NULL,
 source TEXT NOT NULL, sequence INTEGER NOT NULL, url TEXT NOT NULL,
 fetched_at TEXT NOT NULL, sha256 TEXT NOT NULL, path TEXT NOT NULL,
 http_status INTEGER NOT NULL, headers_json TEXT NOT NULL, metadata_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
 run_id TEXT NOT NULL REFERENCES runs(id), id TEXT NOT NULL, product TEXT NOT NULL,
 source TEXT NOT NULL, remote_id TEXT NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL,
 language TEXT NOT NULL, language_method TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 recommended INTEGER, playtime_minutes INTEGER, playtime_at_review_minutes INTEGER,
 helpful_votes INTEGER, state TEXT, closed_at TEXT, labels_json TEXT NOT NULL DEFAULT '[]',
 source_url TEXT NOT NULL, page_id TEXT NOT NULL REFERENCES pages(id), json_pointer TEXT NOT NULL,
 PRIMARY KEY(run_id,id)
);
CREATE INDEX IF NOT EXISTS evidence_slice ON evidence(run_id, product, source, created_at);
CREATE TABLE IF NOT EXISTS mentions (
 run_id TEXT NOT NULL, evidence_id TEXT NOT NULL, category TEXT NOT NULL,
 cues_json TEXT NOT NULL, PRIMARY KEY(run_id,evidence_id,category),
 FOREIGN KEY(run_id,evidence_id) REFERENCES evidence(run_id,id)
);
CREATE TABLE IF NOT EXISTS releases (
 run_id TEXT NOT NULL REFERENCES runs(id), id TEXT NOT NULL, product TEXT NOT NULL,
 title TEXT NOT NULL, tag TEXT NOT NULL, published_at TEXT NOT NULL, body TEXT NOT NULL,
 source_url TEXT NOT NULL, page_id TEXT NOT NULL REFERENCES pages(id), json_pointer TEXT NOT NULL,
 PRIMARY KEY(run_id,id)
);
CREATE TABLE IF NOT EXISTS quarantine (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), product TEXT NOT NULL,
 source TEXT NOT NULL, page_id TEXT NOT NULL REFERENCES pages(id), json_pointer TEXT NOT NULL,
 reason TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS http_cache (
 url TEXT PRIMARY KEY, etag TEXT, path TEXT NOT NULL, sha256 TEXT NOT NULL, fetched_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS triage (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), product TEXT NOT NULL,
 title TEXT NOT NULL, evidence_json TEXT NOT NULL, status TEXT NOT NULL,
 owner TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY, triage_id TEXT NOT NULL REFERENCES triage(id), at TEXT NOT NULL,
 action TEXT NOT NULL, before_json TEXT, after_json TEXT NOT NULL, note TEXT NOT NULL
);
"""


class ConflictError(ValueError):
    pass


class Store:
    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "warehouse.sqlite3"
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
            conn.execute("BEGIN IMMEDIATE")
            if "workspace" not in {r[1] for r in conn.execute("PRAGMA table_info(triage)")}:
                conn.execute("ALTER TABLE triage ADD COLUMN workspace TEXT NOT NULL DEFAULT 'main'")
            if "actor" not in {r[1] for r in conn.execute("PRAGMA table_info(audit)")}:
                conn.execute("ALTER TABLE audit ADD COLUMN actor TEXT NOT NULL DEFAULT ''")

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.database, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def new_run(self, config: dict, lease: tuple[str, str] | None = None) -> str:
        run_id = utc_now().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:10]
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO runs(id,started_at,status,config_json) VALUES(?,?,?,?)",
                (run_id, iso(utc_now()), "queued", json.dumps(config, ensure_ascii=False)),
            )
            if (
                lease
                and conn.execute(
                    "UPDATE task_leases SET task_id=? WHERE resource=? AND owner=? AND expires_at>?",
                    (run_id, *lease, time.time()),
                ).rowcount
                != 1
            ):
                raise ConflictError("任务租约已失效")
            if lease:
                conn.execute("INSERT INTO run_leases VALUES(?,?)", (run_id, lease[1]))
        return run_id

    def progress(self, run_id: str, **progress):
        with self.connect() as conn:
            conn.execute(
                "UPDATE runs SET status='running',progress_json=? WHERE id=?",
                (json.dumps(progress, ensure_ascii=False), run_id),
            )

    def fail(self, run_id: str, error: str):
        with self.connect() as conn:
            conn.execute(
                "UPDATE runs SET status='failed',finished_at=?,error=? WHERE id=?",
                (iso(utc_now()), error[:3000], run_id),
            )

    def recover_interrupted(self):
        with self.connect() as conn:
            conn.execute(
                "UPDATE runs SET status='failed',finished_at=?,error=? "
                "WHERE status IN ('queued','running') AND NOT EXISTS(SELECT 1 FROM task_leases l WHERE l.resource='collection' AND l.task_id=runs.id AND l.expires_at>?)",
                (
                    iso(utc_now()),
                    "上次进程在发布完成快照前中断；请重新采集或重放原始页。",
                    time.time(),
                ),
            )

    def save_page(
        self,
        run_id: str,
        product: str,
        source: str,
        sequence: int,
        url: str,
        content: bytes,
        status: int,
        headers: dict,
        metadata: dict | None = None,
    ) -> dict:
        digest = hashlib.sha256(content).hexdigest()
        relative = Path("raw") / run_id / source / f"{product}-{sequence:04d}-{digest[:12]}.json"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError("immutable raw page has changed")
        else:
            with path.open("xb") as stream:
                stream.write(content)
        page = dict(
            id=uuid.uuid4().hex,
            run_id=run_id,
            product=product,
            source=source,
            sequence=sequence,
            url=url,
            fetched_at=iso(utc_now()),
            sha256=digest,
            path=relative.as_posix(),
            http_status=status,
            headers_json=json.dumps(headers),
            metadata_json=json.dumps(metadata or {}),
        )
        with self.connect() as conn:
            columns = list(page)
            conn.execute(
                f"INSERT INTO pages({','.join(columns)}) VALUES({','.join('?' for _ in columns)})",
                list(page.values()),
            )
            if (
                source.startswith("github")
                and status in (200, 304)
                and not (metadata or {}).get("replayed_from")
            ):
                conn.execute(
                    "INSERT INTO http_cache VALUES(?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET "
                    "etag=excluded.etag,path=excluded.path,sha256=excluded.sha256,"
                    "fetched_at=excluded.fetched_at",
                    (url, headers.get("etag"), page["path"], digest, page["fetched_at"]),
                )
        return page

    def cached(self, url: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM http_cache WHERE url=?", (url,)).fetchone()
        return dict(row) if row else None

    def read_raw(self, path: str, expected_sha: str) -> bytes:
        target = (self.root / path).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("raw path outside store")
        content = target.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected_sha:
            raise ValueError("raw SHA-256 mismatch")
        return content

    def run(self, run_id: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            return None
        out = dict(row)
        for key in ("config", "progress", "report"):
            out[key] = json.loads(out.pop(key + "_json") or "null")
        return out

    def list_runs(self, limit: int = 20) -> list[dict]:
        with self.connect() as conn:
            ids = [
                r[0]
                for r in conn.execute(
                    "SELECT id FROM runs ORDER BY started_at DESC,rowid DESC LIMIT ?", (limit,)
                )
            ]
        return [self.run(i) for i in ids]

    def latest(self, product: str | None = None) -> dict | None:
        """Newest completed snapshot; with a product, the newest one that collected that game."""
        query, params = "SELECT id FROM runs WHERE status='completed'", ()
        if product:
            # Games can be synced on their own, so the newest snapshot may not include every game.
            query += (
                " AND EXISTS(SELECT 1 FROM json_each(runs.config_json,'$.products') WHERE value=?)"
            )
            params = (product,)
        with self.connect() as conn:
            row = conn.execute(
                query + " ORDER BY finished_at DESC,rowid DESC LIMIT 1", params
            ).fetchone()
        return self.run(row[0]) if row else None

    def pages(self, run_id: str) -> list[dict]:
        with self.connect() as conn:
            return [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM pages WHERE run_id=? ORDER BY product,source,sequence", (run_id,)
                )
            ]

    def query(self, sql: str, params=()) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(sql, params)]

    def publish_rows(
        self,
        run_id: str,
        evidence: list[dict],
        releases: list[dict],
        mentions: list[dict],
        quarantine: list[dict],
    ):
        with self.connect() as conn:
            for table, rows in [
                ("evidence", evidence),
                ("releases", releases),
                ("mentions", mentions),
                ("quarantine", quarantine),
            ]:
                if not rows:
                    continue
                columns = list(rows[0])
                conn.executemany(
                    f"INSERT INTO {table}({','.join(columns)}) "
                    f"VALUES({','.join('?' for _ in columns)})",
                    [[r[col] for col in columns] for r in rows],
                )

    def complete(self, run_id: str, report: dict, fingerprint: str):
        encoded = json.dumps(report, ensure_ascii=False, allow_nan=False, sort_keys=True)
        output = self.root / "reports" / run_id
        output.mkdir(parents=True, exist_ok=True)
        (output / "report.json").write_text(encoded, encoding="utf-8")
        from src.quality.exporting import write_outputs

        write_outputs(self, report, output)
        # Only publish after exports are readable; interrupted artifacts never become "latest".
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM run_leases WHERE run_id=?", (run_id,)).fetchone():
                valid = conn.execute(
                    "SELECT 1 FROM task_leases l JOIN run_leases r ON r.owner=l.owner WHERE r.run_id=? AND l.resource='collection' AND l.task_id=? AND l.expires_at>?",
                    (run_id, run_id, time.time()),
                ).fetchone()
                if not valid:
                    raise ConflictError("发布前任务租约已失效，拒绝旧进程覆盖完成快照")
            conn.execute(
                "UPDATE runs SET status='completed',finished_at=?,report_json=?,fingerprint=? WHERE id=?",
                (iso(utc_now()), encoded, fingerprint, run_id),
            )

    def create_triage(
        self,
        run_id: str,
        product: str,
        title: str,
        evidence_ids: list[str],
        owner: str,
        note: str,
        workspace="main",
        actor="",
    ) -> dict:
        evidence_ids = list(dict.fromkeys(evidence_ids))
        with self.connect() as conn:
            for eid in evidence_ids:
                if not conn.execute(
                    "SELECT 1 FROM evidence WHERE run_id=? AND product=? AND id=?",
                    (run_id, product, eid),
                ).fetchone():
                    raise ValueError("证据不存在或不属于所选产品")
            now = iso(utc_now())
            tid = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO triage(id,run_id,product,title,evidence_json,status,owner,created_at,updated_at,revision,workspace) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    tid,
                    run_id,
                    product,
                    title,
                    json.dumps(evidence_ids),
                    "pending",
                    owner,
                    now,
                    now,
                    1,
                    workspace,
                ),
            )
            result = dict(conn.execute("SELECT * FROM triage WHERE id=?", (tid,)).fetchone())
            conn.execute(
                "INSERT INTO audit(triage_id,at,action,after_json,note,actor) VALUES(?,?,?,?,?,?)",
                (tid, now, "created", json.dumps(result), note, actor),
            )
        return self.triage_item(tid)

    def triage_item(self, tid: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM triage WHERE id=?", (tid,)).fetchone()
            if not row:
                return None
            result = dict(row)
            result["evidence_ids"] = json.loads(result.pop("evidence_json"))
            result["history"] = []
            for entry in conn.execute(
                "SELECT at,action,note,actor,before_json,after_json FROM audit WHERE triage_id=? ORDER BY id",
                (tid,),
            ):
                before = json.loads(entry["before_json"]) if entry["before_json"] else {}
                after = json.loads(entry["after_json"])
                result["history"].append(
                    {
                        "at": entry["at"],
                        "action": entry["action"],
                        "note": entry["note"],
                        "actor": entry["actor"],
                        "status": after.get("status"),
                        "previous_status": before.get("status"),
                        "owner": after.get("owner"),
                    }
                )
        return result

    def list_triage(self) -> list[dict]:
        return [
            self.triage_item(r["id"])
            for r in self.query("SELECT id FROM triage ORDER BY updated_at DESC")
        ]

    def update_triage(
        self, tid: str, revision: int, status: str, owner: str, note: str, actor=""
    ) -> dict:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM triage WHERE id=?", (tid,)).fetchone()
            if not row:
                raise ValueError("复核事项不存在")
            before = dict(row)
            if before["revision"] != revision:
                raise ConflictError("事项已被更新，请刷新后再保存")
            if status in ("investigating", "confirmed") and not owner.strip():
                raise ValueError("进入调查或确认状态需要填写负责人")
            allowed = {
                "pending": {"pending", "investigating", "closed"},
                "investigating": {"investigating", "confirmed", "closed", "pending"},
                "confirmed": {"confirmed", "closed", "investigating"},
                "closed": {"closed", "investigating"},
            }
            if status not in allowed[before["status"]]:
                raise ValueError("请先调查证据，再确认问题")
            now = iso(utc_now())
            changed = conn.execute(
                "UPDATE triage SET status=?,owner=?,updated_at=?,revision=revision+1 WHERE id=? AND revision=?",
                (status, owner, now, tid, revision),
            )
            if changed.rowcount != 1:
                raise ConflictError("事项已被更新，请刷新后再保存")
            after = dict(conn.execute("SELECT * FROM triage WHERE id=?", (tid,)).fetchone())
            conn.execute(
                "INSERT INTO audit(triage_id,at,action,before_json,after_json,note,actor) VALUES(?,?,?,?,?,?,?)",
                (tid, now, "updated", json.dumps(before), json.dumps(after), note, actor),
            )
        return self.triage_item(tid)
