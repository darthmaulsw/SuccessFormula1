"""
FastAPI backend — orchestrates the full pipeline and streams state to the frontend via SSE.

Start:  uvicorn backend.main:app --reload --port 8000

Env vars:
  MODAL_INFERENCE_URL  — full URL of deployed Modal /predict endpoint
  K2_API_KEY           — K2 Think V2 API key
  K2_API_URL           — K2 endpoint (default set in k2_client.py)
  DEMO_MODE            — set to "1" to replay suzuka_replay_2024.json
"""

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.state import RaceState, DriverState, DRIVER_INFO, race_state
from backend.openf1_client import fetch_race_snapshot, fetch_radio_clips, get_latest_session_key
from backend.polymarket_client import fetch_polymarket_odds
from backend.radio_processor import process_clips
from backend.k2_client import batch_insights
from modal_ml.features import COMPOUND_MAP

MODAL_INFERENCE_URL = os.getenv("MODAL_INFERENCE_URL", "")
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"
POLL_INTERVAL = 20  # seconds
TOTAL_LAPS = 53


# ---------------------------------------------------------------------------
# Background polling loop
# ---------------------------------------------------------------------------

async def poll_loop():
    """Main loop: poll OpenF1 → build features → call Modal → update state → broadcast."""
    global race_state

    if DEMO_MODE:
        await demo_loop()
        return

    # Discover session key
    print("[Main] Fetching session key...")
    session_key = await get_latest_session_key()
    if not session_key:
        print("[Main] No session key found — falling back to demo mode")
        await demo_loop()
        return

    race_state.session_key = session_key
    print(f"[Main] Session key: {session_key}")

    last_radio_date: str | None = None
    # Per-driver radio state for feature injection
    radio_state: dict[int, dict] = {}  # driver_number → {sentiment, pit_keyword, transcript, keywords}

    # Previous probabilities for delta calculation
    prev_probs: dict[int, float] = {}

    while True:
        try:
            # 1. Fetch OpenF1 snapshot + Polymarket odds concurrently
            snapshot, pm_odds = await asyncio.gather(
                fetch_race_snapshot(session_key),
                fetch_polymarket_odds(),
            )

            current_lap = snapshot["current_lap"]
            if current_lap == 0:
                print("[Main] Race not started yet, waiting...")
                await asyncio.sleep(POLL_INTERVAL)
                continue

            race_state.lap = current_lap
            race_state.safety_car = snapshot["safety_car"]
            race_state.vsc = snapshot["vsc"]
            race_state.last_updated = time.time()

            # 2. Build feature payload for Modal
            driver_features = []
            for dn, info in DRIVER_INFO.items():
                lap_data = snapshot["latest_laps"].get(dn, {})
                stint_data = snapshot["latest_stints"].get(dn, {})
                radio = radio_state.get(dn, {})

                position = snapshot["latest_positions"].get(dn, 20)
                gap = float(lap_data.get("gap_to_leader", 0) or 0)
                tire_age = int(stint_data.get("tyre_life", 1) or 1)
                compound_str = (stint_data.get("compound") or "MEDIUM").upper()
                tire_compound = COMPOUND_MAP.get(compound_str, 1)
                pit_stops = snapshot["pit_counts"].get(dn, 0)
                laps_remaining = max(TOTAL_LAPS - current_lap, 0)

                driver_features.append({
                    "driver_number": dn,
                    "position": position,
                    "gap_to_leader": gap,
                    "tire_age": tire_age,
                    "tire_compound": tire_compound,
                    "pit_stops": pit_stops,
                    "laps_remaining": laps_remaining,
                    "safety_car": int(snapshot["safety_car"]),
                    "vsc": int(snapshot["vsc"]),
                    "radio_sentiment": radio.get("sentiment", 0.0),
                    "radio_pit_keyword": int(radio.get("pit_keyword", False)),
                    "position_change_3lap": 0,  # TODO: track history
                    "gap_delta_3lap": 0.0,
                })

            # 3. Call Modal inference
            win_probs: dict[int, float] = {}
            if MODAL_INFERENCE_URL and driver_features:
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        resp = await client.post(
                            MODAL_INFERENCE_URL,
                            json={"drivers": driver_features},
                        )
                        resp.raise_for_status()
                        data = resp.json()
                        for pred in data.get("predictions", []):
                            win_probs[pred["driver_number"]] = pred["win_probability"]
                except Exception as e:
                    print(f"[Modal] Inference failed: {e}")

            # If Modal failed, use a simple inverse-position heuristic
            if not win_probs:
                total = sum(1.0 / max(f["position"], 1) for f in driver_features)
                win_probs = {
                    f["driver_number"]: round((1.0 / max(f["position"], 1)) / total, 4)
                    for f in driver_features
                }

            # 4. Process new radio clips (async, best-effort)
            try:
                new_clips = await fetch_radio_clips(session_key, after_date=last_radio_date)
                if new_clips:
                    last_radio_date = new_clips[-1].get("date")
                    processed = await process_clips(new_clips)
                    for r in processed:
                        radio_state[r["driver_number"]] = r
            except Exception as e:
                print(f"[Radio] Processing failed: {e}")

            # 5. K2 insights for drivers with >3% probability change
            drivers_for_k2 = []
            for df in driver_features:
                dn = df["driver_number"]
                prev = prev_probs.get(dn, win_probs.get(dn, 0))
                delta = win_probs.get(dn, 0) - prev
                if abs(delta) >= 0.03 or dn not in prev_probs:
                    name, _, _ = DRIVER_INFO.get(dn, (str(dn), "", ""))
                    radio = radio_state.get(dn, {})
                    drivers_for_k2.append({
                        "driver_number": dn,
                        "name": name,
                        "lap": current_lap,
                        "prob_delta": delta,
                        "transcript": radio.get("transcript", ""),
                        "position": df["position"],
                        "tire_compound": (snapshot["latest_stints"].get(dn, {}).get("compound") or "MEDIUM").upper(),
                        "tire_age": df["tire_age"],
                    })

            k2_insights: dict[int, str] = {}
            if drivers_for_k2:
                try:
                    k2_insights = await batch_insights(drivers_for_k2)
                except Exception as e:
                    print(f"[K2] Batch insights failed: {e}")

            # 6. Build updated driver states
            new_drivers = []
            for df in driver_features:
                dn = df["driver_number"]
                name, team, color = DRIVER_INFO.get(dn, (str(dn), "Unknown", "#FFFFFF"))
                win_p = win_probs.get(dn, 0.0)
                pm_p = pm_odds.get(dn, 0.0)
                radio = radio_state.get(dn, {})
                stint = snapshot["latest_stints"].get(dn, {})

                new_drivers.append(DriverState(
                    driver_number=dn,
                    name=name,
                    team=team,
                    team_color=color,
                    position=df["position"],
                    win_probability=win_p,
                    polymarket_probability=pm_p,
                    edge=round(win_p - pm_p, 4),
                    tire_compound=(stint.get("compound") or "MEDIUM").upper(),
                    tire_age=df["tire_age"],
                    pit_stops=df["pit_stops"],
                    last_insight=k2_insights.get(dn, "Analyzing..."),
                    last_radio=radio.get("transcript", ""),
                    radio_sentiment=radio.get("sentiment", 0.0),
                    radio_keywords=radio.get("keywords", []),
                ))

            race_state.drivers = new_drivers
            prev_probs = dict(win_probs)
            print(f"[Main] Lap {current_lap} updated — {len(new_drivers)} drivers")

        except Exception as e:
            print(f"[Main] Poll loop error: {e}")

        await asyncio.sleep(POLL_INTERVAL)


