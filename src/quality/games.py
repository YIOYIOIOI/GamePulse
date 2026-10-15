"""The games GamePulse monitors: a Steam app and, optionally, its public GitHub repository."""

from __future__ import annotations

import re
import sqlite3
import unicodedata

import httpx

from src.quality.contracts import Product, iso, utc_now
from src.quality.store import ConflictError, Store

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
 key TEXT PRIMARY KEY, name TEXT NOT NULL, app_id INTEGER NOT NULL UNIQUE,
 repo TEXT NOT NULL DEFAULT '', added_at TEXT NOT NULL
);
"""
REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9._-]{1,100}")
STORE_REGIONS = ("CN", "US")
# Steam app types that have player reviews; soundtracks, videos and demos do not.
REVIEWED_TYPES = {"game", "dlc"}


def check_reviewed(found: dict | None, app_id: int) -> dict:
    """The Steam app to monitor, or a readable reason why it cannot be."""
    if not found:
        raise ValueError(f"Steam 上找不到 App ID {app_id}")
    if found.get("type") not in REVIEWED_TYPES:
        raise ValueError(f"「{found['name']}」不是游戏或 DLC，没有玩家评论；请选择游戏本体")
    return found


def normalize_repo(text: str) -> str:
    """Returns owner/name from that form or from a github.com URL; empty input means no repository."""
    value = text.strip()
    if not value:
        return ""
    value = re.sub(r"^(?:https?://)?(?:www\.)?github\.com/", "", value, flags=re.IGNORECASE)
    value = "/".join(value.removesuffix(".git").strip("/").split("/")[:2])
    if not REPO.fullmatch(value):
        raise ValueError("GitHub 仓库请填写 owner/name 或仓库链接，例如 Anuken/Mindustry")
    return value


def game_key(name: str, app_id: int, taken: set[str], previous: str | None = None) -> str:
    """A readable key for URLs and the CLI: the Latin part of the name, else app-<id>.

    A game added again gets its previous key back, so its snapshots and follow-ups reattach.
    """
    if previous and previous not in taken:
        return previous
    latin = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", latin.lower()).strip("-")[:40].strip("-")
    key = base if len(base) >= 3 else f"app-{app_id}"
    return f"{key}-{app_id}" if key in taken else key


class Games:
    def __init__(self, store: Store):
        self.store = store
        with store.connect() as conn:
            conn.executescript(SCHEMA)

    def list(self) -> list[dict]:
        return self.store.query("SELECT * FROM games ORDER BY added_at,rowid")

    def get(self, key: str) -> Product:
        rows = self.store.query("SELECT key,name,app_id,repo FROM games WHERE key=?", (key,))
        if not rows:
            raise ValueError(f"没有添加游戏：{key}")
        return Product(**rows[0])

    def add(self, app_id: int, name: str, repo: str) -> dict:
        with self.store.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM games WHERE app_id=?", (app_id,)).fetchone():
                raise ConflictError("这款游戏已经添加过了")
            taken = {r[0] for r in conn.execute("SELECT key FROM games")}
            # Keys a removed game used in earlier snapshots stay reserved for that Steam app,
            # otherwise a different game could inherit its snapshots and follow-ups.
            previous = None
            for used, used_app in conn.execute(
                "SELECT g.key,json_extract(g.value,'$.app_id') FROM runs,"
                "json_each(runs.config_json,'$.games') g"
            ):
                if used_app == app_id:
                    previous = previous or used
                else:
                    taken.add(used)
            key = game_key(name, app_id, taken, previous)
            try:
                conn.execute(
                    "INSERT INTO games(key,name,app_id,repo,added_at) VALUES(?,?,?,?,?)",
                    (key, name, app_id, repo, iso(utc_now())),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError("这款游戏已经添加过了") from exc
        return self.store.query("SELECT * FROM games WHERE key=?", (key,))[0]

    def set_repo(self, key: str, repo: str) -> dict:
        self.get(key)
        with self.store.connect() as conn:
            conn.execute("UPDATE games SET repo=? WHERE key=?", (repo, key))
        return self.store.query("SELECT * FROM games WHERE key=?", (key,))[0]

    def remove(self, key: str) -> None:
        """Stops monitoring the game. Snapshots that already include it are kept."""
        self.get(key)
        with self.store.connect() as conn:
            conn.execute("DELETE FROM games WHERE key=?", (key,))


class GameLookup:
    """Steam and GitHub lookups used while adding a game; none of this enters a snapshot."""

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(15, connect=10),
            follow_redirects=True,
            headers={"User-Agent": "GamePulse/0.2 player-feedback monitoring"},
        )

    def close(self):
        self.client.close()

    def _get(self, url: str, params: dict | None = None, headers: dict | None = None):
        try:
            return self.client.get(url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise ConnectionError("暂时连不上 Steam 或 GitHub，请稍后再试") from exc

    def search(self, term: str) -> list[dict]:
        items = []
        # Chinese names come from the CN store; the US store also lists games not sold in China.
        for region in STORE_REGIONS:
            response = self._get(
                "https://store.steampowered.com/api/storesearch/",
                {"term": term, "l": "schinese", "cc": region},
            )
            if response.status_code != 200:
                raise ConnectionError(f"Steam 搜索返回 HTTP {response.status_code}")
            items = response.json().get("items", [])
            if items:
                break
        return [
            {"app_id": item["id"], "name": item["name"], "image": item.get("tiny_image", "")}
            for item in items
            if item.get("type") == "app" and isinstance(item.get("id"), int)
        ][:10]

    def app(self, app_id: int) -> dict | None:
        for region in STORE_REGIONS:
            response = self._get(
                "https://store.steampowered.com/api/appdetails",
                {"appids": app_id, "l": "schinese", "cc": region},
            )
            if response.status_code != 200:
                raise ConnectionError(f"Steam 返回 HTTP {response.status_code}")
            entry = (response.json() or {}).get(str(app_id), {})
            data = entry.get("data") or {}
            if entry.get("success") is True and data.get("name"):
                return {"app_id": app_id, "name": data["name"], "type": data.get("type", "")}
        return None

    def canonical_repo(self, repo: str) -> str | None:
        """owner/name as GitHub now reports it (after renames and case fixes), or None."""
        response = self._get(
            f"https://api.github.com/repos/{repo}",
            headers={"Accept": "application/vnd.github+json"},
        )
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise ConnectionError(f"GitHub 返回 HTTP {response.status_code}")
        body = response.json()
        return None if body.get("private", False) else body.get("full_name") or repo


def checked_repo(lookup: GameLookup, text: str) -> str:
    """The canonical public repository for user input; empty input means no repository."""
    repo = normalize_repo(text)
    if not repo:
        return ""
    canonical = lookup.canonical_repo(repo)
    if not canonical:
        raise ValueError("GitHub 上找不到这个公开仓库：" + repo)
    return canonical
