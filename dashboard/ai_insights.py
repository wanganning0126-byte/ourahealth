"""AI-generated narrative insights, backed by the OpenAI API.

Each page computes its own compact stats dict, then calls generate() with a
section-specific prompt. Results are cached by Streamlit keyed on the stats
themselves, so the API is only called again when the underlying data changes
(e.g. new days downloaded, or the date filter changes) — not on every rerun.

If OPENAI_API_KEY isn't set, generate() returns None and callers fall back
to showing nothing (or their own rule-based text).
"""
from __future__ import annotations

import json
import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = (
    "You are a data analyst writing short, grounded observations about someone's "
    "wearable health data (Oura Ring) for a personal dashboard. Rules:\n"
    "- Use ONLY the numbers given in the stats JSON. Never invent a number.\n"
    "- Write 2-3 sentences per field, plain language, second person (\"your\").\n"
    "- Point out what's notable (trend direction, standout days, imbalance) and a "
    "plausible, non-alarmist interpretation. You are not a doctor — never diagnose "
    "conditions or give medical advice, just observations.\n"
    "- If the history is short (under ~30 days), note that the pattern is early "
    "and will get clearer with more data, when relevant.\n"
    "- Return strict JSON matching the requested keys, no markdown, no extra keys."
)


def _client():
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    from openai import OpenAI
    return OpenAI(api_key=api_key)


@st.cache_data(show_spinner="Generating AI insights...")
def generate(section: str, stats_json: str, fields: tuple[str, ...]) -> dict | None:
    """Return {field: insight text} for the given fields, or None if unavailable."""
    client = _client()
    if client is None:
        return None

    user_prompt = (
        f"Dashboard section: {section}\n"
        f"Stats:\n{stats_json}\n\n"
        f"Return a JSON object with exactly these keys: {list(fields)}. "
        f"Each value is your written insight for that field."
    )
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
            max_tokens=700,
        )
        result = json.loads(response.choices[0].message.content)
        return {f: result[f] for f in fields if f in result}
    except Exception as exc:
        return {"_error": str(exc)}


def stats_to_json(stats: dict) -> str:
    """Deterministic JSON so identical data hits the Streamlit cache."""
    return json.dumps(stats, sort_keys=True, default=str)


def fetch(section: str, stats: dict, fields: dict[str, str]) -> dict[str, str]:
    """Fetch insight text for each field key. Returns {} if unavailable.

    Call once per page (results are cached), then place each field's text
    with show() wherever it belongs — e.g. right above the matching chart.
    """
    if _client() is None:
        return {}
    result = generate(section, stats_to_json(stats), tuple(fields.keys()))
    if not result:
        return {}
    if "_error" in result:
        st.caption(f"AI insights unavailable: {result['_error'][:150]}")
        return {}
    return {k: v for k, v in result.items() if v}


def show(text: str) -> None:
    st.info(text, icon="✨")
