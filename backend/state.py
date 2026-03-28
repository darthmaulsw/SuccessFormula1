"""
In-memory race state. Single source of truth shared across all backend modules.
The SSE endpoint broadcasts this state to all connected frontend clients.
"""

from dataclasses import dataclass, field
from typing import Optional
import time


@dataclass
class DriverState:
    driver_number: int
    name: str
    team: str
    team_color: str           # hex color for frontend
    position: int
    win_probability: float
    polymarket_probability: float
    edge: float               # win_probability - polymarket_probability
    tire_compound: str
    tire_age: int
    pit_stops: int
    last_insight: str
    last_radio: str
    radio_sentiment: float
    radio_keywords: list[str]


@dataclass
class RaceState:
    lap: int = 0
    total_laps: int = 53
    safety_car: bool = False
    vsc: bool = False
    session_key: Optional[int] = None
    last_updated: float = field(default_factory=time.time)
    drivers: list[DriverState] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "lap": self.lap,
            "total_laps": self.total_laps,
            "safety_car": self.safety_car,
            "vsc": self.vsc,
            "session_key": self.session_key,
            "last_updated": self.last_updated,
            "drivers": [
                {
                    "driver_number": d.driver_number,
                    "name": d.name,
                    "team": d.team,
                    "team_color": d.team_color,
                    "position": d.position,
                    "win_probability": d.win_probability,
                    "polymarket_probability": d.polymarket_probability,
                    "edge": round(d.edge, 4),
                    "tire_compound": d.tire_compound,
                    "tire_age": d.tire_age,
                    "pit_stops": d.pit_stops,
                    "last_insight": d.last_insight,
                    "last_radio": d.last_radio,
                    "radio_sentiment": d.radio_sentiment,
                    "radio_keywords": d.radio_keywords,
                }
                for d in sorted(self.drivers, key=lambda x: x.position)
            ],
        }


# Global singleton — imported by main.py and all clients
race_state = RaceState()

# Driver metadata: number → (name, team, team_color)
DRIVER_INFO: dict[int, tuple[str, str, str]] = {
    1:  ("Verstappen",  "Red Bull",       "#3671C6"),
    11: ("Perez",       "Red Bull",       "#3671C6"),
    16: ("Leclerc",     "Ferrari",        "#E8002D"),
    55: ("Sainz",       "Ferrari",        "#E8002D"),
    44: ("Hamilton",    "Mercedes",       "#27F4D2"),
    63: ("Russell",     "Mercedes",       "#27F4D2"),
    4:  ("Norris",      "McLaren",        "#FF8000"),
    81: ("Piastri",     "McLaren",        "#FF8000"),
    14: ("Alonso",      "Aston Martin",   "#229971"),
    18: ("Stroll",      "Aston Martin",   "#229971"),
    10: ("Gasly",       "Alpine",         "#0093CC"),
    31: ("Ocon",        "Alpine",         "#0093CC"),
    23: ("Albon",       "Williams",       "#64C4FF"),
    2:  ("Sargeant",    "Williams",       "#64C4FF"),
    77: ("Bottas",      "Kick Sauber",    "#52E252"),
    24: ("Zhou",        "Kick Sauber",    "#52E252"),
    20: ("Magnussen",   "Haas",           "#B6BABD"),
    27: ("Hulkenberg",  "Haas",           "#B6BABD"),
    22: ("Tsunoda",     "RB",             "#6692FF"),
    3:  ("Ricciardo",   "RB",             "#6692FF"),
}
