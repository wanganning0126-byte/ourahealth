import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dashboard.data import load_daily_dataset, load_personal_info

st.set_page_config(page_title="Executive Overview | Beyond the Oura", layout="wide")


def filter_by_date(df, start, end):
    mask = (df["day"].dt.date >= start) & (df["day"].dt.date <= end)
    return df.loc[mask]


def kpi_delta(series):
    """Compare the mean of the second half of the window to the first half."""
    series = series.dropna()
    if len(series) < 4:
        return None
    midpoint = len(series) // 2
    first_half, second_half = series.iloc[:midpoint], series.iloc[midpoint:]
    return second_half.mean() - first_half.mean()


df = load_daily_dataset()
info = load_personal_info()

st.title("Executive Overview")
st.caption("Beyond the Oura — a personal wearable health analytics platform")

if df.empty:
    st.warning("No data found in `data/`. Run `python main.py download` first.")
    st.stop()

with st.sidebar:
    st.header("Filters")
    min_day, max_day = df["day"].min().date(), df["day"].max().date()
    date_range = st.date_input(
        "Date range", value=(min_day, max_day), min_value=min_day, max_value=max_day
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = date_range
    else:
        start, end = min_day, max_day

    st.divider()
    st.header("Profile")
    if info:
        st.write(f"**Age:** {info.get('age', '—')}")
        st.write(f"**Sex:** {info.get('biological_sex', '—')}")
        st.write(f"**Weight:** {info.get('weight', '—')} kg")
        st.write(f"**Height:** {info.get('height', '—')} m")

view = filter_by_date(df, start, end)

if view.empty:
    st.info("No data in the selected date range.")
    st.stop()

st.subheader(f"{len(view)} days · {start} to {end}")

kpi_cols = st.columns(5)
kpis = [
    ("Sleep score", "sleep_score", ""),
    ("Readiness score", "readiness_score", ""),
    ("Activity score", "activity_score", ""),
    ("Steps / day", "steps", ""),
    ("Resting HR", "resting_bpm", " bpm"),
]
for col, (label, field, unit) in zip(kpi_cols, kpis):
    with col:
        if field in view.columns and view[field].notna().any():
            current = view[field].mean()
            delta = kpi_delta(view[field])
            delta_str = f"{delta:+.1f}{unit}" if delta is not None else None
            value_str = f"{current:,.0f}{unit}" if field == "steps" else f"{current:.1f}{unit}"
            st.metric(label, value_str, delta_str)
        else:
            st.metric(label, "—")

st.divider()

st.subheader("Score trends")
fig = go.Figure()
for field, name in [("sleep_score", "Sleep"), ("readiness_score", "Readiness"),
                     ("activity_score", "Activity")]:
    if field in view.columns:
        fig.add_trace(go.Scatter(x=view["day"], y=view[field], mode="lines+markers", name=name))
fig.update_layout(yaxis_title="Score (0-100)", xaxis_title="Date", height=420,
                   legend=dict(orientation="h", yanchor="bottom", y=1.02))
st.plotly_chart(fig)

st.subheader("Daily detail")
display_cols = [c for c in ["day", "sleep_score", "readiness_score", "activity_score",
                             "steps", "resting_bpm"] if c in view.columns]
st.dataframe(
    view[display_cols].sort_values("day", ascending=False).rename(columns={"day": "Date"}),
    width="stretch", hide_index=True,
)
