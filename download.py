"""
Download Oura health data and save each dataset as a CSV file in data/.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from auth import API_BASE, get_valid_access_token

DATA_DIR = Path(__file__).parent / "data"


def _date_range() -> tuple[str, str]:
    """Return (start_date, end_date) as YYYY-MM-DD strings."""
    load_dotenv()
    days_back = int(os.getenv("DAYS_BACK", "365"))
    end = date.today()
    start = end - timedelta(days=days_back)
    return start.isoformat(), end.isoformat()


def _datetime_range() -> tuple[str, str]:
    """Return (start_datetime, end_datetime) for heart rate API."""
    start_date, end_date = _date_range()
    return f"{start_date}T00:00:00", f"{end_date}T23:59:59"


def _api_get(access_token: str, endpoint: str, params: dict | None = None) -> dict | list:
    """
    Make an authenticated GET request to the Oura API.

    Most endpoints return {"data": [...], "next_token": "..."} for pagination.
    personal_info returns a single object with no wrapper.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{API_BASE}{endpoint}"
    response = requests.get(url, headers=headers, params=params or {}, timeout=60)
    response.raise_for_status()
    return response.json()


def _fetch_paginated(access_token: str, endpoint: str, params: dict) -> list:
    """Fetch all pages of a paginated Oura endpoint."""
    all_records: list = []
    while True:
        result = _api_get(access_token, endpoint, params)
        if isinstance(result, list):
            return result
        all_records.extend(result.get("data", []))
        next_token = result.get("next_token")
        if not next_token:
            break
        params = {**params, "next_token": next_token}
    return all_records


def _save_json_records(records: list | dict, filename: str) -> Path:
    """
    Flatten nested JSON (like Oura's 'contributors' dicts) and write CSV.

    pandas.json_normalize turns nested objects into flat columns,
    e.g. contributors.deep_sleep becomes its own column.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / filename

    if isinstance(records, dict):
        df = pd.json_normalize(records)
    elif not records:
        print(f"  No data for {filename} — skipping.")
        return path
    else:
        df = pd.json_normalize(records)

    df.to_csv(path, index=False)
    print(f"  Saved {len(df)} rows → {path}")
    return path


def download_all() -> None:
    """Fetch all requested Oura data types and save to data/*.csv."""
    print("\nGetting access token...")
    token = get_valid_access_token()

    start_date, end_date = _date_range()
    start_dt, end_dt = _datetime_range()
    print(f"Date range: {start_date} to {end_date}\n")

    # --- Personal info (single record, not date-filtered) ---
    print("Downloading personal info...")
    personal = _api_get(token, "/usercollection/personal_info")
    _save_json_records(personal, "personal_info.csv")

    # --- Daily summaries ---
    date_params = {"start_date": start_date, "end_date": end_date}

    print("Downloading daily sleep...")
    sleep = _fetch_paginated(token, "/usercollection/daily_sleep", date_params.copy())
    _save_json_records(sleep, "daily_sleep.csv")

    print("Downloading daily readiness...")
    readiness = _fetch_paginated(token, "/usercollection/daily_readiness", date_params.copy())
    _save_json_records(readiness, "daily_readiness.csv")

    print("Downloading daily activity...")
    activity = _fetch_paginated(token, "/usercollection/daily_activity", date_params.copy())
    _save_json_records(activity, "daily_activity.csv")

    # --- Heart rate (time series — fetched in weekly chunks) ---
    print("Downloading heart rate (this may take a minute for long date ranges)...")
    heart_rate_records = _fetch_heart_rate_in_chunks(token, start_dt, end_dt)
    _save_json_records(heart_rate_records, "heart_rate.csv")

    print("\nAll downloads complete! Check the data/ folder.")


def _fetch_heart_rate_in_chunks(
    access_token: str,
    start_datetime: str,
    end_datetime: str,
    chunk_days: int = 7,
) -> list:
    """Heart rate data can be huge — fetch week-by-week to avoid timeouts."""
    start = datetime.fromisoformat(start_datetime)
    end = datetime.fromisoformat(end_datetime)
    all_records: list = []

    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + timedelta(days=chunk_days), end)
        params = {
            "start_datetime": chunk_start.strftime("%Y-%m-%dT%H:%M:%S"),
            "end_datetime": chunk_end.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        records = _fetch_paginated(access_token, "/usercollection/heartrate", params)
        all_records.extend(records)
        print(f"    {chunk_start.date()} → {chunk_end.date()}: {len(records)} samples")
        chunk_start = chunk_end

    return all_records
