"""Shared data loading and cleaning for the dashboard.

Reads the raw CSVs produced by download.py, cleans/renames columns, and
merges sleep, readiness, activity, and heart rate into one daily table.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _read_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _load_sleep() -> pd.DataFrame:
    df = _read_csv("daily_sleep.csv")
    if df.empty:
        return df
    df = df.rename(columns={
        "score": "sleep_score",
        "contributors.deep_sleep": "deep_sleep",
        "contributors.efficiency": "sleep_efficiency",
        "contributors.latency": "sleep_latency",
        "contributors.rem_sleep": "rem_sleep",
        "contributors.restfulness": "restfulness",
        "contributors.timing": "sleep_timing",
        "contributors.total_sleep": "total_sleep_contributor",
    })
    cols = ["day", "sleep_score", "deep_sleep", "sleep_efficiency", "sleep_latency",
            "rem_sleep", "restfulness", "sleep_timing", "total_sleep_contributor"]
    return df[[c for c in cols if c in df.columns]]


def _load_readiness() -> pd.DataFrame:
    df = _read_csv("daily_readiness.csv")
    if df.empty:
        return df
    df = df.rename(columns={
        "score": "readiness_score",
        "contributors.activity_balance": "activity_balance",
        "contributors.body_temperature": "body_temperature",
        "contributors.hrv_balance": "hrv_balance",
        "contributors.previous_day_activity": "previous_day_activity",
        "contributors.previous_night": "previous_night",
        "contributors.recovery_index": "recovery_index",
        "contributors.resting_heart_rate": "resting_heart_rate_contributor",
        "contributors.sleep_balance": "sleep_balance",
        "contributors.sleep_regularity": "sleep_regularity",
    })
    cols = ["day", "readiness_score", "temperature_deviation", "temperature_trend_deviation",
            "activity_balance", "body_temperature", "hrv_balance", "previous_day_activity",
            "previous_night", "recovery_index", "resting_heart_rate_contributor",
            "sleep_balance", "sleep_regularity"]
    return df[[c for c in cols if c in df.columns]]


def _load_activity() -> pd.DataFrame:
    df = _read_csv("daily_activity.csv")
    if df.empty:
        return df
    df = df.rename(columns={"score": "activity_score"})
    cols = ["day", "activity_score", "steps", "total_calories", "active_calories",
            "average_met_minutes", "high_activity_time", "medium_activity_time",
            "low_activity_time", "sedentary_time", "resting_time",
            "equivalent_walking_distance", "target_calories", "target_meters",
            "meters_to_target"]
    return df[[c for c in cols if c in df.columns]]


def _load_heart_rate_daily() -> pd.DataFrame:
    df = _read_csv("heart_rate.csv")
    if df.empty:
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["day"] = df["timestamp"].dt.tz_convert(None).dt.date.astype(str)

    daily = df.groupby("day")["bpm"].agg(avg_bpm="mean", min_bpm="min", max_bpm="max")
    resting = (df[df["source"] == "rest"].groupby("day")["bpm"].mean()
               .rename("resting_bpm"))
    daily = daily.join(resting, how="left")
    return daily.reset_index()


@st.cache_data(ttl=600)
def load_personal_info() -> dict:
    df = _read_csv("personal_info.csv")
    if df.empty:
        return {}
    return df.iloc[0].to_dict()


@st.cache_data(ttl=600)
def load_daily_dataset() -> pd.DataFrame:
    """One row per day, merging sleep, readiness, activity, and heart rate."""
    sleep = _load_sleep()
    readiness = _load_readiness()
    activity = _load_activity()
    heart_rate = _load_heart_rate_daily()

    frames = [f for f in [sleep, readiness, activity, heart_rate] if not f.empty]
    if not frames:
        return pd.DataFrame()

    merged = frames[0]
    for frame in frames[1:]:
        merged = merged.merge(frame, on="day", how="outer")

    merged["day"] = pd.to_datetime(merged["day"])
    merged = merged.sort_values("day").reset_index(drop=True)

    # Convert activity durations from seconds to minutes for readability.
    for col in ["high_activity_time", "medium_activity_time", "low_activity_time",
                "sedentary_time", "resting_time"]:
        if col in merged.columns:
            merged[col + "_min"] = merged[col] / 60.0

    return merged


def numeric_score_columns(df: pd.DataFrame) -> list[str]:
    """Columns suitable for the correlation explorer (numeric, not ids/dates)."""
    exclude = {"day"}
    return [c for c in df.select_dtypes(include=[np.number]).columns if c not in exclude]