async def demo_loop():
    """Replay suzuka_replay_2024.json lap by lap for demo/fallback mode."""
    global race_state

    replay_path = os.path.join(os.path.dirname(__file__), "..", "data", "suzuka_replay_2024.json")
    try:
        with open(replay_path) as f:
            replay_laps: list[dict] = json.load(f)
    except FileNotFoundError:
        print("[Demo] Replay file not found — generating synthetic data")
        replay_laps = _generate_synthetic_replay()

    print(f"[Demo] Replaying {len(replay_laps)} laps")
    idx = 0
    while True:
        frame = replay_laps[idx % len(replay_laps)]
        race_state.lap = frame["lap"]
        race_state.safety_car = frame.get("safety_car", False)
        race_state.vsc = frame.get("vsc", False)
        race_state.last_updated = time.time()
        race_state.drivers = [DriverState(**d) for d in frame["drivers"]]
        idx += 1
        await asyncio.sleep(5)  # faster replay for demo


def _generate_synthetic_replay() -> list[dict]:
    """Minimal synthetic replay so demo mode works without a data file."""
    import random
    drivers_base = [
        (1, "Verstappen", "Red Bull", "#3671C6"),
        (4, "Norris", "McLaren", "#FF8000"),
        (16, "Leclerc", "Ferrari", "#E8002D"),
        (44, "Hamilton", "Mercedes", "#27F4D2"),
        (81, "Piastri", "McLaren", "#FF8000"),
    ]
    laps = []
    probs = {dn: round(1.0 / len(drivers_base), 3) for dn, *_ in drivers_base}
    for lap_num in range(1, 54):
        # Random probability walk
        for dn in probs:
            probs[dn] = max(0.01, probs[dn] + random.uniform(-0.02, 0.02))
        total = sum(probs.values())
        norm = {dn: round(p / total, 4) for dn, p in probs.items()}
        drivers = []
        for i, (dn, name, team, color) in enumerate(drivers_base):
            p = norm[dn]
            pm = max(0.01, p + random.uniform(-0.05, 0.05))
            drivers.append({
                "driver_number": dn, "name": name, "team": team, "team_color": color,
                "position": i + 1, "win_probability": p, "polymarket_probability": round(pm, 4),
                "edge": round(p - pm, 4), "tire_compound": random.choice(["SOFT","MEDIUM","HARD"]),
                "tire_age": lap_num % 20 + 1, "pit_stops": lap_num // 20,
                "last_insight": f"{name} is {'pushing' if lap_num % 3 else 'conserving'} on lap {lap_num}.",
                "last_radio": "", "radio_sentiment": 0.0, "radio_keywords": [],
            })
        laps.append({"lap": lap_num, "safety_car": lap_num == 15, "vsc": False, "drivers": drivers})
    return laps


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(poll_loop())
    yield
    task.cancel()


app = FastAPI(title="SuccessFormula1 API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def event_generator() -> AsyncGenerator[str, None]:
    last_sent = 0.0
    while True:
        if race_state.last_updated > last_sent:
            last_sent = race_state.last_updated
            data = json.dumps(race_state.to_dict())
            yield f"data: {data}\n\n"
        await asyncio.sleep(1)


@app.get("/stream")
async def stream():
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/state")
async def get_state():
    """One-shot JSON snapshot — useful for debugging."""
    return race_state.to_dict()


@app.get("/health")
async def health():
    return {"status": "ok", "lap": race_state.lap, "demo_mode": DEMO_MODE}
