from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.data import load_daily_dataset, numeric_score_columns

st.set_page_config(page_title="Correlation Explorer | Beyond the Oura", layout="wide")
st.title("Correlation Explorer")
st.caption("Explore relationships between any two metrics in your data.")

df = load_daily_dataset()
if df.empty:
    st.warning("No data available.")
    st.stop()

metric_cols = [c for c in numeric_score_columns(df) if df[c].notna().sum() >= 3]
if len(metric_cols) < 2:
    st.info("Need at least two metrics with data to explore correlations.")
    st.stop()

nice_labels = {c: c.replace("_", " ").title() for c in metric_cols}

st.subheader("Correlation matrix")
corr = df[metric_cols].corr(numeric_only=True)
corr_display = corr.rename(columns=nice_labels, index=nice_labels)
fig = px.imshow(corr_display, color_continuous_scale="RdBu", zmin=-1, zmax=1,
                 aspect="auto", text_auto=".2f")
fig.update_layout(height=min(120 + 35 * len(metric_cols), 900))
st.plotly_chart(fig)

st.divider()

st.subheader("Scatter explorer")
col1, col2 = st.columns(2)
with col1:
    x_metric = st.selectbox("X axis", metric_cols, format_func=lambda c: nice_labels[c],
                             index=metric_cols.index("sleep_score") if "sleep_score" in metric_cols else 0)
with col2:
    default_y = "readiness_score" if "readiness_score" in metric_cols else metric_cols[min(1, len(metric_cols) - 1)]
    y_metric = st.selectbox("Y axis", metric_cols, format_func=lambda c: nice_labels[c],
                             index=metric_cols.index(default_y))

scatter_df = df.dropna(subset=[x_metric, y_metric])
if len(scatter_df) < 3:
    st.info("Not enough overlapping data points for these two metrics yet.")
else:
    r_value = scatter_df[x_metric].corr(scatter_df[y_metric])
    fig2 = px.scatter(scatter_df, x=x_metric, y=y_metric, trendline="ols",
                       labels={x_metric: nice_labels[x_metric], y_metric: nice_labels[y_metric]},
                       hover_data=["day"])
    fig2.update_layout(height=460)
    st.plotly_chart(fig2)
    st.metric("Pearson correlation (r)", f"{r_value:.2f}")
