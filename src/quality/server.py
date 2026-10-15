"""Multiprocess entry: uvicorn src.quality.server:build --factory --workers 2."""

import os

from src.quality.api import create_app
from src.quality.cli import default_root
from src.quality.store import Store


def build():
    return create_app(
        Store(default_root()),
        port=int(os.environ.get("GAMEPULSE_PORT", "8767")),
        team=os.environ.get("GAMEPULSE_TEAM", "0") == "1",
    )
