import sys
from pathlib import Path

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dashboard.data import load_daily_dataset
from dashboard import ai_insights

st.set_page_config(page_title="Sleep Analytics | Beyond the Oura", layout="wide")
st.title("Sleep Analytics")

df = load_daily_dataset()
if df.empty or df["sleep_score"].dropna().empty:
    st.warning("No sleep data available.")
    st.stop()

sleep = df.dropna(subset=["sleep_score"])

col1, col2, col3 = st.columns(3)
col1.metric("Avg sleep score", f"{sleep['sleep_score'].mean():.1f}")
col2.metric("Best night", f"{sleep['sleep_score'].max():.0f}",
            help=f"on {sleep.loc[sleep['sleep_score'].idxmax(), 'day'].date()}")
col3.metric("Worst night", f"{sleep['sleep_score'].min():.0f}",
            help=f"on {sleep.loc[sleep['sleep_score'].idxmin(), 'day'].date()}")

contributor_cols = ["deep_sleep", "rem_sleep", "restfulness", "sleep_efficiency",
                     "sleep_latency", "sleep_timing"]
available = [c for c in contributor_cols if c in sleep.columns]

midpoint = len(sleep) // 2
insight_stats = {
    "date_range": f"{sleep['day'].min().date()} to {sleep['day'].max().date()}",
    "num_nights": len(sleep),
    "avg_score": round(sleep["sleep_score"].mean(), 1),
    "latest_score": round(sleep["sleep_score"].iloc[-1], 1),
    "best_score": {"value": int(sleep["sleep_score"].max()),
                   "date": str(sleep.loc[sleep["sleep_score"].idxmax(), "day"].date())},
    "worst_score": {"value": int(sleep["sleep_score"].min()),
                    "date": str(sleep.loc[sleep["sleep_score"].idxmin(), "day"].date())},
    "first_half_avg": round(sleep["sleep_score"].iloc[:midpoint].mean(), 1) if midpoint else None,
    "second_half_avg": round(sleep["sleep_score"].iloc[midpoint:].mean(), 1) if midpoint else None,
    "contributor_averages": {c: round(sleep[c].mean(), 1) for c in available},
}
ai_fields = {
    "trend": "What the score trend suggests",
    "contributors": "What's driving your sleep quality",
}
ai_text = ai_insights.fetch("Sleep Analytics", insight_stats, ai_fields)

st.subheader("Sleep score over time")
if ai_text.get("trend"):
    ai_insights.show(ai_text["trend"])
fig = px.line(sleep, x="day", y="sleep_score", markers=True)
fig.update_layout(yaxis_title="Sleep score", xaxis_title="Date", height=380)
fig.add_hline(y=sleep["sleep_score"].mean(), line_dash="dot",
              annotation_text="average", opacity=0.5)
st.plotly_chart(fig)

st.subheader("Sleep stage contributors")
if ai_text.get("contributors"):
    ai_insights.show(ai_text["contributors"])
if available:
    fig2 = go.Figure()
    for col in available:
        fig2.add_trace(go.Scatter(x=sleep["day"], y=sleep[col], mode="lines",
                                   name=col.replace("_", " ").title()))
    fig2.update_layout(yaxis_title="Contributor score (0-100)", xaxis_title="Date", height=420,
                        legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig2)

    st.caption("Average contributor scores across the selected history")
    avg_contributors = sleep[available].mean().sort_values(ascending=True)
    fig3 = px.bar(avg_contributors, orientation="h",
                  labels={"value": "Average score", "index": ""})
    fig3.update_layout(showlegend=False, height=300)
    st.plotly_chart(fig3)
