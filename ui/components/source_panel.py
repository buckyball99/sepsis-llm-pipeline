import streamlit as st
import pandas as pd


def render_source_panel(df: pd.DataFrame):
    """Render the source verification panel for a given evidence DataFrame."""
    st.subheader("Source Verification")

    if "study_label" not in df.columns:
        st.warning("No study_label column found in results.")
        return

    studies = df["study_label"].dropna().unique().tolist()
    selected = st.selectbox("Select study to verify:", studies, key="source_panel_select")

    if not selected:
        return

    rows = df[df["study_label"] == selected]
    for _, row in rows.iterrows():
        with st.expander(
            f"{row.get('predictor', '?')} → {row.get('outcome', '?')}"
        ):
            st.markdown(f"**Source location:** {row.get('source_location', 'unknown')}")
            st.info(f"**Exact quote:**\n\n{row.get('source_quote', 'N/A')}")
            if row.get("extraction_warnings"):
                st.warning(f"⚠️ Warnings: {row['extraction_warnings']}")