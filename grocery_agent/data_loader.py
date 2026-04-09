"""Utilities for loading the grocery dataset."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd


EXPECTED_COLUMNS = {
    "sub_category",
    "price",
    "discount",
    "rating",
    "title",
    "currency",
    "feature",
    "product_description",
}


def to_snake_case(value: str) -> str:
    """Convert a column name into snake_case."""
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def find_main_csv(search_dir: str | Path = ".") -> Path:
    """
    Find the most likely grocery CSV in a directory.

    Preference order:
    1. CSVs with the most expected grocery-style columns.
    2. Larger files as a tie-breaker.
    """
    search_path = Path(search_dir)
    csv_files = sorted(search_path.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {search_path.resolve()}")

    best_path: Optional[Path] = None
    best_score = (-1, -1)

    for csv_path in csv_files:
        try:
            sample = pd.read_csv(csv_path, nrows=5)
            standardized = {to_snake_case(col) for col in sample.columns}
            overlap = len(EXPECTED_COLUMNS & standardized)
            score = (overlap, csv_path.stat().st_size)
            if score > best_score:
                best_score = score
                best_path = csv_path
        except Exception:
            continue

    if best_path is None:
        raise FileNotFoundError("CSV files were found, but none could be read safely.")

    return best_path


def standardize_columns(columns: Iterable[str]) -> list[str]:
    """Standardize raw column names into snake_case."""
    return [to_snake_case(col) for col in columns]


def load_dataset(csv_path: str | Path | None = None, search_dir: str | Path = ".") -> pd.DataFrame:
    """
    Load the grocery dataset and standardize column names.

    If ``csv_path`` is not provided, the loader tries to detect the most likely CSV.
    """
    dataset_path = Path(csv_path) if csv_path else find_main_csv(search_dir)
    df = pd.read_csv(dataset_path)
    df.columns = standardize_columns(df.columns)
    return df

