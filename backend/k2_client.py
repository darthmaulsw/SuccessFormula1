"""
K2 Think V2 (70B) client.
Generates one-line natural language insights per driver per lap.
Fire-and-forget: never blocks the main lap update cycle.
"""

import asyncio
import httpx
import os
from typing import Optional

K2_API_URL = os.getenv("K2_API_URL", "https://api.k2.ai/v1/chat/completions")
K2_API_KEY = os.getenv("K2_API_KEY", "")
K2_MODEL = os.getenv("K2_MODEL", "k2-think-v2-70b")

# Cache to avoid re-requesting the same driver+lap combo
_insight_cache: dict[tuple[int, int], str] = {}

FALLBACK_TEMPLATES = [
    "{name}'s probability shifted after track position changes on lap {lap}.",
    "{name} is holding position with {tire_age} laps on the current tire set.",
    "Strategy call incoming for {name} — tire age may force a pit soon.",
    "{name} benefits from the safety car gap reset on lap {lap}.",
]


async def get_insight(
    driver_number: int,
    name: str,
    lap: int,
    prob_delta: float,
    transcript: str,
    position: int,
    tire_compound: str,
    tire_age: int,
) -> str:
    cache_key = (driver_number, lap)
    if cache_key in _insight_cache:
        return _insight_cache[cache_key]

    if not K2_API_KEY:
        insight = _fallback_insight(name, lap, prob_delta, tire_age)
        _insight_cache[cache_key] = insight
        return insight

    direction = "rose" if prob_delta >= 0 else "fell"
    abs_delta = abs(prob_delta)

    prompt = (
        f"You are an F1 race analyst. In exactly one sentence (max 20 words), explain why "
        f"{name}'s win probability {direction} by {abs_delta:.0%} on lap {lap}. "
        f"They are currently P{position} on {tire_compound} tires (age {tire_age} laps). "
        f"Recent radio: \"{transcript or 'none'}\". Be specific and insightful."
    )

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(
                K2_API_URL,
                headers={
                    "Authorization": f"Bearer {K2_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": K2_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 60,
                    "temperature": 0.4,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            insight = data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[K2] Insight failed for {name} lap {lap}: {e}")
        insight = _fallback_insight(name, lap, prob_delta, tire_age)

    _insight_cache[cache_key] = insight
    return insight


async def batch_insights(drivers_data: list[dict]) -> dict[int, str]:
    """
    Request insights for multiple drivers concurrently.
    drivers_data: list of dicts with keys matching get_insight params.
    Returns {driver_number: insight_text}.
    """
    tasks = {
        d["driver_number"]: asyncio.create_task(
            get_insight(
                driver_number=d["driver_number"],
                name=d["name"],
                lap=d["lap"],
                prob_delta=d.get("prob_delta", 0.0),
                transcript=d.get("transcript", ""),
                position=d["position"],
                tire_compound=d.get("tire_compound", "MEDIUM"),
                tire_age=d.get("tire_age", 0),
            )
        )
        for d in drivers_data
    }
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    return {
        dn: (r if isinstance(r, str) else "Analyzing...")
        for dn, r in zip(tasks.keys(), results)
    }


def _fallback_insight(name: str, lap: int, prob_delta: float, tire_age: int) -> str:
    import random
    template = random.choice(FALLBACK_TEMPLATES)
    return template.format(name=name, lap=lap, tire_age=tire_age)
