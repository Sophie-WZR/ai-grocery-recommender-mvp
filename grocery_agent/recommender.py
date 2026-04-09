"""Rule-based recommendation pipeline for grocery products."""

from __future__ import annotations

from typing import Any

import pandas as pd


EDIBLE_CATEGORY_PATTERNS = [
    "snack",
    "breakfast",
    "pantry",
    "beverage",
    "water",
    "bakery",
    "dessert",
    "meat",
    "seafood",
    "deli",
    "coffee",
    "organic",
    "candy",
]

NON_EDIBLE_CATEGORY_PATTERNS = [
    "cleaning",
    "laundry",
    "household",
    "paper",
    "plastic",
    "floral",
]


def _safe_contains(series: pd.Series, needle: str) -> pd.Series:
    return series.fillna("").str.contains(needle, case=False, regex=False)


def has_query_signal(query: dict[str, Any]) -> bool:
    """Return True when the parser extracted meaningful constraints or search terms."""
    return any(
        [
            query.get("subcategory"),
            query.get("category_hint"),
            query.get("edible_only"),
            query.get("meal_type"),
            query.get("max_price") is not None,
            query.get("min_rating") is not None,
            query.get("discount_only"),
            query.get("healthy_intent"),
            query.get("protein_level"),
            query.get("sugar_level"),
            bool(query.get("text_terms")),
        ]
    )


def build_no_result_message(query: dict[str, Any], original_text: str | None = None) -> str:
    """Create a user-facing message for weak or out-of-domain queries."""
    if not has_query_signal(query):
        return "Sorry, I couldn't understand your request. Try something like 'snacks' or 'low sugar items'."

    category_hint = query.get("category_hint")
    text_terms = query.get("text_terms", [])
    if category_hint or text_terms:
        search_label = original_text or "that item"
        return f"I couldn't find a strong match for '{search_label}' in this grocery catalog."

    return "No matching products found for the current filters."


def _build_explanation(row: pd.Series, query: dict[str, Any]) -> str:
    reasons: list[str] = []

    max_price = query.get("max_price")
    min_rating = query.get("min_rating")
    protein_level = query.get("protein_level")
    sugar_level = query.get("sugar_level")
    meal_type = query.get("meal_type")

    if max_price is not None and row.get("price", 0) <= max_price:
        reasons.append("it is under your budget")
    if min_rating is not None and pd.notna(row.get("rating")) and row.get("rating", 0) >= min_rating:
        reasons.append("it has a strong rating")
    elif pd.notna(row.get("rating")) and row.get("rating", 0) >= 4.2:
        reasons.append("it has a strong rating")
    if query.get("healthy_intent") and row.get("health_score", 0) >= 2.5:
        reasons.append("it looks like a healthier option based on our simple heuristics")
    if query.get("discount_only") and row.get("discount_flag", False):
        reasons.append("it is currently discounted")
    if protein_level and row.get("estimated_protein_level") == protein_level:
        reasons.append(f"it is estimated as {protein_level} protein from title and description keywords")
    if sugar_level and row.get("estimated_sugar_level") == sugar_level:
        reasons.append(f"it is estimated as {sugar_level} sugar from title and description keywords")
    if meal_type and meal_type in row.get("meal_type_tags", []):
        reasons.append(f"it fits your {meal_type} use case")

    if not reasons:
        reasons.append("it is one of the strongest overall matches in the catalog")

    return "Recommended because " + ", ".join(reasons[:-1] + [reasons[-1] if len(reasons) == 1 else f"and {reasons[-1]}"]) + "."


