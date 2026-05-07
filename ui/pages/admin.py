import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd

from pipeline.storage.db import (
    init_db,
    get_stats,
    get_all_papers,
    get_evidence_for_paper,
    get_predictor_summary,
    delete_paper,
    query_db,
)

st.set_page_config(page_title="Sepsis Atlas — Admin", page_icon="⚙️", layout="wide")

st.title("⚙️ Admin Dashboard")
st.markdown("Inspect and manage the DuckDB evidence database.")

# ── Initialise DB (safe no-op if already exists) ──────────────────────────────
try:
    init_db()
except Exception:
    pass

# ── Stats row ─────────────────────────────────────────────────────────────────
stats = get_stats()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Papers", stats["papers"])
c2.metric("Evidence records", stats["evidence_records"])
c3.metric("High-confidence", stats["high_confidence"])
c4.metric("Not reported", stats["not_reported"])

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_papers, tab_evidence, tab_predictor, tab_sql = st.tabs(
    ["Papers", "Evidence Browser", "Predictor Summary", "Raw SQL"]
)

# ════════════════════════════════════════════════════════════════════════════
# TAB 1: PAPERS
# ════════════════════════════════════════════════════════════════════════════
with tab_papers:
    st.subheader("Ingested Papers")

    papers_df = get_all_papers()

    if papers_df.empty:
        st.info("No papers ingested yet. Use the main app's 'Ingest Papers' tab to add PDFs.")
    else:
        st.dataframe(papers_df.drop(columns=["paper_id"], errors="ignore"),
                     use_container_width=True)

        st.divider()
        st.subheader("Delete a Paper")
        st.warning("This permanently removes the paper and all its evidence records from the database.")

        paper_options = papers_df.apply(
            lambda r: f"{r.get('title') or r.get('paper_id', 'Unknown')} ({r.get('year', '')})",
            axis=1,
        ).tolist()
        paper_ids = papers_df["paper_id"].tolist()

        selected_idx = st.selectbox("Select paper to delete:", range(len(paper_options)),
                                    format_func=lambda i: paper_options[i])

        if st.button("Delete selected paper", type="primary"):
            pid = paper_ids[selected_idx]
            delete_paper(pid)
            st.success(f"Deleted paper and its evidence records.")
            st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# TAB 2: EVIDENCE BROWSER
# ════════════════════════════════════════════════════════════════════════════
with tab_evidence:
    st.subheader("Evidence Records")

    papers_df2 = get_all_papers()
    if papers_df2.empty:
        st.info("No papers ingested yet.")
    else:
        paper_labels = papers_df2.apply(
            lambda r: f"{r.get('title') or 'Unknown'} ({r.get('year', '')})", axis=1
        ).tolist()
        paper_ids2 = papers_df2["paper_id"].tolist()

        col_sel, col_filter = st.columns([2, 3])
        with col_sel:
            sel_idx = st.selectbox("Paper:", range(len(paper_labels)),
                                   format_func=lambda i: paper_labels[i],
                                   key="ev_paper_sel")
        with col_filter:
            conf_filter = st.multiselect(
                "Confidence filter:",
                ["high", "medium", "low"],
                default=["high", "medium", "low"],
            )

        ev_df = get_evidence_for_paper(paper_ids2[sel_idx])

        if ev_df.empty:
            st.info("No evidence records for this paper.")
        else:
            if conf_filter:
                ev_df = ev_df[ev_df["confidence"].isin(conf_filter)]

            show_cols = [
                c for c in [
                    "study_label", "predictor", "predictor_timing", "outcome",
                    "method", "effect_size", "performance",
                    "auc_value", "odds_ratio", "p_value",
                    "confidence", "not_reported", "source_location",
                ]
                if c in ev_df.columns
            ]

            st.markdown(f"**{len(ev_df)} records**")
            st.dataframe(ev_df[show_cols], use_container_width=True, height=350)

            # Source quote drill-down
            st.subheader("Source Quotes")
            for _, row in ev_df.iterrows():
                label = f"{row.get('predictor', '?')} → {row.get('outcome', '?')}"
                with st.expander(label):
                    col_a, col_b = st.columns(2)
                    col_a.markdown(f"**Effect size:** {row.get('effect_size', '—')}")
                    col_a.markdown(f"**Performance:** {row.get('performance', '—')}")
                    col_b.markdown(f"**Confidence:** `{row.get('confidence')}`")
                    col_b.markdown(f"**Not reported:** {row.get('not_reported')}")
                    st.info(f"📄 {row.get('source_quote', 'N/A')}")
                    if row.get("extraction_warnings"):
                        st.warning(row["extraction_warnings"])

            st.divider()
            st.download_button(
                "⬇️ Download this paper's evidence as CSV",
                ev_df.to_csv(index=False),
                f"{paper_labels[sel_idx][:40]}_evidence.csv",
                "text/csv",
            )

# ════════════════════════════════════════════════════════════════════════════
# TAB 3: PREDICTOR SUMMARY
# ════════════════════════════════════════════════════════════════════════════
with tab_predictor:
    st.subheader("Predictor Evidence Summary")
    st.markdown("Ranked by number of studies reporting each predictor.")

    pred_df = get_predictor_summary()
    if pred_df.empty:
        st.info("No evidence records yet.")
    else:
        st.dataframe(pred_df, use_container_width=True, height=400)

        # Bar chart of study count
        st.bar_chart(
            pred_df.set_index("predictor")["study_count"].head(15),
            use_container_width=True,
        )

        st.download_button(
            "⬇️ Download predictor summary as CSV",
            pred_df.to_csv(index=False),
            "predictor_summary.csv",
            "text/csv",
        )

# ════════════════════════════════════════════════════════════════════════════
# TAB 4: RAW SQL CONSOLE
# ════════════════════════════════════════════════════════════════════════════
with tab_sql:
    st.subheader("Raw SQL Console")
    st.markdown("Run any read-only DuckDB query against the evidence database.")

    default_sql = "SELECT study_label, predictor, outcome, auc_value, odds_ratio, confidence\nFROM evidence\nWHERE not_reported = FALSE\nORDER BY auc_value DESC NULLS LAST\nLIMIT 20"

    sql_input = st.text_area("SQL query:", value=default_sql, height=140)

    if st.button("Run query"):
        if any(kw in sql_input.upper() for kw in ("DROP", "DELETE", "TRUNCATE", "INSERT", "UPDATE")):
            st.error("Write operations are not permitted in the SQL console.")
        else:
            try:
                result_df = query_db(sql_input)
                st.success(f"{len(result_df)} rows returned")
                st.dataframe(result_df, use_container_width=True, height=400)
                st.download_button(
                    "⬇️ Download result as CSV",
                    result_df.to_csv(index=False),
                    "query_result.csv",
                    "text/csv",
                )
            except Exception as e:
                st.error(f"Query failed: {e}")
