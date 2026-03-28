"""
Polymarket Gamma API client.
Fetches live win-market odds for the Japanese GP and normalises to [0,1] per driver.
"""

import httpx
from typing import Optional

GAMMA_BASE = "https://gamma-api.polymarket.com"
MARKET_SLUG = "f1-japanese-gp-2026"

# Fallback pre-race odds (used if Polymarket has no active market)
FALLBACK_ODDS: dict[int, float] = {
    1:  0.42,
    4:  0.18,
    16: 0.14,
    44: 0.08,
    81: 0.07,
    55: 0.05,
    63: 0.03,
    14: 0.02,
    11: 0.01,
}


async def fetch_polymarket_odds() -> dict[int, float]:
    """
    Returns {driver_number: implied_probability} normalised to sum 1.0.
    Falls back to FALLBACK_ODDS if the market is unavailable.
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{GAMMA_BASE}/markets",
                params={"slug": MARKET_SLUG},
            )
            resp.raise_for_status()
            markets = resp.json()

        if not markets:
            return _normalize(FALLBACK_ODDS)

        market = markets[0]
        outcomes = market.get("outcomes", [])
        prices_raw = market.get("outcomePrices", [])

        # outcomes is a JSON string in some versions — parse defensively
        import json
        if isinstance(outcomes, str):
            outcomes = json.loads(outcomes)
        if isinstance(prices_raw, str):
            prices_raw = json.loads(prices_raw)

        odds: dict[int, float] = {}
        for name, price in zip(outcomes, prices_raw):
            driver_number = _name_to_driver_number(name)
            if driver_number:
                odds[driver_number] = float(price)

        if not odds:
            return _normalize(FALLBACK_ODDS)

        return _normalize(odds)

    except Exception as e:
        print(f"[Polymarket] Failed to fetch odds: {e} — using fallback")
        return _normalize(FALLBACK_ODDS)


def _normalize(odds: dict[int, float]) -> dict[int, float]:
    total = sum(odds.values())
    if total == 0:
        return odds
    return {k: round(v / total, 4) for k, v in odds.items()}


# Map Polymarket outcome name → driver number
# Adjust these strings to match how Polymarket labels their outcomes
_NAME_MAP: dict[str, int] = {
    "verstappen": 1,
    "norris": 4,
    "leclerc": 16,
    "hamilton": 44,
    "piastri": 81,
    "sainz": 55,
    "russell": 63,
    "alonso": 14,
    "perez": 11,
    "tsunoda": 22,
}


def _name_to_driver_number(name: str) -> Optional[int]:
    lower = name.lower()
    for key, number in _NAME_MAP.items():
        if key in lower:
            return number
    return None
