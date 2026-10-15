"""python -m src.quality.cli sync | replay | verify | serve | member | backup | restore-drill."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from src.quality.contracts import SyncRequest
from src.quality.pipeline import replay, sync
from src.quality.store import Store


def default_root() -> Path:
    return Path(
        os.environ.get("GAMEPULSE_DATA_DIR", str(Path(__file__).resolve().parents[2] / "var"))
    ).resolve()


def main():
    parser = argparse.ArgumentParser(description="GamePulse 玩家反馈监控")
    parser.add_argument("--data-dir", type=Path, default=default_root())
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("sync")
    collect.add_argument("--products", nargs="+", default=[], help="游戏 key；默认全部已添加的游戏")
    collect.add_argument("--days", type=int, default=180)
    collect.add_argument("--max-reviews", type=int, default=6000)
    collect.add_argument("--max-issue-pages", type=int, default=4)
    repeated = commands.add_parser("replay")
    repeated.add_argument("run_id")
    verify = commands.add_parser("verify")
    verify.add_argument("run_id", nargs="?")
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8767)
    serve.add_argument("--team", action="store_true")
    member = commands.add_parser("member")
    member.add_argument("--name", required=True)
    member.add_argument("--role", choices=["owner", "reviewer", "analyst", "viewer"], required=True)
    member.add_argument("--workspace", default="main")
    game = commands.add_parser("game", help="查看、添加或移除要监控的游戏")
    game_commands = game.add_subparsers(dest="action", required=True)
    game_commands.add_parser("list")
    add = game_commands.add_parser("add")
    add.add_argument("app_id", type=int, help="Steam App ID")
    add.add_argument("--repo", default="", help="GitHub 仓库 owner/name，可选")
    remove = game_commands.add_parser("remove")
    remove.add_argument("key")
    commands.add_parser("backup")
    restore = commands.add_parser("restore-drill")
    restore.add_argument("backup_id")
    args = parser.parse_args()
    store = Store(args.data_dir)
    if args.command == "serve":
        import uvicorn

        from src.quality.api import create_app

        uvicorn.run(
            create_app(store, port=args.port, team=args.team), host="127.0.0.1", port=args.port
        )
        return
    if args.command == "game":
        from src.quality.games import GameLookup, Games, check_reviewed, normalize_repo

        games = Games(store)
        if args.action == "add":
            lookup = GameLookup()
            try:
                found = check_reviewed(lookup.app(args.app_id), args.app_id)
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
            repo = normalize_repo(args.repo)
            if repo and not lookup.repo_exists(repo):
                raise SystemExit("GitHub 上找不到这个公开仓库：" + repo)
            print(json.dumps(games.add(args.app_id, found["name"], repo), ensure_ascii=False))
        elif args.action == "remove":
            games.remove(args.key)
            print(json.dumps({"removed": args.key}))
        else:
            print(json.dumps(games.list(), ensure_ascii=False, indent=2))
        return
    if args.command == "member":
        from src.quality.access import Access

        print(
            json.dumps(
                Access(store).create(args.name, args.role, args.workspace),
                ensure_ascii=False,
            )
        )
        return
    if args.command in ("backup", "restore-drill"):
        from src.quality.operations import Operations

        operation = Operations(store)
        print(
            json.dumps(
                operation.backup()
                if args.command == "backup"
                else operation.restore_drill(args.backup_id),
                ensure_ascii=False,
            )
        )
        return
    if args.command == "verify":
        run = store.run(args.run_id) if args.run_id else store.latest()
        if not run:
            raise SystemExit("No completed snapshot")
        pages = store.pages(run["id"])
        for page in pages:
            store.read_raw(page["path"], page["sha256"])
        print(
            json.dumps(
                {
                    "run_id": run["id"],
                    "status": run["status"],
                    "raw_sha_verified": len(pages),
                    "fingerprint": run["fingerprint"],
                },
                ensure_ascii=False,
            )
        )
        return
    if args.command == "sync" and not args.products:
        from src.quality.games import Games

        if not Games(store).list():
            raise SystemExit("还没有添加游戏：先运行 game add <Steam App ID>")
    from src.quality.operations import Operations

    operation = Operations(store)
    store.recover_interrupted()
    owner = operation.acquire("collection", "preparing")
    try:
        if args.command == "sync":
            config = SyncRequest(
                products=args.products,
                days=args.days,
                max_reviews=args.max_reviews,
                max_issue_pages=args.max_issue_pages,
            ).model_dump()
        else:
            original = store.run(args.run_id)
            if not original or original["status"] != "completed":
                raise ValueError("只能重放完成快照")
            config = {**original["config"], "replayed_from": args.run_id}
        run_id = store.new_run(config, ("collection", owner))
        print(json.dumps({"run_id": run_id, "status": "started"}), flush=True)
        with operation.heartbeat("collection", owner):
            report = (
                sync(store, run_id, config)
                if args.command == "sync"
                else replay(store, args.run_id, run_id)
            )
    except Exception:
        operation.release("collection", owner)
        raise
    print(
        json.dumps(
            {
                "run_id": report["run_id"],
                "fingerprint": report["fingerprint"],
                "products": [
                    {
                        "name": p["name"],
                        "reviews": p["recommendation"]["n"],
                        "issues": p["issues"],
                        "complete": p["coverage"]["steam"]["complete"],
                        "quarantined": p["quality"]["quarantined"],
                    }
                    for p in report["products"]
                ],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
