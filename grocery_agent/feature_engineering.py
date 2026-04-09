"""Feature engineering for lightweight grocery recommendations."""

from __future__ import annotations

import re

import pandas as pd


PROTEIN_KEYWORDS = [
    "protein",
    "chicken",
    "tuna",
    "salmon",
    "greek yogurt",
    "yogurt",
    "eggs",
    "egg",
    "jerky",
    "nuts",
    "almond",
    "peanut",
    "turkey",
    "beef",
    "tofu",
    "beans",
]

SUGAR_HIGH_KEYWORDS = [
    "candy",
    "cake",
    "cookies",
    "cookie",
    "soda",
    "juice",
    "chocolate",
    "dessert",
    "sweet",
    "brownie",
    "frosting",
    "ice cream",
    "caramel",
    "cupcake",
    "cola",
    "vanilla",
    "drink mix",
]

BREAKFAST_SUGAR_WARNING_KEYWORDS = [
    "honey",
    "chocolate",
    "frosted",
    "sweet",
    "syrup",
    "maple",
]

SUGAR_LOW_KEYWORDS = [
    "unsweetened",
    "no sugar",
    "sugar free",
    "low sugar",
    "plain yogurt",
    "sparkling water",
    "purified water",
]

MEAL_TYPE_RULES = {
    "breakfast": ["oatmeal", "cereal", "granola", "yogurt", "pancake", "breakfast", "waffle", "egg"],
    "snack": ["snack", "chips", "cracker", "trail mix", "jerky", "bar", "popcorn", "nuts"],
    "pantry": ["rice", "pasta", "beans", "oil", "flour", "sauce", "pantry", "spice", "seasoning"],
    "dessert": ["dessert", "cake", "cookie", "brownie", "candy", "chocolate", "ice cream", "sweet"],
    "beverage": ["drink", "beverage", "water", "coffee", "tea", "juice", "soda", "sparkling"],
}


def _normalize_category(value: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"&", " and ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _estimate_protein_level(text: str) -> str:
    hits = sum(keyword in text for keyword in PROTEIN_KEYWORDS)
    if hits >= 2:
        return "high"
    if hits == 1:
        return "medium"
    return "low"


def _estimate_sugar_level(text: str) -> str:
    if _contains_any(text, SUGAR_LOW_KEYWORDS):
        return "low"
    if "water" in text and not _contains_any(text, SUGAR_HIGH_KEYWORDS):
        return "low"
    high_hits = sum(keyword in text for keyword in SUGAR_HIGH_KEYWORDS)
    if high_hits >= 2:
        return "high"
    if high_hits == 1:
        return "medium"
    return "medium"


def _infer_meal_types(text: str, category: str) -> list[str]:
    combined = f"{text} {category}".strip()
    tags = [meal_type for meal_type, keywords in MEAL_TYPE_RULES.items() if _contains_any(combined, keywords)]
    if tags:
        return tags
    if "pantry" in category:
        return ["pantry"]
    return []


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create simple engineered fields for recommendation and rule-based search."""
    working = df.copy()

    for column in ["title", "feature", "product_description", "sub_category", "price", "rating", "discount_amount"]:
        if column not in working.columns:
            working[column] = "" if column in {"title", "feature", "product_description", "sub_category"} else 0

    working["category_normalized"] = working["sub_category"].fillna("").map(_normalize_category)
    working["text_blob"] = (
        working["title"].fillna("")
        + " "
        + working["feature"].fillna("")
        + " "
        + working["product_description"].fillna("")
    ).str.lower().str.replace(r"\s+", " ", regex=True).str.strip()

    working["budget_flag"] = working["price"].fillna(0).le(20)
    working["discount_flag"] = working["discount_amount"].fillna(0).gt(0)
    working["high_rating_flag"] = working["rating"].ge(4.2).fillna(False)

    working["estimated_protein_level"] = working["text_blob"].map(_estimate_protein_level)
    working["estimated_sugar_level"] = working["text_blob"].map(_estimate_sugar_level)
    working["meal_type_tags"] = [
        _infer_meal_types(text_blob, category)
        for text_blob, category in zip(working["text_blob"], working["category_normalized"])
    ]

    working["health_score"] = 0.0
    working["health_score"] += working["estimated_protein_level"].map({"high": 2.0, "medium": 1.0, "low": 0.0})
    working["health_score"] += working["estimated_sugar_level"].map({"low": 2.0, "medium": 0.5, "high": -1.5})
    working["health_score"] += working["rating"].ge(4.2).fillna(False).astype(float) * 1.5
    working["health_score"] -= working["category_normalized"].str.contains(
        "candy|bakery|dessert|cleaning|laundry|paper|plastic|household|floral", regex=True, na=False
    ).astype(float) * 2.0
    working["health_score"] -= working["text_blob"].str.contains(
        "cat food|dog food|pet food|pet", regex=True, na=False
    ).astype(float) * 4.0

    breakfast_mask = working["meal_type_tags"].apply(lambda tags: "breakfast" in tags if isinstance(tags, list) else False)
    breakfast_sugar_mask = working["text_blob"].str.contains(
        "|".join(BREAKFAST_SUGAR_WARNING_KEYWORDS), regex=True, na=False
    )
    working.loc[breakfast_mask & breakfast_sugar_mask, "estimated_sugar_level"] = "high"
    working.loc[breakfast_mask & breakfast_sugar_mask, "health_score"] -= 2.0

    return working
