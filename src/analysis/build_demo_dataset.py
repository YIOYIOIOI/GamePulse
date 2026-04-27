"""Build a product-demo dataset from existing local analysis artifacts.

This does not fabricate reviews. It only merges already collected/analyzed local
CSV files and adds a game_name label derived from file names so the competitor
monitor can operate on real available records.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd


DEFAULT_SOURCES = [
    ("DOTA 2", "data/results/DOTA2_100K_20260313_205835_cleaned_sentiment_topic.csv"),
    ("Grand Theft Auto V", "data/results/Grand_Theft_Auto_V_20260313_194420_cleaned_sentiment_topic.csv"),
]


def load_source(game_name: str, path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.copy()
    df["game_name"] = game_name
    df["source_file"] = str(path)
    return df


def build_demo_dataset(sources: Iterable[tuple[str, str]], output: Path) -> pd.DataFrame:
    frames = []
    for game_name, src in sources:
        path = Path(src)
        if path.exists():
            frames.append(load_source(game_name, path))
    if not frames:
        raise FileNotFoundError("No source CSV files found for demo dataset")

    # Align columns across games while preserving available evidence fields.
    df = pd.concat(frames, ignore_index=True, sort=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False, encoding="utf-8-sig")
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/results/gamepulse_demo_competitor_dataset.csv")
    args = parser.parse_args()
    df = build_demo_dataset(DEFAULT_SOURCES, Path(args.output))
    print(f"output={args.output}")
    print(f"rows={len(df)}")
    print(f"games={df['game_name'].nunique()}")


if __name__ == "__main__":
    main()
