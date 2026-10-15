"""Adding, linking and removing monitored games. Steam and GitHub lookups are stubbed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_quality_workflow import GAME, WINDOW

from src.quality.api import create_app
from src.quality.games import Games, game_key, normalize_repo
from src.quality.pipeline import sync
from src.quality.store import Store


class FakeLookup:
    """Answers like Steam and GitHub would for a few known ids."""

    apps = {
        1127400: "Mindustry",
        2358720: "黑神话：悟空",
        598190: "Hollow Knight - Official Soundtrack",
    }
    repos = {"Anuken/Mindustry"}

    def search(self, term):
        return [
            {"app_id": app_id, "name": name, "image": ""}
            for app_id, name in self.apps.items()
            if term.lower() in name.lower()
        ]

    def app(self, app_id):
        name = self.apps.get(app_id)
        kind = "music" if "Soundtrack" in (name or "") else "game"
        return {"app_id": app_id, "name": name, "type": kind} if name else None

    def repo_exists(self, repo):
        return repo in self.repos


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", ""),
        ("Anuken/Mindustry", "Anuken/Mindustry"),
        ("https://github.com/Anuken/Mindustry", "Anuken/Mindustry"),
        ("github.com/Anuken/Mindustry.git", "Anuken/Mindustry"),
        ("https://github.com/Anuken/Mindustry/issues/12", "Anuken/Mindustry"),
    ],
)
def test_repository_accepts_owner_name_or_url(text, expected):
    assert normalize_repo(text) == expected


@pytest.mark.parametrize("text", ["Mindustry", "https://gitlab.com/a/b", "a b/c", "/x"])
def test_repository_rejects_anything_else(text):
    with pytest.raises(ValueError):
        normalize_repo(text)


def test_game_keys_are_readable_and_unique():
    assert game_key("Battle for Wesnoth", 599390, set()) == "battle-for-wesnoth"
    assert game_key("黑神话：悟空", 2358720, set()) == "app-2358720"
    assert game_key("Mindustry", 1127400, {"mindustry"}) == "mindustry-1127400"


def test_admin_adds_links_and_removes_games(tmp_path):
    app = create_app(Store(tmp_path), serve_frontend=False, lookup=FakeLookup())
    with TestClient(app) as client:
        assert client.get("/api/quality/games").json() == []
        assert client.post("/api/quality/sync", json={}).status_code == 422
        added = client.post("/api/quality/games", json={"app_id": 2358720})
        assert added.status_code == 201
        assert added.json()["key"] == "app-2358720" and added.json()["repo"] == ""
        assert client.post("/api/quality/games", json={"app_id": 2358720}).status_code == 409
        assert client.post("/api/quality/games", json={"app_id": 42}).status_code == 422
        soundtrack = client.post("/api/quality/games", json={"app_id": 598190})
        assert soundtrack.status_code == 422 and "不是游戏" in soundtrack.json()["detail"]
        bad_repo = {"app_id": 1127400, "repo": "Anuken/NotThere"}
        assert client.post("/api/quality/games", json=bad_repo).status_code == 422
        game = client.post(
            "/api/quality/games",
            json={"app_id": 1127400, "repo": "https://github.com/Anuken/Mindustry"},
        ).json()
        assert game["key"] == "mindustry" and game["repo"] == "Anuken/Mindustry"
        found = client.get("/api/quality/games/search?q=mind").json()
        assert found == [{"app_id": 1127400, "name": "Mindustry", "image": "", "added": True}]
        assert client.patch("/api/quality/games/mindustry", json={"repo": ""}).json()["repo"] == ""
        unknown = client.post("/api/quality/sync", json={"products": ["openttd"]})
        assert unknown.status_code == 422
        assert client.delete("/api/quality/games/mindustry").status_code == 200
        assert [g["key"] for g in client.get("/api/quality/games").json()] == ["app-2358720"]


def test_only_admins_change_games(tmp_path):
    store = Store(tmp_path)
    app = create_app(store, serve_frontend=False, team=True, lookup=FakeLookup())
    viewer = app.state.access.create("fixture viewer", "viewer", "main")
    headers = {
        "Authorization": "Bearer " + Path(viewer["token_file"]).read_text(),
        "X-Workspace-ID": "main",
    }
    with TestClient(app) as client:
        assert client.get("/api/quality/games", headers=headers).status_code == 200
        assert client.get("/api/quality/games/search?q=m", headers=headers).status_code == 403
        assert (
            client.post("/api/quality/games", headers=headers, json={"app_id": 1127400}).status_code
            == 403
        )


class SteamOnlyCollector:
    """Returns the captured Steam window and fails if any GitHub source is requested."""

    def __init__(self, store, run_id, progress=None):
        self.store, self.run_id = store, run_id

    def identity(self, product):
        return {"steam_name": product.name, "developers": [], "repository": product.repo}

    def steam(self, product, start, end, max_reviews):
        page = self.store.save_page(
            self.run_id,
            product.key,
            "steam",
            1,
            "https://api.steampowered.com/captured",
            json.dumps(WINDOW["first"], ensure_ascii=False).encode(),
            200,
            {},
            {},
        )
        reviews = WINDOW["first"]["response"]["reviews"]
        rows = [(row, page, f"/response/reviews/{i}") for i, row in enumerate(reviews)]
        coverage = {
            "source": "steam",
            "pages": 1,
            "raw_rows": len(rows),
            "complete": True,
            "stop_reason": "test_capture_end",
            "scope": "测试捕获",
        }
        return rows, coverage

    def github(self, *args):
        raise AssertionError("a game without a repository must not query GitHub")

    def close(self):
        pass


SYNC_REQUEST = {"products": [], "days": 730, "max_reviews": 6000, "max_issue_pages": 4}


def test_game_without_repository_syncs_steam_only(tmp_path):
    store = Store(tmp_path)
    Games(store).add(GAME.app_id, GAME.name, "")
    run_id = store.new_run(SYNC_REQUEST)
    report = sync(store, run_id, SYNC_REQUEST, collector_factory=SteamOnlyCollector)
    product = report["products"][0]
    assert product["key"] == GAME.key and product["repo"] == ""
    assert product["coverage"]["github_issues"]["stop_reason"] == "not_linked"
    assert not product["quality"]["warnings"] or all(
        "GitHub" not in w for w in product["quality"]["warnings"]
    )
    # The snapshot keeps the definition it used, so removing the game later changes nothing.
    assert store.run(run_id)["config"]["games"][GAME.key]["app_id"] == GAME.app_id


def test_each_game_shows_its_own_latest_snapshot(tmp_path):
    store = Store(tmp_path)
    games = Games(store)
    games.add(GAME.app_id, GAME.name, "")
    other = games.add(2358720, "黑神话：悟空", "")["key"]
    first = store.new_run({})
    sync(store, first, {**SYNC_REQUEST, "products": [GAME.key]}, SteamOnlyCollector)
    # A later sync of another game alone must not hide this game's data.
    second = store.new_run({})
    sync(store, second, {**SYNC_REQUEST, "products": [other]}, SteamOnlyCollector)
    assert store.latest()["id"] == second
    assert store.latest(GAME.key)["id"] == first
    app = create_app(store, serve_frontend=False, lookup=FakeLookup())
    with TestClient(app) as client:
        snapshot = client.get(f"/api/quality/snapshot?product={GAME.key}").json()
        assert snapshot["report"]["run_id"] == first
        listed = {g["key"]: g["latest"] for g in client.get("/api/quality/games").json()}
        assert listed[GAME.key]["run_id"] == first and listed[other]["run_id"] == second
        assert listed[GAME.key]["reviews"] > 0
