"""Runnable demo for the grocery recommendation MVP."""

from __future__ import annotations

import pandas as pd

from grocery_agent.data_loader import find_main_csv, load_dataset
from grocery_agent.feature_engineering import build_features
from grocery_agent.nlq_parser import parse_query
from grocery_agent.preprocess import preprocess_dataframe
from grocery_agent.recommender import build_no_result_message, recommend_products


EXAMPLE_QUERIES = [
    "Recommend low sugar breakfast items under 20 dollars",
    "Find high protein snacks with strong ratings",
    "Suggest budget friendly pantry items",
    "Show highly rated products with discounts",
    "cheap pantry items with good ratings",
]


def print_recommendations(query_text: str, results: pd.DataFrame) -> None:
    """Pretty-print recommendation results for the demo."""
    print(f"\nUser query: {query_text}")
    if results.empty:
        return

    display_columns = ["title", "sub_category", "price", "rating", "explanation"]
    display_df = results[display_columns].copy()
    display_df["rating"] = display_df["rating"].apply(lambda value: "N/A" if pd.isna(value) else value)
    print(display_df.to_string(index=False))


def main() -> None:
    """Run an end-to-end local demo against the detected grocery dataset."""
    dataset_path = find_main_csv(".")
    raw_df = load_dataset(dataset_path)
    clean_df = preprocess_dataframe(raw_df)
    featured_df = build_features(clean_df)

    print(f"Detected dataset: {dataset_path}")
    print(f"Rows loaded: {len(raw_df)}")
    print(f"Rows after cleaning: {len(clean_df)}")

    for query_text in EXAMPLE_QUERIES:
        structured_query = parse_query(query_text)
        results = recommend_products(featured_df, structured_query, top_n=5)
        if results.empty:
            print(f"\nUser query: {query_text}")
            print(build_no_result_message(structured_query, query_text))
            continue
        print_recommendations(query_text, results)


if __name__ == "__main__":
    main()
