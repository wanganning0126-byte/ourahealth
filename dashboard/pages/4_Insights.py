from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import streamlit as st
from sklearn.linear_model import LinearRegression

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.data import load_daily_dataset
from dashboard import ai_insights

st.set_page_config(page_title="Insights | Beyond the Oura", layout="wide")
st.title("Insights")
st.caption("Automatically generated observations from your data. More history makes these sharper.")

df = load_daily_dataset()
if df.empty:
    st.warning("No data available.")
    st.stop()


def trend_slope(series: "np.ndarray") -> float | None:
    """Points per day, from a simple linear regression against day index."""
    valid = ~np.isnan(series)
    if valid.sum() < 4:
        return None
    x = np.arange(len(series))[valid].reshape(-1, 1)
    y = series[valid]
    model = LinearRegression().fit(x, y)
    return float(model.coef_[0])


def describe_trend(label: str, series, unit: str = "pts") -> str:
    slope = trend_slope(series.to_numpy(dtype=float))
    if slope is None:
        return f"Not enough {label.lower()} data yet to detect a trend."
    weekly = slope * 7
    if abs(weekly) < 0.5:
        return f"{label} has been roughly stable (~{weekly:+.1f} {unit}/week)."
    direction = "improving" if weekly > 0 else "declining"
    return f"{label} is {direction}, changing about {weekly:+.1f} {unit}/week."


score_fields = [("Sleep score", "sleep_score"), ("Readiness score", "readiness_score"),
                 ("Activity score", "activity_score")]
weekly_slopes = {}
for label, field in score_fields:
    if field in df.columns and df[field].notna().sum() >= 4:
        slope = trend_slope(df[field].to_numpy(dtype=float))
        if slope is not None:
            weekly_slopes[field] = round(slope * 7, 2)

candidate_cols = ["sleep_score", "readiness_score", "activity_score", "steps",
                   "resting_bpm", "total_calories", "hrv_balance", "deep_sleep", "rem_sleep"]
available = [c for c in candidate_cols if c in df.columns and df[c].notna().sum() >= 5]
pairs = []
if len(available) >= 2:
    corr = df[available].corr(numeric_only=True)
    for i, a in enumerate(available):
        for b in available[i + 1:]:
            value = corr.loc[a, b]
            if not np.isnan(value):
                pairs.append((abs(value), value, a, b))
    pairs.sort(reverse=True)

insight_stats = {
    "date_range": f"{df['day'].min().date()} to {df['day'].max().date()}",
    "num_days": len(df),
    "weekly_score_change": weekly_slopes,
    "top_correlations": [
        {"metric_a": a, "metric_b": b, "r": round(value, 2)}
        for _, value, a, b in pairs[:5]
    ],
}
ai_fields = {
    "trends": "Overall trend narrative",
    "correlations": "What the strongest relationships might mean",
}
ai_text = ai_insights.fetch("Insights", insight_stats, ai_fields)

st.subheader("Trends")
for label, field in score_fields:
    if field in df.columns and df[field].notna().sum() >= 4:
        st.write("- " + describe_trend(label, df[field]))
if ai_text.get("trends"):
    ai_insights.show(ai_text["trends"])

st.divider()

st.subheader("Personal bests & lows")
records = [
    ("Sleep score", "sleep_score", "pts"),
    ("Readiness score", "readiness_score", "pts"),
    ("Activity score", "activity_score", "pts"),
    ("Steps", "steps", "steps"),
    ("Resting heart rate", "resting_bpm", "bpm"),
]
cols = st.columns(2)
for label, field, unit in records:
    if field not in df.columns or df[field].dropna().empty:
        continue
    valid = df.dropna(subset=[field])
    best_row = valid.loc[valid[field].idxmax()]
    worst_row = valid.loc[valid[field].idxmin()]
    with cols[0]:
        st.write(f"**Best {label.lower()}:** {best_row[field]:,.0f} {unit} "
                 f"on {best_row['day'].date()}")
    with cols[1]:
        st.write(f"**Lowest {label.lower()}:** {worst_row[field]:,.0f} {unit} "
                 f"on {worst_row['day'].date()}")

st.divider()

st.subheader("Strongest relationships")
if len(available) >= 2:
    if pairs:
        for _, value, a, b in pairs[:5]:
            strength = "strong" if abs(value) >= 0.6 else "moderate" if abs(value) >= 0.3 else "weak"
            direction = "positive" if value > 0 else "negative"
            a_label, b_label = a.replace("_", " "), b.replace("_", " ")
            st.write(f"- {a_label} and {b_label}: **{strength} {direction}** correlation "
                     f"(r = {value:.2f})")
        if ai_text.get("correlations"):
            ai_insights.show(ai_text["correlations"])
    else:
        st.info("No correlations could be computed yet.")
else:
    st.info("Need more overlapping metrics with data to compute relationships.")

st.caption("Correlation does not imply causation — treat these as leads to explore further, "
           "especially with only a couple weeks of history.")
