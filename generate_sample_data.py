"""Generate a synthetic ~90-day dataset so this repo runs out of the box.

None of these numbers came from a real Oura Ring — they're fabricated from a
shared "wellness" latent variable (with a slow upward drift + weekly rhythm)
so that sleep/readiness/activity/heart-rate end up plausibly correlated,
which is what makes the dashboard's Insights and Correlation Explorer pages
worth looking at. Column names match what dashboard/data.py reads from a
real Oura export, so swapping in your own data (via `python main.py
download`) just means overwriting these files.

Run:
    python generate_sample_data.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
DAYS = 90
END_DATE = "2026-07-31"
SEED = 42


def clip_int(values: np.ndarray, low: int, high: int) -> np.ndarray:
    return np.clip(values, low, high).round().astype(int)


def main() -> None:
    rng = np.random.default_rng(SEED)
    days = pd.date_range(end=END_DATE, periods=DAYS, freq="D")
    t = np.arange(DAYS)

    # Latent daily wellness factor: slow improvement over the window + a
    # weekly rhythm (weekends skew differently) + day-to-day noise.
    drift = np.linspace(-4, 5, DAYS)
    weekly = 3 * np.sin(2 * np.pi * t / 7)
    wellness = drift + weekly + rng.normal(0, 6, DAYS)

    # ---- Sleep ----
    sleep_score = clip_int(74 + wellness * 0.9 + rng.normal(0, 4, DAYS), 45, 97)
    deep_sleep = clip_int(64 + wellness * 0.5 + rng.normal(0, 8, DAYS), 20, 95)
    efficiency = clip_int(88 + wellness * 0.2 + rng.normal(0, 5, DAYS), 60, 99)
    latency = clip_int(80 + rng.normal(0, 10, DAYS), 30, 99)
    rem_sleep = clip_int(70 + wellness * 0.3 + rng.normal(0, 7, DAYS), 30, 95)
    restfulness = clip_int(75 + wellness * 0.4 + rng.normal(0, 8, DAYS), 30, 98)
    timing = clip_int(80 + rng.normal(0, 12, DAYS), 20, 99)
    total_sleep_contrib = clip_int(78 + wellness * 0.3 + rng.normal(0, 6, DAYS), 40, 98)

    sleep_df = pd.DataFrame({
        "id": [f"sample-sleep-{i:03d}" for i in range(DAYS)],
        "day": days.strftime("%Y-%m-%d"),
        "score": sleep_score,
        "timestamp": days.strftime("%Y-%m-%dT00:00:00.000+00:00"),
        "contributors.deep_sleep": deep_sleep,
        "contributors.efficiency": efficiency,
        "contributors.latency": latency,
        "contributors.rem_sleep": rem_sleep,
        "contributors.restfulness": restfulness,
        "contributors.timing": timing,
        "contributors.total_sleep": total_sleep_contrib,
    })

    # ---- Activity ----
    activity_score = clip_int(72 + wellness * 0.7 + rng.normal(0, 5, DAYS), 40, 98)
    steps = clip_int(3200 + activity_score * 85 + rng.normal(0, 1100, DAYS), 800, 15000)
    total_calories = clip_int(1450 + steps * 0.09 + rng.normal(0, 70, DAYS), 1300, 3200)
    active_calories = clip_int(total_calories * 0.28 + rng.normal(0, 40, DAYS), 80, 900)
    equivalent_walking_distance = clip_int(steps * 0.72 + rng.normal(0, 200, DAYS), 500, 12000)
    high_activity_time = clip_int(np.maximum(0, (activity_score - 70)) * 25 + rng.normal(0, 200, DAYS), 0, 3600)
    medium_activity_time = clip_int(600 + activity_score * 15 + rng.normal(0, 300, DAYS), 0, 5400)
    low_activity_time = clip_int(2800 + rng.normal(0, 600, DAYS), 600, 6000)
    sedentary_time = clip_int(35000 - activity_score * 90 + rng.normal(0, 1500, DAYS), 18000, 46000)
    resting_time = clip_int(28000 - wellness * 100 + rng.normal(0, 1200, DAYS), 18000, 34000)
    average_met_minutes = np.round(1.1 + activity_score * 0.005 + rng.normal(0, 0.08, DAYS), 4)

    activity_df = pd.DataFrame({
        "id": [f"sample-activity-{i:03d}" for i in range(DAYS)],
        "day": days.strftime("%Y-%m-%d"),
        "score": activity_score,
        "steps": steps,
        "total_calories": total_calories,
        "active_calories": active_calories,
        "average_met_minutes": average_met_minutes,
        "high_activity_time": high_activity_time,
        "medium_activity_time": medium_activity_time,
        "low_activity_time": low_activity_time,
        "sedentary_time": sedentary_time,
        "resting_time": resting_time,
        "equivalent_walking_distance": equivalent_walking_distance,
        "target_calories": 550,
        "target_meters": 9000,
        "meters_to_target": clip_int(np.maximum(0, 9000 - equivalent_walking_distance), 0, 9000),
        "timestamp": days.strftime("%Y-%m-%dT04:00:00.000-05:00"),
    })

    # ---- Readiness (depends a bit on yesterday's activity + sleep) ----
    prev_activity = np.concatenate([[activity_score[0]], activity_score[:-1]])
    readiness_score = clip_int(
        70 + wellness * 0.6 + (sleep_score - 75) * 0.2 - (prev_activity - 72) * 0.05
        + rng.normal(0, 4, DAYS), 50, 97,
    )
    resting_bpm_daily = np.clip(60 - activity_score * 0.06 - wellness * 0.15 + rng.normal(0, 2.5, DAYS), 44, 68)
    temperature_deviation = np.round(rng.normal(0, 0.18, DAYS), 2)
    temperature_trend_deviation = np.round(pd.Series(temperature_deviation).rolling(5, min_periods=1).mean(), 2)

    activity_balance = clip_int(75 + wellness * 0.3 + rng.normal(0, 8, DAYS), 30, 99)
    body_temperature = clip_int(90 - np.abs(temperature_deviation) * 40 + rng.normal(0, 5, DAYS), 50, 99)
    hrv_balance = clip_int(70 + wellness * 0.5 + rng.normal(0, 9, DAYS), 25, 98)
    previous_day_activity = clip_int(70 + (prev_activity - 72) * 0.6 + rng.normal(0, 8, DAYS), 30, 99)
    previous_night = clip_int(70 + (sleep_score - 75) * 0.6 + rng.normal(0, 7, DAYS), 30, 99)
    recovery_index = clip_int(72 + wellness * 0.4 + rng.normal(0, 8, DAYS), 30, 98)
    resting_hr_contrib = clip_int(95 - (resting_bpm_daily - 55) * 1.5 + rng.normal(0, 6, DAYS), 40, 100)
    sleep_balance = clip_int(74 + (sleep_score - 75) * 0.4 + rng.normal(0, 8, DAYS), 30, 99)
    sleep_regularity = clip_int(78 + rng.normal(0, 9, DAYS), 30, 99)

    readiness_df = pd.DataFrame({
        "id": [f"sample-readiness-{i:03d}" for i in range(DAYS)],
        "day": days.strftime("%Y-%m-%d"),
        "score": readiness_score,
        "temperature_deviation": temperature_deviation,
        "temperature_trend_deviation": temperature_trend_deviation,
        "timestamp": days.strftime("%Y-%m-%dT00:00:00.000+00:00"),
        "contributors.activity_balance": activity_balance,
        "contributors.body_temperature": body_temperature,
        "contributors.hrv_balance": hrv_balance,
        "contributors.previous_day_activity": previous_day_activity,
        "contributors.previous_night": previous_night,
        "contributors.recovery_index": recovery_index,
        "contributors.resting_heart_rate": resting_hr_contrib,
        "contributors.sleep_balance": sleep_balance,
        "contributors.sleep_regularity": sleep_regularity,
    })

    # ---- Heart rate (5-minute samples, resting overnight + a workout block) ----
    hr_rows = []
    for i, day in enumerate(days):
        baseline = resting_bpm_daily[i]
        workout_start = rng.integers(10, 20)  # hour of day
        for minute in range(0, 24 * 60, 5):
            hour = minute // 60
            ts = day + pd.Timedelta(minutes=minute)
            if 0 <= hour < 6:
                source, bpm = "rest", baseline + rng.normal(0, 2.5)
            elif workout_start <= hour < workout_start + 1:
                source, bpm = "workout", baseline + 55 + rng.normal(0, 10)
            else:
                source, bpm = "awake", baseline + 15 + rng.normal(0, 6)
            hr_rows.append((ts, max(38, round(bpm)), source))

    hr_df = pd.DataFrame(hr_rows, columns=["timestamp", "bpm", "source"])
    hr_df["timestamp"] = hr_df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    hr_df["producer_timestamp"] = 0
    hr_df = hr_df[["timestamp", "bpm", "producer_timestamp", "source"]]

    # ---- Personal info (fabricated profile, not a real person) ----
    personal_df = pd.DataFrame([{
        "id": "sample-profile-001",
        "age": 29,
        "weight": 68.0,
        "height": 1.75,
        "biological_sex": "male",
        "email": "demo@example.com",
    }])

    DATA_DIR.mkdir(exist_ok=True)
    sleep_df.to_csv(DATA_DIR / "daily_sleep.csv", index=False)
    readiness_df.to_csv(DATA_DIR / "daily_readiness.csv", index=False)
    activity_df.to_csv(DATA_DIR / "daily_activity.csv", index=False)
    hr_df.to_csv(DATA_DIR / "heart_rate.csv", index=False)
    personal_df.to_csv(DATA_DIR / "personal_info.csv", index=False)

    print(f"Wrote {DAYS} days of synthetic data to {DATA_DIR}/")


if __name__ == "__main__":
    main()
