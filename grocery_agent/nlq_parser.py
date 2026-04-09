"""Simple rule-based natural language parser for grocery shopping queries."""

from __future__ import annotations

import re


SUBCATEGORY_KEYWORDS = {
    "snacks": ["snack", "snacks", "chips", "crackers", "bars"],
    "pantry": ["pantry", "dry goods", "rice", "pasta", "beans"],
    "breakfast": ["breakfast", "cereal", "granola", "oatmeal", "pancake", "waffle"],
    "dessert": ["dessert", "cake", "cookie", "cookies", "candy", "chocolate"],
    "beverage": ["beverage", "drink", "drinks", "coffee", "tea", "water", "juice", "soda"],
}

CATEGORY_KEYWORDS = {
    "snack": "snacks",
    "snacks": "snacks",
    "cake": "bakery desserts",
    "dessert": "bakery desserts",
    "desserts": "bakery desserts",
    "drink": "beverages",
    "drinks": "beverages",
    "juice": "beverages",
    "coffee": "coffee",
    "flower": "floral",
    "flowers": "floral",
    "paper towel": "paper plastic",
    "paper towels": "paper plastic",
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "best",
    "budget",
    "buy",
    "cheap",
    "deal",
    "deals",
    "dollar",
    "dollars",
    "find",
    "food",
    "foods",
    "for",
    "good",
    "healthy",
    "healthier",
    "high",
    "highly",
    "items",
    "low",
    "me",
    "of",
    "on",
    "only",
    "product",
    "products",
    "rated",
    "rating",
    "ratings",
    "recommend",
    "sale",
    "show",
    "strong",
    "suggest",
    "the",
    "under",
    "with",
}


def _extract_max_price(text: str) -> float | None:
    patterns = [
        r"under\s+\$?(\d+(?:\.\d+)?)",
        r"below\s+\$?(\d+(?:\.\d+)?)",
        r"less than\s+\$?(\d+(?:\.\d+)?)",
        r"max(?:imum)?\s+\$?(\d+(?:\.\d+)?)",
        r"\$?(\d+(?:\.\d+)?)\s*(?:dollars|bucks)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))
    if any(word in text for word in ["cheap", "budget", "budget friendly", "affordable"]):
        return 20.0
    return None


def _extract_min_rating(text: str) -> float | None:
    match = re.search(r"(\d(?:\.\d+)?)\s*(?:stars|star|rating)", text)
    if match:
        return float(match.group(1))
    if any(phrase in text for phrase in ["highly rated", "good ratings", "strong ratings", "top rated", "best rated"]):
        return 4.0
    return None


def _extract_subcategory(text: str) -> str | None:
    for label, keywords in SUBCATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return label
    return None


def extract_category(text: str) -> str | None:
    """Map user keywords to broad catalog category hints."""
    lowered = text.lower()
    for keyword, category in CATEGORY_KEYWORDS.items():
        if keyword in lowered:
            return category
    return None


def _extract_text_terms(text: str) -> list[str]:
    """Keep meaningful leftover words for lexical matching when rules do not fire."""
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    terms: list[str] = []
    for token in tokens:
        if len(token) < 3:
            continue
        if token in STOPWORDS:
            continue
        if token not in terms:
            terms.append(token)
    return terms


def parse_query(query_text: str) -> dict:
    """
    Convert simple natural language grocery requests into a structured query dict.

    This parser is intentionally explicit and easy to edit as product requirements evolve.
    """
    text = query_text.lower().strip()

    subcategory = _extract_subcategory(text)
    category_hint = extract_category(text)
    meal_type = subcategory if subcategory in {"breakfast", "dessert", "beverage"} else None
    edible_only = any(
        term in text
        for term in [
            "food",
            "foods",
            "healthy food",
            "healthy foods",
            "healthy",
            "healthier",
            "snack",
            "snacks",
            "breakfast",
            "drink",
            "drinks",
            "beverage",
            "beverages",
            "pantry",
            "dessert",
            "coffee",
        ]
    )
    if "snack" in text:
        meal_type = "snack"
    if "pantry" in text:
        meal_type = "pantry"

    query = {
        "max_price": _extract_max_price(text),
        "min_rating": _extract_min_rating(text),
        "subcategory": subcategory,
        "category_hint": category_hint,
        "edible_only": edible_only,
        "discount_only": any(term in text for term in ["discount", "discounted", "sale", "on sale", "deal"]),
        "healthy_intent": any(term in text for term in ["healthy", "healthier"]),
        "protein_level": "high" if "high protein" in text or "protein rich" in text else None,
        "sugar_level": "low" if "low sugar" in text or "sugar free" in text else "high" if "high sugar" in text else None,
        "meal_type": meal_type,
        "sort_by": "rating",
        "text_terms": _extract_text_terms(text),
    }

    if any(term in text for term in ["cheapest", "lowest price", "budget", "cheap", "affordable"]):
        query["sort_by"] = "price"
    if any(term in text for term in ["discount", "discounted", "sale", "deal"]):
        query["sort_by"] = "discount"
    if any(term in text for term in ["best", "top", "highly rated", "good ratings", "strong ratings"]):
        query["sort_by"] = "rating"
    if query["healthy_intent"]:
        query["sort_by"] = "match_score"

    return query
