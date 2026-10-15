"""Local evidence service with bounded jobs, source lineage and audit-backed triage."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from src.quality import VERSION
from src.quality.access import Access
from src.quality.agent import AgentService
from src.quality.agent_contracts import AgentRequest
from src.quality.contracts import (
    GameCreate,
    GameUpdate,
    MemberCreate,
    SyncRequest,
    TriageCreate,
    TriageUpdate,
)
from src.quality.exporting import csv_bytes, evidence_rows
from src.quality.games import GameLookup, Games, check_reviewed, normalize_repo
from src.quality.operations import Operations
from src.quality.pipeline import replay, sync
from src.quality.store import ConflictError, Store
from src.quality.taxonomy import CATEGORIES

logger = logging.getLogger(__name__)
LOCAL_ORIGINS = {
    f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (3011, 8767)
}


class Jobs:
    def __init__(self, store: Store):
        self.store = store
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="quality-sync")
        self.lock = threading.Lock()
        self.operations = Operations(store)

    def submit(self, config: dict, original: str | None = None) -> str:
        with self.lock:
            self.store.recover_interrupted()
            if self.store.query("SELECT id FROM runs WHERE status IN ('queued','running') LIMIT 1"):
                raise ConflictError("已有采集或重放任务，请等当前任务结束")
            owner = self.operations.acquire("collection", "preparing")
            try:
                run_id = self.store.new_run(config, ("collection", owner))
                self.pool.submit(self._leased_execute, run_id, config, original, owner)
            except Exception:
                self.operations.release("collection", owner)
                raise
            return run_id

    def _leased_execute(self, run_id, config, original, owner):
        with self.operations.heartbeat("collection", owner):
            self._execute(run_id, config, original)

    def _execute(self, run_id: str, config: dict, original: str | None):
        try:
            if original:
                replay(self.store, original, run_id)
            else:
                sync(self.store, run_id, config)
        except Exception as exc:
            self.store.fail(run_id, f"{type(exc).__name__}: {exc}")
            logger.exception("Quality job failed: %s", run_id)


def create_app(
    store: Store, serve_frontend: bool = True, port: int = 8767, team=False, lookup=None
) -> FastAPI:
    jobs = Jobs(store)
    games = Games(store)
    lookup = lookup or GameLookup()
    agents = AgentService(store)
    operations = Operations(store)
    access = Access(store, team)
    allowed_origins = LOCAL_ORIGINS | {
        f"http://{host}:{port}" for host in ("localhost", "127.0.0.1")
    }

    @asynccontextmanager
    async def lifespan(_app):
        store.recover_interrupted()
        agents.recover()

        async def recover_expired():
            while True:
                await asyncio.sleep(15)
                await asyncio.to_thread(store.recover_interrupted)
                await asyncio.to_thread(agents.recover)

        reaper = asyncio.create_task(recover_expired())
        yield
        reaper.cancel()
        try:
            await reaper
        except asyncio.CancelledError:
            pass
        agents.shutdown()
        jobs.pool.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="GamePulse Product Quality", version=VERSION, lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1"] + ([] if serve_frontend else ["testserver"]),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(allowed_origins),
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-Workspace-ID"],
    )

    @app.middleware("http")
    async def local_writes(request: Request, call_next):
        origin = request.headers.get("origin")
        if (
            request.method in ("POST", "PATCH", "DELETE")
            and origin
            and origin not in allowed_origins
        ):
            return Response(
                json.dumps({"detail": "本地分析服务拒绝此来源的写入"}, ensure_ascii=False),
                status_code=403,
                media_type="application/json",
            )
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > 1024 * 1024):
            return Response("Details too large", status_code=413)
        if request.url.path.startswith("/api/quality") and request.method in ("POST", "PATCH"):
            body = await request.body()
            if len(body) > 1024 * 1024:
                return Response("Details too large", status_code=413)
            try:
                parsed = json.loads(body) if body else {}
                if not isinstance(parsed, dict):
                    raise ValueError()
                request.state.json_body = parsed
            except (ValueError, UnicodeError):
                return Response(
                    '{"detail":"需要有效的JSON对象"}',
                    status_code=422,
                    media_type="application/json",
                )
        if (
            request.url.path.startswith("/api/quality")
            and request.url.path != "/api/quality/health"
            and request.method != "OPTIONS"
        ):
            try:
                principal = access.principal(
                    request.headers.get("authorization"), request.headers.get("x-workspace-id")
                )
                path = request.url.path
                permission = "read"
                if any(s in path for s in ("/access/identities", "/backups", "/sync", "/replay/")):
                    permission = "admin"
                elif path.startswith("/api/quality/games") and (
                    request.method != "GET" or path.endswith("/search")
                ):
                    # Adding, relinking or removing games changes what every sync collects.
                    permission = "admin"
                elif request.method in ("POST", "PATCH", "DELETE"):
                    permission = "analyze"
                access.require(principal, permission)
                if "/agent/conversations/" in path or "/agent/turns/" in path:
                    identity = path.split("/")[5]
                    found = (
                        store.query(
                            "SELECT workspace FROM agent_conversations WHERE id=?", (identity,)
                        )
                        if "/conversations/" in path
                        else store.query(
                            "SELECT c.workspace FROM agent_turns t JOIN agent_conversations c ON c.id=t.conversation_id WHERE t.id=?",
                            (identity,),
                        )
                    )
                    if found and found[0]["workspace"] != principal["workspace"]:
                        raise PermissionError("会话不属于当前工作区")
                if "/triage/" in path:
                    found = store.query(
                        "SELECT workspace FROM triage WHERE id=?", (path.split("/")[4],)
                    )
                    if found and found[0]["workspace"] != principal["workspace"]:
                        raise PermissionError("事项不属于当前工作区")
                    if request.method == "PATCH":
                        body = request.state.json_body
                        if body.get("status") in ("confirmed", "closed"):
                            access.require(principal, "review")
                request.state.principal = principal
            except PermissionError as exc:
                return Response(
                    json.dumps({"detail": str(exc)}, ensure_ascii=False),
                    status_code=401 if not request.headers.get("authorization") and team else 403,
                    media_type="application/json",
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ConflictError)
    async def conflict(_request, exc):
        return Response(
            json.dumps({"detail": str(exc)}, ensure_ascii=False),
            status_code=409,
            media_type="application/json",
        )

    @app.exception_handler(PermissionError)
    async def denied(_request, exc):
        return Response(
            json.dumps({"detail": str(exc)}, ensure_ascii=False),
            status_code=403,
            media_type="application/json",
        )

    @app.exception_handler(ConnectionError)
    async def upstream(_request, exc):
        return Response(
            json.dumps({"detail": str(exc)}, ensure_ascii=False),
            status_code=502,
            media_type="application/json",
        )

    @app.exception_handler(ValueError)
    async def invalid(_request, exc):
        return Response(
            json.dumps({"detail": str(exc)}, ensure_ascii=False),
            status_code=422,
            media_type="application/json",
        )

    @app.get("/api/quality/health")
    def health():
        store.query("SELECT 1")
        latest = store.latest()
        return {
            "status": "ok",
            "version": VERSION,
            "latest_run": latest["id"] if latest else None,
            "worker_pid": os.getpid(),
        }

    @app.get("/api/quality/access/session")
    def session(request: Request):
        return {"principal": request.state.principal, "team_mode": access.enabled}

    @app.get("/api/quality/access/identities")
    def members(request: Request):
        workspace = request.state.principal["workspace"]
        return [r for r in access.list() if r["workspace"] == workspace]

    @app.post("/api/quality/access/identities", status_code=201)
    def create_member(body: MemberCreate, request: Request):
        result = access.create(body.name, body.role, request.state.principal["workspace"])
        access.audit(request.state.principal, "identity_created", result["id"])
        return result

    @app.post("/api/quality/access/identities/{identity}/revoke")
    def revoke_member(identity: str, request: Request):
        workspace = request.state.principal["workspace"]
        if not any(r["id"] == identity and r["workspace"] == workspace for r in access.list()):
            raise PermissionError("成员不属于当前工作区")
        access.revoke(identity)
        access.audit(request.state.principal, "identity_revoked", identity)
        return {"revoked": True}

    def require_main_workspace(request: Request):
        # The database and raw pages are shared by every workspace.
        if request.state.principal["workspace"] != "main":
            raise PermissionError("全库备份仅向主工作区管理员开放")

    @app.get("/api/quality/backups")
    def backups(request: Request):
        require_main_workspace(request)
        return operations.backups()

    @app.post("/api/quality/backups", status_code=201)
    def create_backup(request: Request):
        require_main_workspace(request)
        owner = operations.acquire("backup", "backup")
        with operations.heartbeat("backup", owner):
            result = operations.backup()
        access.audit(request.state.principal, "backup_created", result["id"])
        return result

    @app.get("/api/quality/games")
    def list_games():
        result = []
        for game in games.list():
            run = store.latest(game["key"])
            data = next(
                (
                    p
                    for p in (run or {}).get("report", {}).get("products", [])
                    if p["key"] == game["key"]
                ),
                None,
            )
            latest = data and {
                "run_id": run["id"],
                "as_of": run["report"]["as_of"],
                "reviews": data["recommendation"]["n"],
            }
            result.append({**game, "latest": latest})
        return result

    @app.get("/api/quality/games/search")
    def search_games(q: str = Query(min_length=1, max_length=100)):
        added = {g["app_id"] for g in games.list()}
        term = q.strip()
        results = lookup.search(term)
        if term.isdigit() and not any(r["app_id"] == int(term) for r in results):
            found = lookup.app(int(term))
            if found:
                results.insert(0, {"app_id": found["app_id"], "name": found["name"], "image": ""})
        return [{**r, "added": r["app_id"] in added} for r in results]

    def checked_repo(text: str) -> str:
        repo = normalize_repo(text)
        if repo and not lookup.repo_exists(repo):
            raise ValueError("GitHub 上找不到这个公开仓库：" + repo)
        return repo

    @app.post("/api/quality/games", status_code=201)
    def add_game(body: GameCreate, request: Request):
        found = check_reviewed(lookup.app(body.app_id), body.app_id)
        game = games.add(body.app_id, found["name"], checked_repo(body.repo))
        access.audit(request.state.principal, "game_added", game["key"])
        return game

    @app.patch("/api/quality/games/{key}")
    def update_game(key: str, body: GameUpdate, request: Request):
        game = games.set_repo(key, checked_repo(body.repo))
        access.audit(request.state.principal, "game_repo_changed", key)
        return game

    @app.delete("/api/quality/games/{key}")
    def remove_game(key: str, request: Request):
        games.remove(key)
        access.audit(request.state.principal, "game_removed", key)
        return {"removed": key}

    def choose_run(run_id: str | None):
        run = store.run(run_id) if run_id else store.latest()
        if not run or run["status"] != "completed":
            raise HTTPException(404, "没有可用的完成快照")
        return run

    @app.get("/api/quality/agent/status")
    def agent_status():
        return agents.status()

    @app.get("/api/quality/agent/conversations")
    def agent_conversations(run_id: str, product: str, request: Request):
        choose_run(run_id)
        return agents.list_conversations(run_id, product, request.state.principal["workspace"])

    @app.get("/api/quality/agent/conversations/{conversation_id}")
    def agent_history(conversation_id: str):
        return agents.turns(conversation_id)

    @app.post("/api/quality/agent/turns", status_code=202)
    def agent_start(body: AgentRequest, request: Request):
        try:
            return agents.submit(
                body, request.state.principal["workspace"], request.state.principal["id"]
            )
        except ConflictError:
            raise
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/quality/agent/turns/{turn_id}")
    def agent_turn(turn_id: str):
        try:
            return agents.get(turn_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/quality/agent/turns/{turn_id}/cancel")
    def agent_cancel(turn_id: str):
        return agents.cancel(turn_id)

    @app.get("/api/quality/snapshot")
    def snapshot(run_id: str | None = None, product: str | None = None):
        run = store.run(run_id) if run_id else store.latest(product)
        if not run:
            return {"status": "empty", "report": None}
        if run["status"] != "completed":
            raise HTTPException(409, "此任务尚未完成，不能发布为分析快照")
        return {"status": "ready", "report": run["report"]}

    @app.get("/api/quality/runs")
    def runs():
        return [{k: v for k, v in run.items() if k != "report"} for run in store.list_runs()]

    @app.get("/api/quality/runs/{run_id}")
    def run_status(run_id: str):
        run = store.run(run_id)
        if not run:
            raise HTTPException(404, "任务不存在")
        return {k: v for k, v in run.items() if k != "report"}

    @app.post("/api/quality/sync", status_code=202)
    def start_sync(body: SyncRequest):
        added = [g["key"] for g in games.list()]
        keys = body.products or added
        if not keys:
            raise HTTPException(422, "还没有添加游戏")
        unknown = [k for k in keys if k not in added]
        if unknown:
            raise HTTPException(422, "没有添加这些游戏：" + "、".join(unknown))
        return {"run_id": jobs.submit({**body.model_dump(), "products": keys}), "status": "queued"}

    @app.post("/api/quality/replay/{run_id}", status_code=202)
    def start_replay(run_id: str):
        run = choose_run(run_id)
        new_id = jobs.submit({**run["config"], "replayed_from": run_id}, original=run_id)
        return {"run_id": new_id, "status": "queued"}

    @app.get("/api/quality/evidence")
    def evidence(
        run_id: str | None = None,
        product: str | None = None,
        source: Literal["steam", "github_issues"] | None = None,
        category: str | None = None,
        language: str | None = None,
        recommended: bool | None = None,
        search: str = Query(default="", max_length=200),
        limit: int = Query(default=40, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ):
        run = choose_run(run_id)
        clauses, params = ["e.run_id=?"], [run["id"]]
        for column, value in [
            ("product", product),
            ("source", source),
            ("language", language),
            ("recommended", recommended),
        ]:
            if value is not None:
                clauses.append(f"e.{column}=?")
                params.append(value)
        if category is not None:
            if category not in CATEGORIES:
                raise HTTPException(422, "未知问题类型")
            clauses.append(
                "EXISTS(SELECT 1 FROM mentions m WHERE m.run_id=e.run_id AND m.evidence_id=e.id AND m.category=?)"
            )
            params.append(category)
        if search.strip():
            clauses.append("(e.title||' '||e.text) LIKE ? ESCAPE '\\'")
            escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.append("%" + escaped + "%")
        where = " AND ".join(clauses)
        total = store.query("SELECT COUNT(*) AS n FROM evidence e WHERE " + where, params)[0]["n"]
        rows = store.query(
            "SELECT e.* FROM evidence e WHERE "
            + where
            + " ORDER BY e.created_at DESC,e.id LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        categories = {}
        if rows:
            ids = [row["id"] for row in rows]
            for mention in store.query(
                f"SELECT evidence_id,category FROM mentions WHERE run_id=? AND evidence_id IN ({','.join('?' for _ in ids)}) ORDER BY category",
                (run["id"], *ids),
            ):
                categories.setdefault(mention["evidence_id"], []).append(mention["category"])
        for row in rows:
            row["text"] = row["text"][:900]
            row["labels"] = json.loads(row.pop("labels_json"))
            row["categories"] = categories.get(row["id"], [])
        return {"run_id": run["id"], "total": total, "limit": limit, "offset": offset, "rows": rows}

    @app.get("/api/quality/evidence/{evidence_id}")
    def detail(evidence_id: str, run_id: str | None = None):
        run = choose_run(run_id)
        rows = store.query(
            "SELECT * FROM evidence WHERE run_id=? AND id=?", (run["id"], evidence_id)
        )
        if not rows:
            raise HTTPException(404, "证据不存在")
        row = rows[0]
        row["labels"] = json.loads(row.pop("labels_json"))
        page = store.query("SELECT * FROM pages WHERE id=?", (row["page_id"],))[0]
        content = json.loads(store.read_raw(page["path"], page["sha256"]))
        record = content
        for part in row["json_pointer"].strip("/").split("/"):
            record = record[int(part)] if isinstance(record, list) else record[part]
        mentions = store.query(
            "SELECT category,cues_json FROM mentions WHERE run_id=? AND evidence_id=?",
            (run["id"], evidence_id),
        )
        for mention in mentions:
            mention["cues"] = json.loads(mention.pop("cues_json"))
        page_metadata = json.loads(page["metadata_json"])
        return {
            "evidence": row,
            "mentions": mentions,
            "lineage": {
                "page_id": page["id"],
                "sha256": page["sha256"],
                "path": page["path"],
                "request_url": page["url"],
                "fetched_at": page["fetched_at"],
                "source_fetched_at": page_metadata.get("original_fetched_at", page["fetched_at"]),
                "replayed_from": page_metadata.get("replayed_from"),
                "json_pointer": row["json_pointer"],
                "record": record,
            },
        }

    @app.get("/api/quality/pages/{page_id}")
    def raw_page(page_id: str):
        rows = store.query("SELECT * FROM pages WHERE id=?", (page_id,))
        if not rows:
            raise HTTPException(404, "原始页不存在")
        page = rows[0]
        return Response(
            store.read_raw(page["path"], page["sha256"]),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{page_id}.json"'},
        )

    @app.get("/api/quality/quality")
    def quality(run_id: str | None = None):
        run = choose_run(run_id)
        pages = [
            {k: v for k, v in p.items() if k not in ("headers_json", "metadata_json")}
            for p in store.pages(run["id"])
        ]
        quarantined = store.query(
            "SELECT product,source,json_pointer,reason,page_id FROM quarantine WHERE run_id=? ORDER BY id LIMIT 100",
            (run["id"],),
        )
        return {
            "run_id": run["id"],
            "fingerprint": run["fingerprint"],
            "pages": pages,
            "quarantine": quarantined,
            "products": [
                {"key": p["key"], "quality": p["quality"], "coverage": p["coverage"]}
                for p in run["report"]["products"]
            ],
        }

    @app.get("/api/quality/triage")
    def triage_list(request: Request):
        return [
            r for r in store.list_triage() if r["workspace"] == request.state.principal["workspace"]
        ]

    @app.post("/api/quality/triage", status_code=201)
    def create_triage(body: TriageCreate, request: Request):
        run = choose_run(body.run_id)
        try:
            return store.create_triage(
                run["id"],
                body.product,
                body.title,
                body.evidence_ids,
                body.owner,
                body.note,
                request.state.principal["workspace"],
                request.state.principal["name"],
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.patch("/api/quality/triage/{triage_id}")
    def update_triage(triage_id: str, body: TriageUpdate, request: Request):
        try:
            return store.update_triage(
                triage_id,
                body.revision,
                body.status,
                body.owner,
                body.note,
                request.state.principal["name"],
            )
        except ConflictError:
            raise
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/quality/export")
    def export(
        run_id: str | None = None,
        format: Literal["csv", "json"] = "json",
        product: str | None = None,
    ):
        run = choose_run(run_id)
        if format == "json":
            return Response(
                json.dumps(run["report"], ensure_ascii=False, allow_nan=False),
                media_type="application/json",
                headers={
                    "Content-Disposition": f'attachment; filename="gamepulse-{run["id"]}.json"'
                },
            )
        return Response(
            csv_bytes(
                evidence_rows(store, run["id"], product), ["id", "product", "source", "source_url"]
            ),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="gamepulse-{run["id"]}.csv"'},
        )

    build = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if serve_frontend and build.is_dir():
        app.mount("/", StaticFiles(directory=build, html=True), name="frontend")
    app.state.store = store
    app.state.jobs = jobs
    app.state.access = access
    app.state.games = games
    return app
