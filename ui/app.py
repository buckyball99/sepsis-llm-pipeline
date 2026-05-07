import sys
import os
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

from pipeline.query.router import route_query
from pipeline.query.expander import expand_query
from pipeline.query.sql_generator import query_to_dataframe
from pipeline.query.bm25_fallback import bm25_search
from pipeline.storage.db import init_db, get_stats

st.set_page_config(
    page_title="Sepsis Atlas",
    page_icon="🩺",
    layout="wide",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🩺 Sepsis Atlas")
    st.markdown(
        "AI-powered clinical evidence assistant. "
        "Every extracted value is traceable to its source sentence."
    )
    st.divider()

    stats = get_stats()
    st.metric("Papers ingested", stats["papers"])
    st.metric("Evidence records", stats["evidence_records"])
    st.metric("High-confidence", stats["high_confidence"])
    st.divider()

    st.markdown("**Example queries:**")
    st.markdown("- What predicts 28-day mortality in septic shock?")
    st.markdown("- Show AUC values for lactate across all studies")
    st.markdown("- Which studies report SOFA as a predictor?")
    st.markdown("- Compare sensitivity and specificity for lymphocyte count")
    st.divider()
    st.page_link("pages/admin.py", label="Admin Dashboard", icon="⚙️")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_query, tab_ingest = st.tabs(["Evidence Explorer", "Ingest Papers"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: EVIDENCE QUERY
# ══════════════════════════════════════════════════════════════════════════════
with tab_query:
    st.header("Evidence Explorer")
    st.markdown("Ask a clinical question. Every result links back to its exact source sentence.")

    query = st.text_input(
        "Ask a clinical question:",
        placeholder="e.g. What predicts 28-day mortality in septic shock?",
        key="query_input",
    )

    if not query:
        st.info("Enter a question above to search the evidence database.")
        st.stop()

    # Run expand + route in parallel to save one round-trip
    with st.spinner("Processing query..."):
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_expand = pool.submit(expand_query, query)
            f_route  = pool.submit(route_query, query)   # route on raw query for speed
            expanded = f_expand.result()
            route    = f_route.result()

    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"Expanded: *{expanded}*")
    with col2:
        badge = {"sql": "🔢 SQL", "graph": "🕸️ Graph", "text": "📝 Text"}.get(route, route)
        st.caption(f"Query type: **{badge}**")

    # ── SQL / Graph path ──────────────────────────────────────────────────────
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

            # ── Evidence table in task-spec format ───────────────────────────
            st.subheader("Evidence Table")

            # Map internal column names to task-spec display names
            COLUMN_MAP = {
                "study_label":       "Study",
                "population_desc":   "Population",
                "sample_size":       "Sample Size",
                "predictor":         "Predictor",
                "predictor_timing":  "Measurement Timing",
                "outcome":           "Outcome",
                "method":            "Method",
                "effect_size":       "Effect Size",
                "performance":       "Performance",
                "notes":             "Notes",
                "source_location":   "Source",
                "confidence":        "Confidence",
                "not_reported":      "Not Reported",
            }

            display_cols = [c for c in COLUMN_MAP if c in df.columns]
            display_df = df[display_cols].rename(columns=COLUMN_MAP)

            def _highlight(row):
                conf = row.get("Confidence", "")
                if conf == "low":
                    return ["background-color: #fff3cd"] * len(row)
                if row.get("Not Reported"):
                    return ["color: #6c757d; font-style: italic"] * len(row)
                return [""] * len(row)

            st.dataframe(
                display_df.style.apply(_highlight, axis=1),
                use_container_width=True,
                height=420,
            )

            # ── Source verification ───────────────────────────────────────────
            st.subheader("Source Verification")
            st.markdown("Expand a row to see the exact sentence the value was extracted from.")

            studies = df["study_label"].dropna().unique().tolist()
            selected = st.selectbox("Study:", studies)

            if selected:
                study_rows = df[df["study_label"] == selected]
                for _, row in study_rows.iterrows():
                    header = (
                        f"{row.get('predictor', '?')} → {row.get('outcome', '?')} "
                        f"| {row.get('source_location', '')}"
                    )
                    with st.expander(header):
                        ca, cb = st.columns(2)
                        ca.markdown(f"**Predictor:** {row.get('predictor')}")
                        ca.markdown(f"**Outcome:** {row.get('outcome')}")
                        ca.markdown(f"**Method:** {row.get('method', '—')}")
                        cb.markdown(f"**Effect size:** {row.get('effect_size', 'not reported')}")
                        cb.markdown(f"**Performance:** {row.get('performance', 'not reported')}")
                        cb.markdown(f"**Confidence:** `{row.get('confidence')}`")
                        st.info(f"📄 **Exact source quote:**\n\n{row.get('source_quote', 'N/A')}")
                        if row.get("extraction_warnings"):
                            st.warning(f"⚠️ {row['extraction_warnings']}")

            # ── Export ────────────────────────────────────────────────────────
            st.divider()
            col_dl, col_sql = st.columns(2)
            with col_dl:
                st.download_button(
                    "⬇️ Download as CSV",
                    display_df.to_csv(index=False),
                    "evidence_table.csv",
                    "text/csv",
                )
            with col_sql:
                with st.expander("Show generated SQL"):
                    st.code(sql, language="sql")

        except RuntimeError as e:
            st.error(f"Query failed: {e}")
            st.markdown("Try rephrasing or check that papers have been ingested.")

    # ── Text / BM25 path ──────────────────────────────────────────────────────
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

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: PDF INGESTION
# ══════════════════════════════════════════════════════════════════════════════
with tab_ingest:
    st.header("Ingest New Papers")
    st.markdown(
        "Upload PDF papers here to add them to the evidence database. "
        "Each paper is parsed, chunked, and extracted automatically."
    )

    uploaded_files = st.file_uploader(
        "Upload PDF files",
        type=["pdf"],
        accept_multiple_files=True,
        help="Select one or more sepsis research PDFs.",
    )

    col_btn, col_skip = st.columns([2, 3])
    with col_skip:
        skip_existing = st.checkbox("Skip already-ingested papers", value=True)

    if uploaded_files and col_btn.button("Start Ingestion", type="primary"):
        init_db()

        raw_pdf_dir = "data/raw_pdfs"
        os.makedirs(raw_pdf_dir, exist_ok=True)

        saved_paths = []
        for uf in uploaded_files:
            dest = os.path.join(raw_pdf_dir, uf.name)
            with open(dest, "wb") as fh:
                fh.write(uf.read())
            saved_paths.append(dest)

        st.info(f"Saved {len(saved_paths)} PDF(s). Starting ingestion...")

        from flows.ingest_flow import ingest_paper

        progress = st.progress(0, text="Ingesting…")
        log_area = st.empty()
        results_summary = []

        for idx, path in enumerate(saved_paths):
            name = os.path.basename(path)
            log_area.info(f"Processing {name} ({idx+1}/{len(saved_paths)})…")
            n = ingest_paper(path, skip_existing=skip_existing)
            results_summary.append({"file": name, "records_stored": n})
            progress.progress((idx + 1) / len(saved_paths), text=f"Done: {name}")

        progress.empty()
        log_area.empty()
        total = sum(r["records_stored"] for r in results_summary)
        st.success(f"Ingestion complete! {total} total records stored.")
        st.dataframe(pd.DataFrame(results_summary), use_container_width=True)
        st.rerun()

    elif not uploaded_files:
        st.markdown("---")
        st.markdown("**Or re-ingest all PDFs already in `data/raw_pdfs/`:**")
        if st.button("Re-ingest all PDFs from disk"):
            from flows.ingest_flow import ingest_all
            init_db()
            with st.spinner("Ingesting all PDFs…"):
                results = ingest_all(skip_existing=skip_existing)
            total = sum(results.values())
            st.success(f"Done! {total} new records stored across {len(results)} papers.")
            st.rerun()
