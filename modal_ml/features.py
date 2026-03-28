"""
Shared feature vector definition for training and inference.
Both train.py and inference.py import from here to guarantee consistency.
"""

from dataclasses import dataclass
from typing import Optional

FEATURE_COLUMNS = [
    "position",
    "gap_to_leader",
    "tire_age",
    "tire_compound",
    "pit_stops",
    "laps_remaining",
    "safety_car",
    "vsc",
    "radio_sentiment",
    "radio_pit_keyword",
    "position_change_3lap",
    "gap_delta_3lap",
]

COMPOUND_MAP = {
    "SOFT": 0,
    "MEDIUM": 1,
    "HARD": 2,
    "INTERMEDIATE": 3,
    "WET": 4,
    "UNKNOWN": 1,  # default to medium
}


@dataclass
class DriverFeatures:
    driver_number: int
    position: int
    gap_to_leader: float
    tire_age: int
    tire_compound: int         # encoded via COMPOUND_MAP
    pit_stops: int
    laps_remaining: int
    safety_car: int            # 0 or 1
    vsc: int                   # 0 or 1
    radio_sentiment: float     # VADER compound [-1, 1], default 0.0
    radio_pit_keyword: int     # 1 if pit/box mentioned in last 2 laps
    position_change_3lap: int  # positive = gained positions
    gap_delta_3lap: float      # negative = closing gap to leader

    def to_list(self) -> list:
        return [getattr(self, col) for col in FEATURE_COLUMNS]
