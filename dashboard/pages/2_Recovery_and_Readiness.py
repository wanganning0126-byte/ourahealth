import sys
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.data import load_daily_dataset
from dashboard import ai_insights

st.set_page_config(page_title="Recovery and Readiness | Beyond the Oura", layout="wide")
st.title("Recovery and Readiness")

df = load_daily_dataset()
if df.empty or df["readiness_score"].dropna().empty:
    st.warning("No readiness data available.")
    st.stop()

readiness = df.dropna(subset=["readiness_score"])

col1, col2, col3 = st.columns(3)
col1.metric("Avg readiness score", f"{readiness['readiness_score'].mean():.1f}")
if "resting_bpm" in readiness.columns and readiness["resting_bpm"].notna().any():
    col2.metric("Avg resting HR", f"{readiness['resting_bpm'].mean():.0f} bpm")
if "temperature_deviation" in readiness.columns and readiness["temperature_deviation"].notna().any():
    col3.metric("Avg temp deviation", f"{readiness['temperature_deviation'].mean():+.2f}°C")

contributor_cols = ["activity_balance", "body_temperature", "hrv_balance",
                     "previous_day_activity", "previous_night", "recovery_index",
                     "resting_heart_rate_contributor", "sleep_balance", "sleep_regularity"]
available = [c for c in contributor_cols if c in readiness.columns
             and readiness[c].notna().any()]

midpoint = len(readiness) // 2
insight_stats = {
    "date_range": f"{readiness['day'].min().date()} to {readiness['day'].max().date()}",
    "num_days": len(readiness),
    "avg_score": round(readiness["readiness_score"].mean(), 1),
    "latest_score": round(readiness["readiness_score"].iloc[-1], 1),
    "first_half_avg": round(readiness["readiness_score"].iloc[:midpoint].mean(), 1) if midpoint else None,
    "second_half_avg": round(readiness["readiness_score"].iloc[midpoint:].mean(), 1) if midpoint else None,
    "contributor_averages": {c: round(readiness[c].mean(), 1) for c in available},
    "avg_resting_bpm": round(readiness["resting_bpm"].mean(), 1)
        if "resting_bpm" in readiness.columns and readiness["resting_bpm"].notna().any() else None,
    "avg_temp_deviation_c": round(readiness["temperature_deviation"].mean(), 2)
        if "temperature_deviation" in readiness.columns and readiness["temperature_deviation"].notna().any() else None,
}
ai_fields = {
    "trend": "What the readiness trend suggests",
    "recovery": "What's driving your recovery, including resting heart rate and temperature",
}
ai_text = ai_insights.fetch("Recovery and Readiness", insight_stats, ai_fields)

st.subheader("Readiness score over time")
if ai_text.get("trend"):
    ai_insights.show(ai_text["trend"])
fig = px.line(readiness, x="day", y="readiness_score", markers=True)
fig.update_layout(yaxis_title="Readiness score", xaxis_title="Date", height=380)
fig.add_hline(y=readiness["readiness_score"].mean(), line_dash="dot",
              annotation_text="average", opacity=0.5)
st.plotly_chart(fig)

if ai_text.get("recovery"):
    ai_insights.show(ai_text["recovery"])

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Readiness contributors")
    if available:
        avg_contributors = readiness[available].mean().sort_values(ascending=True)
        fig2 = px.bar(avg_contributors, orientation="h",
                      labels={"value": "Average score", "index": ""})
        fig2.update_layout(showlegend=False, height=420)
        st.plotly_chart(fig2)

with col_b:
    st.subheader("Resting heart rate")
    if "resting_bpm" in readiness.columns and readiness["resting_bpm"].notna().any():
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=readiness["day"], y=readiness["resting_bpm"],
                                   mode="lines+markers", name="Resting HR"))
        fig3.update_layout(yaxis_title="bpm", xaxis_title="Date", height=420)
        st.plotly_chart(fig3)
    else:
        st.info("No resting heart rate samples found for this period.")

if "temperature_deviation" in readiness.columns and readiness["temperature_deviation"].notna().any():
    st.subheader("Body temperature deviation")
    fig4 = px.bar(readiness, x="day", y="temperature_deviation")
    fig4.update_layout(yaxis_title="Deviation (°C)", xaxis_title="Date", height=320)
    st.plotly_chart(fig4)
