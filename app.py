"""Small Streamlit UI for the grocery recommendation MVP."""

from __future__ import annotations

import pandas as pd
import streamlit as st

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
    "healthy food",
]


@st.cache_data
def prepare_dataset() -> tuple[str, pd.DataFrame]:
    """Load and prepare the dataset once per app session."""
    dataset_path = find_main_csv(".")
    raw_df = load_dataset(dataset_path)
    clean_df = preprocess_dataframe(raw_df)
    featured_df = build_features(clean_df)
    return str(dataset_path), featured_df


def _format_money(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"${float(value):.2f}"


def _format_rating(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{float(value):.1f}"


def format_query_summary(query: dict) -> list[str]:
    """Convert the parsed query into a human-readable summary."""
    summary: list[str] = []

    if query.get("max_price") is not None:
        summary.append(f"Budget: under ${float(query['max_price']):.0f}")
    if query.get("subcategory"):
        summary.append(f"Category: {str(query['subcategory']).title()}")
    elif query.get("category_hint"):
        summary.append(f"Category Hint: {str(query['category_hint']).title()}")
    if query.get("meal_type"):
        summary.append(f"Meal Type: {str(query['meal_type']).title()}")
    if query.get("protein_level"):
        summary.append(f"Protein Preference: {str(query['protein_level']).title()}")
    if query.get("sugar_level"):
        summary.append(f"Sugar Preference: {str(query['sugar_level']).title()}")
    if query.get("min_rating") is not None:
        summary.append(f"Minimum Rating: {float(query['min_rating']):.1f}+")
    if query.get("discount_only"):
        summary.append("Discounts Only")
    if query.get("healthy_intent"):
        summary.append("Healthy Intent")
    if query.get("sort_by"):
        summary.append(f"Sort: {str(query['sort_by']).replace('_', ' ').title()}")

    return summary or ["No strong structured filters detected"]


def render_query_summary(query: dict) -> None:
    """Render the parsed query in a more product-friendly format."""
    st.subheader("How The Request Was Interpreted")
    for item in format_query_summary(query):
        st.markdown(f"- {item}")

    if query.get("text_terms"):
        terms = ", ".join(query["text_terms"])
        st.caption(f"Fallback keywords: {terms}")


def render_result_card(row: pd.Series) -> None:
    """Render one recommendation as a simple card."""
    title = row.get("title", "Untitled product")
    sub_category = row.get("sub_category", "Unknown")
    price = _format_money(row.get("price"))
    rating = _format_rating(row.get("rating"))
    explanation = row.get("explanation", "")

    meta_parts = [
        f"Category: {sub_category}",
        f"Price: {price}",
        f"Rating: {rating}",
    ]

    if pd.notna(row.get("estimated_protein_level")):
        meta_parts.append(f"Protein: {row.get('estimated_protein_level')}")
    if pd.notna(row.get("estimated_sugar_level")):
        meta_parts.append(f"Sugar: {row.get('estimated_sugar_level')}")

    st.markdown(f"#### {title}")
    st.caption(" | ".join(meta_parts))
    st.write(explanation)
    st.divider()


def main() -> None:
    """Render the MVP grocery recommendation app."""
    st.set_page_config(page_title="AI Grocery Recommender MVP", layout="wide")

    st.title("AI Grocery Recommender MVP")
    st.write(
        "Type a shopping request in plain English. The app will interpret your constraints, "
        "rank grocery products, and explain why the results were selected."
    )

    dataset_path, featured_df = prepare_dataset()

    with st.sidebar:
        st.subheader("Dataset")
        st.write(f"Source: `{dataset_path}`")
        st.write(f"Products available: `{len(featured_df)}`")
        rating_coverage_pct = 100 - (featured_df["rating"].isna().mean() * 100)
        st.write(f"Rating coverage: `{rating_coverage_pct:.1f}%`")
        st.caption("This demo uses rule-based parsing and lightweight heuristic features.")

    query_text = st.text_input(
        "Shopping request",
        value=st.session_state.get("query_text", ""),
        placeholder='Try: "high protein snacks" or "low sugar breakfast under 20"',
        help="Example: low sugar breakfast under 15 dollars",
    )
    st.session_state["query_text"] = query_text

    selected_example = st.pills(
        "Example prompts",
        EXAMPLE_QUERIES,
        selection_mode="single",
        default=None,
    )
    if selected_example and selected_example != st.session_state.get("query_text"):
        st.session_state["query_text"] = selected_example
        st.rerun()

    top_n = st.slider("Number of recommendations", min_value=3, max_value=10, value=5)

    if not query_text.strip():
        st.info("Enter a shopping request to see recommendations.")
        return

    structured_query = parse_query(query_text)
    results = recommend_products(featured_df, structured_query, top_n=top_n)

    st.caption("Protein and sugar labels are heuristic estimates based on product title and description text.")

    col1, col2 = st.columns([1, 2])

    with col1:
        render_query_summary(structured_query)

    with col2:
        st.subheader("Top Recommendations")
        if results.empty:
            st.warning(build_no_result_message(structured_query, query_text))
        else:
            st.write(
                f"Showing {min(len(results), top_n)} results matched to your request."
            )
            for _, row in results.iterrows():
                render_result_card(row)


if __name__ == "__main__":
    main()
