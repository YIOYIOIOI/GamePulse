"""Smoke test Steam game-name search.

Run:
    python scripts/smoke_steam_search.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_collection.steam_light_collector import search_steam_apps  # noqa: E402


def main() -> None:
    results, status = search_steam_apps("dota 2", limit=5)
    assert status["ok"], status
    assert results, status
    assert any(int(r["app_id"]) == 570 for r in results), results
    print("steam_search_smoke=ok")
    print(results[:3])


if __name__ == "__main__":
    main()
