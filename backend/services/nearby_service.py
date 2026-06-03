"""
backend/services/nearby_service.py — Nearby Cities & Sub-region Logic
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class NearbyCity:
    name:        str
    distance_km: float
    drive_hours: float
    description: str
    style_match: List[str]
    emoji:       str = "📍"


NEARBY_DB: Dict[str, Dict] = {
    "goa": {
        "sub_regions":  ["North Goa", "South Goa"],
        "split_days":   {"North Goa": 0.45, "South Goa": 0.55},
        "auto_split_max_days": 7,
        "nearby": [
            NearbyCity("Gokarna",   120, 2.5, "Pristine beaches, less crowded, spiritual vibe",    ["relaxation","adventure","photography"], "🏖️"),
            NearbyCity("Coorg",     250, 5.0, "Coffee estates, waterfalls, misty hills",            ["relaxation","nature","photography"],     "☕"),
            NearbyCity("Hampi",     340, 7.0, "UNESCO ruins, boulder landscapes, history",          ["culture","adventure","photography"],     "🏛️"),
            NearbyCity("Mangalore", 100, 2.0, "Coastal city, seafood, temples",                     ["food","culture"],                        "🌊"),
        ],
    },
    "dubai": {
        "sub_regions":  ["Downtown Dubai", "Dubai Marina", "Deira & Old Dubai"],
        "split_days":   {"Downtown Dubai": 0.40, "Dubai Marina": 0.35, "Deira & Old Dubai": 0.25},
        "auto_split_max_days": 10,
        "nearby": [
            NearbyCity("Abu Dhabi", 140, 1.5, "Grand Mosque, Ferrari World, Louvre",  ["culture","family","luxury"],  "🕌"),
            NearbyCity("Sharjah",   30,  0.5, "Art museums, heritage area, budget",   ["culture","budget"],           "🎨"),
            NearbyCity("Fujairah",  130, 1.5, "East coast beaches, diving, forts",    ["adventure","relaxation"],     "🤿"),
        ],
    },
    "manali": {
        "sub_regions":  ["Old Manali", "Solang Valley", "Rohtang Pass Area"],
        "split_days":   {"Old Manali": 0.30, "Solang Valley": 0.35, "Rohtang Pass Area": 0.35},
        "auto_split_max_days": 6,
        "nearby": [
            NearbyCity("Kasol",     75,  2.0, "Hippie haven, riverside camps, treks",  ["adventure","relaxation"],    "🏕️"),
            NearbyCity("Spiti",     200, 5.0, "High altitude desert, monasteries",     ["adventure","culture","photography"], "🏔️"),
            NearbyCity("Dharamshala", 250, 6.0, "Tibetan culture, Dalai Lama temple", ["culture","relaxation"],       "🙏"),
        ],
    },
    "kerala": {
        "sub_regions":  ["Alleppey Backwaters", "Munnar Hills", "Kovalam Beach"],
        "split_days":   {"Alleppey Backwaters": 0.35, "Munnar Hills": 0.35, "Kovalam Beach": 0.30},
        "auto_split_max_days": 8,
        "nearby": [
            NearbyCity("Coorg",    270, 5.5, "Coffee estates, misty hills",        ["relaxation","nature"],           "☕"),
            NearbyCity("Pondicherry", 550, 10.0, "French colony, beaches, yoga",   ["culture","relaxation"],          "🇫🇷"),
            NearbyCity("Wayanad",  100, 2.5, "Wildlife, tribal culture, waterfalls",["adventure","nature"],           "🌿"),
        ],
    },
    "rajasthan": {
        "sub_regions":  ["Jaipur", "Jodhpur", "Udaipur"],
        "split_days":   {"Jaipur": 0.35, "Jodhpur": 0.30, "Udaipur": 0.35},
        "auto_split_max_days": 10,
        "nearby": [
            NearbyCity("Pushkar",   150, 3.0, "Holy lake, camel fair, Brahma temple", ["culture","relaxation"],       "🐪"),
            NearbyCity("Jaisalmer", 290, 5.5, "Golden fort, desert safari",           ["adventure","culture"],        "🏰"),
            NearbyCity("Mount Abu", 160, 3.0, "Only hill station in Rajasthan",       ["relaxation","nature"],        "⛰️"),
        ],
    },
    "leh": {
        "sub_regions":  ["Leh Town", "Nubra Valley", "Pangong Lake"],
        "split_days":   {"Leh Town": 0.25, "Nubra Valley": 0.35, "Pangong Lake": 0.40},
        "auto_split_max_days": 10,
        "nearby": [
            NearbyCity("Kargil",    230, 5.0, "Scenic drive, war memorial, villages", ["adventure","culture"],        "🏔️"),
            NearbyCity("Zanskar",   240, 6.0, "Remote valley, monastery treks",       ["adventure","photography"],    "🗻"),
        ],
    },
    "ladakh": {
        "sub_regions":  ["Leh Town", "Nubra Valley", "Pangong Lake"],
        "split_days":   {"Leh Town": 0.25, "Nubra Valley": 0.35, "Pangong Lake": 0.40},
        "auto_split_max_days": 10,
        "nearby": [
            NearbyCity("Kargil",    230, 5.0, "War memorial, scenic Suru valley",     ["adventure","culture"],        "🏔️"),
        ],
    },
    "shimla": {
        "sub_regions":  ["Shimla Mall Road", "Kufri", "Chail"],
        "split_days":   {"Shimla Mall Road": 0.40, "Kufri": 0.35, "Chail": 0.25},
        "auto_split_max_days": 5,
        "nearby": [
            NearbyCity("Manali",    270, 6.0, "Adventure hub, snow peaks, Rohtang", ["adventure","photography"],      "🏔️"),
            NearbyCity("Dharamshala", 240, 5.5, "Tibetan culture, mountain views",  ["culture","relaxation"],         "🙏"),
            NearbyCity("Kasauli",   65,  1.5, "Quiet hill town, colonial charm",    ["relaxation"],                   "🌲"),
        ],
    },
    "andaman": {
        "sub_regions":  ["Port Blair", "Havelock Island", "Neil Island"],
        "split_days":   {"Port Blair": 0.25, "Havelock Island": 0.50, "Neil Island": 0.25},
        "auto_split_max_days": 7,
        "nearby": [],
    },
    "darjeeling": {
        "sub_regions":  ["Darjeeling Town", "Tiger Hill", "Tea Garden Circuit"],
        "split_days":   {"Darjeeling Town": 0.40, "Tiger Hill": 0.30, "Tea Garden Circuit": 0.30},
        "auto_split_max_days": 5,
        "nearby": [
            NearbyCity("Gangtok",   90,  3.0, "Sikkim capital, monasteries, views",  ["culture","adventure"],         "🏔️"),
            NearbyCity("Pelling",   130, 4.0, "Kanchenjunga views, monasteries",     ["photography","culture"],       "📸"),
        ],
    },
}


def should_auto_split(destination: str, num_days: int) -> bool:
    """Return True if destination should be auto-split into sub-regions."""
    dest = destination.lower().strip()
    config = NEARBY_DB.get(dest)
    if not config:
        return False
    max_days = config.get("auto_split_max_days", 5)
    return num_days <= max_days and len(config.get("sub_regions", [])) > 1


def get_sub_regions(destination: str) -> List[str]:
    """Return sub-region list for a destination."""
    dest = destination.lower().strip()
    config = NEARBY_DB.get(dest, {})
    return config.get("sub_regions", [])


def split_days_across_regions(destination: str, total_days: int) -> Dict[str, int]:
    """
    Split total days across sub-regions proportionally.
    E.g. Goa 5 days → {North Goa: 2, South Goa: 3}
    """
    dest   = destination.lower().strip()
    config = NEARBY_DB.get(dest, {})
    splits = config.get("split_days", {})

    if not splits:
        return {}

    result = {}
    remaining = total_days
    items     = list(splits.items())

    for i, (region, ratio) in enumerate(items):
        if i == len(items) - 1:
            result[region] = remaining
        else:
            days = max(1, round(total_days * ratio))
            result[region] = days
            remaining -= days

    return result


def get_nearby_cities(destination: str, style_id: str = "balanced") -> List[NearbyCity]:
    """Return nearby city suggestions filtered by travel style."""
    dest   = destination.lower().strip()
    config = NEARBY_DB.get(dest, {})
    nearby = config.get("nearby", [])

    if not nearby:
        return []

    # Filter by style match if possible
    style_filtered = [c for c in nearby if not c.style_match or style_id in c.style_match]
    return style_filtered[:3] if style_filtered else nearby[:3]