def recommend_products(df: pd.DataFrame, query: dict[str, Any], top_n: int = 5) -> pd.DataFrame:
    """
    Filter and rank grocery products from a structured query.

    The function is intentionally simple and readable for MVP/demo use.
    """
    working = df.copy()

    text_terms = [term for term in query.get("text_terms", []) if term]
    has_structured_filters = any(
        [
            query.get("subcategory"),
            query.get("category_hint"),
            query.get("edible_only"),
            query.get("meal_type"),
            query.get("max_price") is not None,
            query.get("min_rating") is not None,
            query.get("discount_only"),
            query.get("healthy_intent"),
            query.get("protein_level"),
            query.get("sugar_level"),
        ]
    )

    if "subcategory" in query and query["subcategory"]:
        subcategory = str(query["subcategory"]).lower()
        working = working[
            _safe_contains(working.get("category_normalized", pd.Series(dtype=str)), subcategory)
            | _safe_contains(working.get("sub_category", pd.Series(dtype=str)), subcategory)
        ]

    if query.get("edible_only"):
        category_series = (
            working.get("category_normalized", pd.Series(dtype=str)).fillna("")
            + " "
            + working.get("sub_category", pd.Series(dtype=str)).fillna("").str.lower()
        )
        edible_mask = pd.Series(False, index=working.index)
        for pattern in EDIBLE_CATEGORY_PATTERNS:
            edible_mask |= category_series.str.contains(pattern, regex=False)
        for pattern in NON_EDIBLE_CATEGORY_PATTERNS:
            edible_mask &= ~category_series.str.contains(pattern, regex=False)
        working = working[edible_mask]

    if query.get("category_hint"):
        category_hint = str(query["category_hint"]).lower()
        working = working[
            _safe_contains(working.get("category_normalized", pd.Series(dtype=str)), category_hint)
            | _safe_contains(working.get("sub_category", pd.Series(dtype=str)), category_hint)
        ]

    if query.get("meal_type"):
        meal_type = query["meal_type"]
        working = working[working["meal_type_tags"].apply(lambda tags: meal_type in tags if isinstance(tags, list) else False)]

    if query.get("max_price") is not None:
        working = working[working["price"] <= float(query["max_price"])]

    if query.get("min_rating") is not None:
        working = working[working["rating"] >= float(query["min_rating"])]

    if query.get("discount_only"):
        working = working[working["discount_flag"]]

    if query.get("protein_level"):
        target = query["protein_level"]
        working = working[working["estimated_protein_level"] == target]

    if query.get("sugar_level"):
        target = query["sugar_level"]
        if target == "low":
            # Prefer low-sugar items, but keep medium items as fallback when the catalog
            # does not contain many explicit low-sugar labels.
            working = working[working["estimated_sugar_level"].isin(["low", "medium"])]
        else:
            working = working[working["estimated_sugar_level"] == target]

    # Avoid global fallback rankings when the query carries no usable signal.
    if not has_structured_filters and not text_terms:
        return working.iloc[0:0]

    if not has_structured_filters and text_terms:
        title_pool = working.get("title", pd.Series(dtype=str)).fillna("").str.lower()
        category_pool = (
            working.get("sub_category", pd.Series(dtype=str)).fillna("")
            + " "
            + working.get("category_normalized", pd.Series(dtype=str)).fillna("")
        ).str.lower()
        feature_pool = working.get("feature", pd.Series(dtype=str)).fillna("").str.lower()
        description_pool = working.get("product_description", pd.Series(dtype=str)).fillna("").str.lower()

        term_hits = pd.Series(0, index=working.index, dtype=float)
        for term in text_terms:
            singular = term[:-1] if term.endswith("s") and len(term) > 3 else term
            variants = {term, singular}
            for variant in variants:
                term_hits += title_pool.str.contains(variant, regex=False).astype(float) * 4.0
                term_hits += category_pool.str.contains(variant, regex=False).astype(float) * 3.0
                term_hits += feature_pool.str.contains(variant, regex=False).astype(float) * 1.5
                term_hits += description_pool.str.contains(variant, regex=False).astype(float) * 0.5

        working = working[term_hits > 0].copy()
        if working.empty:
            return working
        working["text_match_score"] = term_hits.loc[working.index]
    else:
        working["text_match_score"] = 0.0

    if working.empty:
        return working

    working["match_score"] = 0.0
    working["match_score"] += working["text_match_score"] * 3.0
    working["match_score"] += working["rating"].fillna(-1) * 2
    working["match_score"] += working["discount_flag"].astype(int) * 1.5
    working["match_score"] += working["budget_flag"].astype(int) * 1.0
    working["match_score"] += working.get("health_score", pd.Series(0.0, index=working.index))

    if query.get("protein_level") == "high":
        working["match_score"] += (working["estimated_protein_level"] == "high").astype(int) * 2.0
    if query.get("sugar_level") == "low":
        working["match_score"] += working["estimated_sugar_level"].map({"low": 2.0, "medium": 0.5, "high": -2.0}).fillna(0.0)
    if query.get("healthy_intent"):
        working["match_score"] += working.get("health_score", pd.Series(0.0, index=working.index)) * 2.0
    if query.get("meal_type"):
        meal_type = query["meal_type"]
        working["match_score"] += working["meal_type_tags"].apply(
            lambda tags: 1.5 if isinstance(tags, list) and meal_type in tags else 0.0
        )

    sort_by = query.get("sort_by", "match_score")
    sort_columns = {
        "price": ["price", "match_score"],
        "rating": ["rating", "match_score"],
        "discount": ["discount_amount", "match_score"],
        "match_score": ["match_score", "rating"],
    }.get(sort_by, ["match_score", "rating"])

    if sort_by == "price":
        working = working.sort_values(by=["price", "rating", "match_score"], ascending=[True, False, False], na_position="last")
    elif sort_by == "rating":
        working = working.sort_values(by=["rating", "match_score"], ascending=[False, False], na_position="last")
    else:
        working = working.sort_values(by=sort_columns, ascending=[False] * len(sort_columns), na_position="last")
    results = working.head(top_n).copy()
    results["explanation"] = results.apply(lambda row: _build_explanation(row, query), axis=1)

    preferred_columns = [
        "title",
        "sub_category",
        "price",
        "rating",
        "discount",
        "estimated_protein_level",
        "estimated_sugar_level",
        "meal_type_tags",
        "explanation",
    ]
    existing_columns = [col for col in preferred_columns if col in results.columns]
    return results[existing_columns]
