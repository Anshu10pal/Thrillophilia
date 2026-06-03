"""
backend/services/style_service.py — Travel Style Configuration
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger("thrillophilia.styles")

STYLE_CONFIGS: Dict[str, Dict] = {
    "adventure": {
        "id":    "adventure",
        "label": "Adventure",
        "emoji": "🏔️",
        "color": "#E85D04",
        "description": "Trekking, sports, adrenaline rushes",
        "geoapify_categories": "sport,natural,tourism.attraction",
        "hotel_preference":    "hostel,camp,guesthouse",
        "itinerary_tone":      "action-packed, early mornings, physical challenges, outdoor experiences",
        "interests":           ["trekking","rafting","camping","rock climbing","bouldering","paragliding","zip-line"],
        "budget_split": {"transport":0.20,"accommodation":0.25,"activities":0.40,"food":0.10,"miscellaneous":0.05},
    },
    "relaxation": {
        "id":    "relaxation",
        "label": "Relaxation",
        "emoji": "🧘",
        "color": "#4ECDC4",
        "description": "Spas, beaches, slow travel",
        "geoapify_categories": "leisure,natural.beach,tourism.attraction,catering.restaurant",
        "hotel_preference":    "resort,spa,villa",
        "itinerary_tone":      "slow-paced, late starts, spa days, sunset walks, minimal planning",
        "interests":           ["spa","beach","yoga","sunset","poolside","meditation","wellness"],
        "budget_split": {"transport":0.15,"accommodation":0.50,"activities":0.15,"food":0.15,"miscellaneous":0.05},
    },
    "romance": {
        "id":    "romance",
        "label": "Romance",
        "emoji": "💑",
        "color": "#E63946",
        "description": "Honeymoon, couples, intimate experiences",
        "geoapify_categories": "tourism.attraction,natural.beach,catering.restaurant,leisure",
        "hotel_preference":    "resort,villa,boutique hotel",
        "itinerary_tone":      "intimate, candlelit dinners, private experiences, couple activities, sunset cruises",
        "interests":           ["beach","fine dining","sunset cruise","couples spa","rooftop","private dining"],
        "budget_split": {"transport":0.15,"accommodation":0.45,"activities":0.20,"food":0.15,"miscellaneous":0.05},
    },
    "culture": {
        "id":    "culture",
        "label": "Culture",
        "emoji": "🏛️",
        "color": "#C9A84C",
        "description": "Heritage, museums, local life",
        "geoapify_categories": "heritage,tourism.attraction,education.museum,entertainment.culture,religion",
        "hotel_preference":    "boutique hotel,heritage hotel,guesthouse",
        "itinerary_tone":      "immersive, heritage walks, museum visits, local markets, historical sites",
        "interests":           ["heritage","museum","temple","local market","history","architecture","art"],
        "budget_split": {"transport":0.20,"accommodation":0.30,"activities":0.30,"food":0.15,"miscellaneous":0.05},
    },
    "food": {
        "id":    "food",
        "label": "Food & Drink",
        "emoji": "🍜",
        "color": "#F4A261",
        "description": "Street food, fine dining, culinary tours",
        "geoapify_categories": "catering.restaurant,catering.cafe,catering.bar,catering.fast_food",
        "hotel_preference":    "hotel,boutique hotel",
        "itinerary_tone":      "food-focused, multiple restaurant visits, street food tours, cooking classes",
        "interests":           ["street food","fine dining","local cuisine","food market","cooking class","cafe"],
        "budget_split": {"transport":0.15,"accommodation":0.25,"activities":0.15,"food":0.40,"miscellaneous":0.05},
    },
    "family": {
        "id":    "family",
        "label": "Family",
        "emoji": "👨‍👩‍👧",
        "color": "#2E7D52",
        "description": "Kid-friendly, safe, educational fun",
        "geoapify_categories": "entertainment,tourism.attraction,leisure.park,natural",
        "hotel_preference":    "resort,hotel,family suite",
        "itinerary_tone":      "family-friendly, educational, safe activities, early evenings, kid-approved restaurants",
        "interests":           ["theme park","beach","nature walk","educational","zoo","aquarium","family activities"],
        "budget_split": {"transport":0.20,"accommodation":0.35,"activities":0.25,"food":0.15,"miscellaneous":0.05},
    },
    "nightlife": {
        "id":    "nightlife",
        "label": "Nightlife",
        "emoji": "🎉",
        "color": "#7B2FBE",
        "description": "Clubs, bars, live music, late nights",
        "geoapify_categories": "entertainment.nightclub,catering.bar,entertainment,tourism.attraction",
        "hotel_preference":    "hotel,boutique hotel,hostel",
        "itinerary_tone":      "late starts, evening-focused, bar crawls, rooftop parties, live music venues",
        "interests":           ["club","bar","rooftop","live music","pub crawl","night market","cocktails"],
        "budget_split": {"transport":0.15,"accommodation":0.25,"activities":0.30,"food":0.25,"miscellaneous":0.05},
    },
    "photography": {
        "id":    "photography",
        "label": "Photography",
        "emoji": "📸",
        "color": "#1A4A8A",
        "description": "Golden hour, landscapes, street photography",
        "geoapify_categories": "natural,tourism.sights,heritage,natural.beach,tourism.attraction",
        "hotel_preference":    "hotel,guesthouse",
        "itinerary_tone":      "early mornings for golden hour, landscape hunts, street photography, scenic viewpoints",
        "interests":           ["viewpoint","sunrise","sunset","landscape","street photography","architecture","nature"],
        "budget_split": {"transport":0.25,"accommodation":0.30,"activities":0.20,"food":0.15,"miscellaneous":0.10},
    },
    "balanced": {
        "id":    "balanced",
        "label": "Balanced",
        "emoji": "⚖️",
        "color": "#888888",
        "description": "A mix of everything",
        "geoapify_categories": "tourism.attraction,catering.restaurant,natural,entertainment",
        "hotel_preference":    "hotel",
        "itinerary_tone":      "well-rounded mix of sightseeing, food, relaxation and local experiences",
        "interests":           ["sightseeing","local food","beach","culture","nature"],
        "budget_split": {"transport":0.20,"accommodation":0.35,"activities":0.25,"food":0.15,"miscellaneous":0.05},
    },
    "other": {
        "id":    "other",
        "label": "Other",
        "emoji": "✨",
        "color": "#C9A84C",
        "description": "Tell us your style",
        "geoapify_categories": "tourism.attraction,catering.restaurant,entertainment",
        "hotel_preference":    "hotel",
        "itinerary_tone":      "personalised experience",
        "interests":           [],
        "budget_split": {"transport":0.20,"accommodation":0.35,"activities":0.25,"food":0.15,"miscellaneous":0.05},
    },
}


def get_style_config(style_id: str) -> Dict:
    return STYLE_CONFIGS.get(style_id, STYLE_CONFIGS["balanced"])


def get_all_styles():
    return [
        {
            "id":          s["id"],
            "label":       s["label"],
            "emoji":       s["emoji"],
            "description": s["description"],
            "color":       s["color"],
        }
        for s in STYLE_CONFIGS.values()
    ]


async def interpret_custom_style(custom_text: str) -> Dict:
    """
    Use LLM to interpret a custom travel style string
    and map it to interests, hotel preference, and tone.
    """
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from agents.agents import _llm_call

        system = """You are a travel style expert. Given a custom travel style description,
extract key details. Return ONLY valid JSON:
{
  "label": "short label (2-3 words)",
  "emoji": "single emoji",
  "interests": ["keyword1", "keyword2", "keyword3"],
  "hotel_preference": "resort/hotel/hostel/villa/camp",
  "itinerary_tone": "one sentence describing the trip vibe",
  "geoapify_categories": "relevant,geoapify,categories"
}"""
        raw = _llm_call(system, f"Custom travel style: {custom_text}")

        import json, re as _re
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```")
        parsed = json.loads(clean)

        base = STYLE_CONFIGS["balanced"].copy()
        base.update(parsed)
        base["id"]          = "other"
        base["description"] = custom_text
        base["color"]       = "#C9A84C"
        base["budget_split"]= STYLE_CONFIGS["balanced"]["budget_split"]
        return base

    except Exception as e:
        logger.warning("Custom style interpretation failed: %s — using balanced", e)
        return STYLE_CONFIGS["balanced"]
