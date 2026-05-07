import streamlit as st
import pandas as pd


def render_evidence_table(df: pd.DataFrame):
    """Render the main evidence table with confidence highlighting."""
    display_cols = [
        col for col in [
            "study_label", "predictor", "predictor_timing", "outcome",
            "method", "effect_size", "performance",
            "auc_value", "odds_ratio", "p_value",
            "sample_size", "setting", "confidence", "not_reported",
        ]
        if col in df.columns
    ]

    st.dataframe(df[display_cols], use_container_width=True, height=400)