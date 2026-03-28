"""
OpenF1 REST API client.
Polls all required endpoints and returns a normalised snapshot of the current race.
"""

import httpx
import asyncio
from typing import Optional
from backend.state import DRIVER_INFO

BASE_URL = "https://api.openf1.org/v1"
POLL_INTERVAL = 20  # seconds


async def get_latest_session_key(year: int = 2026, country: str = "Japan") -> Optional[int]:
    url = f"{BASE_URL}/sessions"
    params = {"year": year, "country_name": country, "session_type": "Race"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        sessions = resp.json()
        if sessions:
            return sessions[-1]["session_key"]
    return None


async def _get(client: httpx.AsyncClient, path: str, params: dict) -> list:
    try:
        resp = await client.get(f"{BASE_URL}{path}", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[OpenF1] {path} failed: {e}")
        return []


async def fetch_race_snapshot(session_key: int) -> dict:
    """
    Returns a dict with the latest data needed to build the feature vector.
    Keys: laps, positions, stints, pits, race_control
    """
    params = {"session_key": session_key}

    async with httpx.AsyncClient(timeout=15) as client:
        laps, positions, stints, pits, race_control = await asyncio.gather(
            _get(client, "/laps",         params),
            _get(client, "/position",     params),
            _get(client, "/stints",       params),
            _get(client, "/pit",          params),
            _get(client, "/race_control", params),
        )

    # Latest lap per driver
    latest_laps: dict[int, dict] = {}
    for lap in laps:
        dn = lap.get("driver_number")
        if dn and (dn not in latest_laps or lap["lap_number"] > latest_laps[dn]["lap_number"]):
            latest_laps[dn] = lap

    # Latest position per driver
    latest_positions: dict[int, int] = {}
    for pos in positions:
        dn = pos.get("driver_number")
        if dn:
            latest_positions[dn] = pos.get("position", 20)

    # Latest stint per driver (tire info)
    latest_stints: dict[int, dict] = {}
    for stint in stints:
        dn = stint.get("driver_number")
        if dn and (
            dn not in latest_stints
            or stint.get("stint_number", 0) >= latest_stints[dn].get("stint_number", 0)
        ):
            latest_stints[dn] = stint

    # Pit stop count per driver
    pit_counts: dict[int, int] = {}
    for pit in pits:
        dn = pit.get("driver_number")
        if dn:
            pit_counts[dn] = pit_counts.get(dn, 0) + 1

    # Safety car / VSC from race control
    safety_car = False
    vsc = False
    if race_control:
        latest_rc = race_control[-1]
        flag = latest_rc.get("flag", "")
        safety_car = flag == "SAFETY CAR"
        vsc = flag == "VIRTUAL SAFETY CAR"

    # Current lap number (max across all drivers)
    current_lap = max((l.get("lap_number", 0) for l in latest_laps.values()), default=0)

    return {
        "current_lap": current_lap,
        "safety_car": safety_car,
        "vsc": vsc,
        "latest_laps": latest_laps,
        "latest_positions": latest_positions,
        "latest_stints": latest_stints,
        "pit_counts": pit_counts,
    }


async def fetch_radio_clips(session_key: int, after_date: Optional[str] = None) -> list[dict]:
    """Returns new team radio entries since `after_date` (ISO string)."""
    params: dict = {"session_key": session_key}
    if after_date:
        params["date>"] = after_date

    async with httpx.AsyncClient(timeout=15) as client:
        clips = await _get(client, "/team_radio", params)

    return [
        {
            "driver_number": c.get("driver_number"),
            "recording_url": c.get("recording_url"),
            "date": c.get("date"),
        }
        for c in clips
        if c.get("recording_url")
    ]
