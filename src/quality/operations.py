"""Database task leases, consistent backups and restore drills."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
import zipfile
from contextlib import closing, contextmanager

from src.quality.contracts import iso, utc_now
from src.quality.store import ConflictError, Store

SCHEMA = """
CREATE TABLE IF NOT EXISTS task_leases(resource TEXT PRIMARY KEY,owner TEXT NOT NULL,task_id TEXT NOT NULL,expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS recovery_drills(id TEXT PRIMARY KEY,at TEXT NOT NULL,backup TEXT NOT NULL,result_json TEXT NOT NULL);
"""


class Operations:
    def __init__(self, store: Store):
        self.store = store
        with store.connect() as conn:
            conn.executescript(SCHEMA)

    def acquire(self, resource: str, task_id: str, ttl=60):
        owner = uuid.uuid4().hex
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM task_leases WHERE resource=?", (resource,)).fetchone()
            if row and row["expires_at"] > time.time():
                raise ConflictError("其他进程持有此任务资源，请等待或取消当前任务")
            conn.execute(
                "INSERT INTO task_leases VALUES(?,?,?,?) ON CONFLICT(resource) DO UPDATE SET owner=excluded.owner,task_id=excluded.task_id,expires_at=excluded.expires_at",
                (resource, owner, task_id, time.time() + ttl),
            )
        return owner

    def bind(self, resource, owner, task_id):
        with self.store.connect() as conn:
            if (
                conn.execute(
                    "UPDATE task_leases SET task_id=? WHERE resource=? AND owner=?",
                    (task_id, resource, owner),
                ).rowcount
                != 1
            ):
                raise ConflictError("任务租约已被其他进程取得")

    def release(self, resource, owner):
        with self.store.connect() as conn:
            conn.execute("DELETE FROM task_leases WHERE resource=? AND owner=?", (resource, owner))

    @contextmanager
    def heartbeat(self, resource, owner, ttl=60):
        stopped = threading.Event()

        def beat():
            while not stopped.wait(10):
                with self.store.connect() as conn:
                    conn.execute(
                        "UPDATE task_leases SET expires_at=? WHERE resource=? AND owner=?",
                        (time.time() + ttl, resource, owner),
                    )

        thread = threading.Thread(target=beat, daemon=True)
        thread.start()
        try:
            yield
        finally:
            stopped.set()
            thread.join(timeout=2)
            self.release(resource, owner)

    def backup(self):
        identity = utc_now().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
        staging = self.store.root / "backups" / identity
        staging.mkdir(parents=True)
        database = staging / "warehouse.sqlite3"
        with (
            closing(sqlite3.connect(self.store.database)) as src,
            closing(sqlite3.connect(database)) as dst,
        ):
            src.backup(dst)
            if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("备份数据库完整性检查失败")
            pages = dst.execute("SELECT path,sha256 FROM pages").fetchall()
        files = {"warehouse.sqlite3": hashlib.sha256(database.read_bytes()).hexdigest()}
        archive = staging / "backup.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.write(database, "warehouse.sqlite3")
            for relative, digest in pages:
                content = self.store.read_raw(relative, digest)
                if relative in files:
                    continue
                files[relative] = digest
                z.writestr(relative, content)
            manifest = {
                "id": identity,
                "at": iso(utc_now()),
                "files": files,
                "scope": "一致性数据库与全部原始来源页；不包含访问令牌；查询缓存与导出报告可重建",
            }
            z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        report = {
            "id": identity,
            "at": manifest["at"],
            "path": str(archive),
            "bytes": archive.stat().st_size,
            "files": len(files),
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        }
        (staging / "backup-summary.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return report

    def restore_drill(self, backup_id: str):
        if not backup_id.replace("-", "").isalnum() or len(backup_id) > 60:
            raise ValueError("无效备份ID")
        archive = self.store.root / "backups" / backup_id / "backup.zip"
        start = time.monotonic()
        target = self.store.root / "recovery" / (backup_id + "-" + uuid.uuid4().hex[:8])
        target.mkdir(parents=True)
        with zipfile.ZipFile(archive) as z:
            if z.getinfo("manifest.json").file_size > 10 * 1024 * 1024:
                raise ValueError("备份清单过大")
            manifest = json.loads(z.read("manifest.json"))
            if (
                "warehouse.sqlite3" not in manifest.get("files", {})
                or len(manifest["files"]) > 100000
            ):
                raise ValueError("备份清单缺少数据库或文件数超限")
            if sum(z.getinfo(relative).file_size for relative in manifest["files"]) > 2 * 1024**3:
                raise ValueError("备份解压大小超过2GiB，请分区恢复")
            for relative, digest in manifest["files"].items():
                resolved = (target / relative).resolve()
                if not resolved.is_relative_to(target.resolve()) or "\\" in relative:
                    raise ValueError("备份包含越界路径")
                content = z.read(relative)
                if hashlib.sha256(content).hexdigest() != digest:
                    raise ValueError("备份文件校验不通过")
                resolved.parent.mkdir(parents=True, exist_ok=True)
                resolved.write_bytes(content)
        with closing(sqlite3.connect(target / "warehouse.sqlite3")) as conn, conn:
            if (
                conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                or conn.execute("PRAGMA foreign_key_check").fetchall()
            ):
                raise ValueError("恢复数据库完整性或外键检查失败")
            rows = conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
            latest = conn.execute(
                "SELECT id,fingerprint FROM runs WHERE status='completed' ORDER BY finished_at DESC,rowid DESC LIMIT 1"
            ).fetchone()
            # Dead worker leases and access sessions cannot survive a restored server.
            conn.execute("DELETE FROM task_leases")
        result = {
            "status": "passed",
            "restored_to": str(target),
            "evidence_rows": rows,
            "raw_files": sum(path.startswith("raw/") for path in manifest["files"]),
            "latest_run": latest[0] if latest else None,
            "fingerprint": latest[1] if latest else None,
            "recovery_seconds": round(time.monotonic() - start, 3),
            "original_untouched": True,
        }
        with self.store.connect() as conn:
            conn.execute(
                "INSERT INTO recovery_drills VALUES(?,?,?,?)",
                (uuid.uuid4().hex, iso(utc_now()), backup_id, json.dumps(result)),
            )
        return result

    def backups(self, limit=10):
        """Most recent backups first, read from the summary written next to each archive."""
        root = self.store.root / "backups"
        return [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(root.glob("*/backup-summary.json"), reverse=True)[:limit]
        ]
