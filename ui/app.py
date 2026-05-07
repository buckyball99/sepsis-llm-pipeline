import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

from pipeline.query.router import route_query
from pipeline.query.expander import expand_query
from pipeline.query.sql_generator import query_to_dataframe
from pipeline.query.bm25_fallback import bm25_search

st.set_page_config(
    page_title="Sepsis Atlas",
    page_icon="🩺",
    layout="wide",
)

st.title("🩺 Sepsis Atlas — Evidence Explorer")
st.markdown(
    "Ask a clinical question. Every result links back to its exact source sentence."
)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("About")
    st.markdown(
        "This tool extracts structured predictor-outcome associations "
        "from sepsis research papers. "
        "Every value is traceable to a source sentence."
    )
    st.divider()
    st.markdown("**Example queries:**")
    st.markdown("- What predicts 28-day mortality in septic shock?")
    st.markdown("- Show AUC values for lactate across all studies")
    st.markdown("- Which studies report SOFA as a predictor?")
    st.markdown("- Compare sensitivity and specificity for lymphocyte count")

# ── Query input ───────────────────────────────────────────────────────────────
query = st.text_input(
    "Ask a clinical question:",
    placeholder="e.g. What predicts 28-day mortality in septic shock?",
)

if not query:
    st.stop()

# ── Processing ────────────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])

with st.spinner("Expanding query with medical synonyms..."):
    expanded = expand_query(query)

with col1:
    st.caption(f"Expanded: *{expanded}*")

route = route_query(expanded)
with col2:
    badge = {"sql": "🔢 SQL", "graph": "🕸️ Graph", "text": "📝 Text"}.get(route, route)
    st.caption(f"Query type: **{badge}**")

# ── SQL / Graph path ──────────────────────────────────────────────────────────
if route in ("sql", "graph"):
    try:
        with st.spinner("Querying evidence database..."):
            df, sql = query_to_dataframe(expanded)

        if df.empty:
            st.warning("No records matched your query. Try different terms.")
            st.stop()

        st.success(
            f"**{len(df)} records** found across "
            f"**{df['study_label'].nunique()} studies**"
        )

        # ── Evidence table ─────────────────────────────────────────────────
        st.subheader("Evidence Table")

        display_cols = [
            col for col in [
                "study_label", "population_desc", "sample_size",
                "predictor", "predictor_timing", "outcome",
                "method", "effect_size", "performance",
                "auc_value", "odds_ratio", "p_value",
                "notes", "source_location", "confidence", "not_reported",
            ]
            if col in df.columns
        ]

        # Highlight low confidence rows
        def highlight_confidence(row):
            if row.get("confidence") == "low":
                return ["background-color: #fff3cd"] * len(row)
            if row.get("not_reported"):
                return ["color: #6c757d"] * len(row)
            return [""] * len(row)

        st.dataframe(
            df[display_cols].style.apply(highlight_confidence, axis=1),
            use_container_width=True,
            height=400,
        )

        # ── Source verification ────────────────────────────────────────────
        st.subheader("Source Verification")
        st.markdown("Select a study to see the exact sentence the value was extracted from.")

        studies = df["study_label"].dropna().unique().tolist()
        selected = st.selectbox("Study:", studies)

        if selected:
            study_rows = df[df["study_label"] == selected]
            for _, row in study_rows.iterrows():
                with st.expander(
                    f"{row.get('predictor', '?')} → {row.get('outcome', '?')} "
                    f"| {row.get('source_location', '')}"
                ):
                    st.markdown(f"**Predictor:** {row.get('predictor')}")
                    st.markdown(f"**Outcome:** {row.get('outcome')}")
                    st.markdown(f"**Effect size:** {row.get('effect_size', 'not reported')}")
                    st.markdown(f"**Performance:** {row.get('performance', 'not reported')}")
                    st.info(f"📄 **Exact source quote:**\n\n{row.get('source_quote', 'N/A')}")
                    if row.get("extraction_warnings"):
                        st.warning(f"⚠️ {row['extraction_warnings']}")

        # ── Export ────────────────────────────────────────────────────────
        st.divider()
        col_dl, col_sql = st.columns(2)
        with col_dl:
            st.download_button(
                "⬇️ Download as CSV",
                df.to_csv(index=False),
                "evidence_table.csv",
                "text/csv",
            )
        with col_sql:
            with st.expander("Show generated SQL"):
                st.code(sql, language="sql")

    except RuntimeError as e:
        st.error(f"Query failed: {e}")
        st.markdown("Try rephrasing your question or check that papers have been ingested.")

# ── Text / BM25 path ──────────────────────────────────────────────────────────
elif route == "text":
    with st.spinner("Searching literature..."):
        results = bm25_search(expanded, top_k=8)

    if not results:
        st.warning("No relevant passages found.")
        st.stop()

    st.subheader(f"Relevant passages ({len(results)} found)")
    for r in results:
        with st.expander(
            f"**{r['study_label']}** — "
            f"{r.get('predictor', '')} → {r.get('outcome', '')} "
            f"(score: {r['score']:.2f})"
        ):
            st.write(r["text"])
            