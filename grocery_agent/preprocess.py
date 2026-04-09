"""Dataset cleaning for the grocery recommendation MVP."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd


TEXT_COLUMNS = [
    "title",
    "sub_category",
    "feature",
    "product_description",
    "discount",
    "currency",
]


def _ensure_column(df: pd.DataFrame, column: str, default: Any) -> pd.DataFrame:
    """Add a missing column so downstream steps can fail gracefully."""
    if column not in df.columns:
        df[column] = default
    return df


def clean_text(value: Any) -> str:
    """Normalize free text fields."""
    if pd.isna(value):
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_price(value: Any) -> float:
    """Convert price strings like '$14.99' into floats."""
    if pd.isna(value):
        return float("nan")
    text = str(value)
    match = re.search(r"(\d+(?:\.\d+)?)", text.replace(",", ""))
    return float(match.group(1)) if match else float("nan")


def parse_rating(value: Any) -> float:
    """Extract a numeric rating from text such as 'Rated 4.3 out of 5 stars'."""
    if pd.isna(value):
        return float("nan")
    text = str(value)
    match = re.search(r"(\d+(?:\.\d+)?)\s*out of\s*5", text.lower())
    if match:
        return float(match.group(1))
    fallback = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(fallback.group(1)) if fallback else float("nan")


def parse_discount_amount(value: Any) -> float:
    """Extract discount amount from strings such as 'After $5 OFF'."""
    if pd.isna(value):
        return 0.0
    text = str(value).strip().lower()
    if not text or "no discount" in text:
        return 0.0
    match = re.search(r"(\d+(?:\.\d+)?)", text.replace(",", ""))
    return float(match.group(1)) if match else 0.0


def preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the main grocery dataset fields and return a recommendation-ready DataFrame.

    This function tolerates missing source columns by creating sensible defaults.
    """
    working = df.copy()

    for column in [
        "title",
        "sub_category",
        "price",
        "rating",
        "discount",
        "feature",
        "product_description",
        "currency",
    ]:
        _ensure_column(working, column, "")

    for column in TEXT_COLUMNS:
        working[column] = working[column].apply(clean_text)

    working["price"] = working["price"].apply(parse_price)
    working["rating"] = working["rating"].apply(parse_rating)
    working["discount_amount"] = working["discount"].apply(parse_discount_amount)

    working["title"] = working["title"].replace("", "Untitled product")
    working["sub_category"] = working["sub_category"].replace("", "unknown")
    working["feature"] = working["feature"].fillna("")
    working["product_description"] = working["product_description"].fillna("")

    # For an MVP, use simple imputations that keep items eligible instead of dropping too much data.
    median_price = working["price"].median()
    working["price"] = working["price"].fillna(median_price if pd.notna(median_price) else 0.0)
    working["discount_amount"] = working["discount_amount"].fillna(0.0)

    working = working.drop_duplicates()
    working = working.drop_duplicates(subset=["title", "sub_category", "price"])

    return working.reset_index(drop=True)
