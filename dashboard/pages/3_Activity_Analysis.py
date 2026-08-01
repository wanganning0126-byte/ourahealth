import sys
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.data import load_daily_dataset
from dashboard import ai_insights

st.set_page_config(page_title="Activity Analysis | Beyond the Oura", layout="wide")
st.title("Activity Analysis")

df = load_daily_dataset()
if df.empty or df["activity_score"].dropna().empty:
    st.warning("No activity data available.")
    st.stop()

activity = df.dropna(subset=["activity_score"])

col1, col2, col3, col4 = st.columns(4)
col1.metric("Avg activity score", f"{activity['activity_score'].mean():.1f}")
if "steps" in activity.columns:
    col2.metric("Avg steps / day", f"{activity['steps'].mean():,.0f}")
    col3.metric("Best day (steps)", f"{activity['steps'].max():,.0f}")
if "total_calories" in activity.columns:
    col4.metric("Avg total calories", f"{activity['total_calories'].mean():,.0f}")

intensity_cols = ["sedentary_time_min", "resting_time_min", "low_activity_time_min",
                   "medium_activity_time_min", "high_activity_time_min"]
intensity_available = [c for c in intensity_cols if c in activity.columns]

midpoint = len(activity) // 2
insight_stats = {
    "date_range": f"{activity['day'].min().date()} to {activity['day'].max().date()}",
    "num_days": len(activity),
    "avg_score": round(activity["activity_score"].mean(), 1),
    "latest_score": round(activity["activity_score"].iloc[-1], 1),
    "avg_steps": round(activity["steps"].mean()) if "steps" in activity.columns else None,
    "best_steps_day": {
        "value": int(activity["steps"].max()),
        "date": str(activity.loc[activity["steps"].idxmax(), "day"].date()),
    } if "steps" in activity.columns else None,
    "first_half_avg_score": round(activity["activity_score"].iloc[:midpoint].mean(), 1) if midpoint else None,
    "second_half_avg_score": round(activity["activity_score"].iloc[midpoint:].mean(), 1) if midpoint else None,
    "avg_minutes_by_intensity": {c.replace("_time_min", ""): round(activity[c].mean(), 1)
                                  for c in intensity_available},
}
ai_fields = {
    "trend": "What the activity trend suggests",
    "intensity": "What your intensity mix says about your activity habits",
}
ai_text = ai_insights.fetch("Activity Analysis", insight_stats, ai_fields)

st.subheader("Activity score & steps over time")
if ai_text.get("trend"):
    ai_insights.show(ai_text["trend"])
fig = go.Figure()
fig.add_trace(go.Scatter(x=activity["day"], y=activity["activity_score"], mode="lines+markers",
                          name="Activity score", yaxis="y1"))
if "steps" in activity.columns:
    fig.add_trace(go.Bar(x=activity["day"], y=activity["steps"], name="Steps",
                          yaxis="y2", opacity=0.35))
fig.update_layout(
    height=420,
    yaxis=dict(title="Activity score"),
    yaxis2=dict(title="Steps", overlaying="y", side="right", showgrid=False),
    xaxis_title="Date",
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
)
st.plotly_chart(fig)

st.subheader("Time in each activity intensity")
if ai_text.get("intensity"):
    ai_insights.show(ai_text["intensity"])
if intensity_available:
    labels = {c: c.replace("_time_min", "").replace("_", " ").title() for c in intensity_available}
    fig2 = go.Figure()
    for col in intensity_available:
        fig2.add_trace(go.Bar(x=activity["day"], y=activity[col], name=labels[col]))
    fig2.update_layout(barmode="stack", yaxis_title="Minutes", xaxis_title="Date", height=420,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig2)

if "equivalent_walking_distance" in activity.columns:
    st.subheader("Equivalent walking distance")
    fig3 = px.bar(activity, x="day", y="equivalent_walking_distance")
    fig3.update_layout(yaxis_title="Meters", xaxis_title="Date", height=320)
    st.plotly_chart(fig3)
