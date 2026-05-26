"""
agents/agents.py — All Specialized Agents for the Trip Planner
==============================================================
Fixes in this version:
  1. user_input_agent: smarter extraction — understands multi-stop routes,
     explicit car/transport mentions, stopover cities, "from X" parsing
  2. clarification_agent: ONLY asks for fields that are truly missing after
     thorough extraction. Never asks about something the user already said.
  3. transport_agent: passes transport_preference to fetch_route_distance
     so ORS returns 'car' when user says 'by car'
  4. places_agent: limits LLM enrichment input to prevent truncation;
     falls back to raw Geoapify data if LLM returns fewer places
  5. All JSON parsing uses _parse_json_robust() with json_repair fallback
  6. itinerary_agent: compact prompt + dedicated 8000-token LLM instance
"""

import json
import logging
import re as _re
from typing import Any, Dict, List
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import OPENAI_API_KEY, LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS
from state import TripState



# LangSmith tracing
try:
    from langsmith import traceable
    LANGSMITH_AVAILABLE = True
except ImportError:
    # Graceful fallback — define a no-op decorator
    def traceable(**kwargs):
        def decorator(fn): return fn
        return decorator
    LANGSMITH_AVAILABLE = False

logger = logging.getLogger("trip_planner.agents")

# ── json_repair ───────────────────────────────────────────────────────────────
JSON_REPAIR_AVAILABLE = False
try:
    from json_repair import repair_json
    JSON_REPAIR_AVAILABLE = True
    logger.info("json_repair available ✓")
except ImportError:
    logger.warning("json_repair not installed — run: pip install json-repair")

# ── Live APIs ─────────────────────────────────────────────────────────────────
LIVE_APIS_AVAILABLE = False
try:
    from tools.live_apis import (
        fetch_weather, fetch_places, fetch_route_distance,
        fetch_hotel_prices, geocode_city,
    )
    LIVE_APIS_AVAILABLE = True
except ImportError:
    logger.warning("live_apis not found — using LLM fallback")

# ── Guardrails ────────────────────────────────────────────────────────────────
GUARDRAILS_AVAILABLE = False
try:
    from tools.guardrails import (
        retrieval_guard, output_guard, output_guard_itinerary,
        tool_guard, pii_masker, hallucination_guard
    )
    GUARDRAILS_AVAILABLE = True
except ImportError:
    logger.warning("guardrails not found — guardrails disabled")


# ═════════════════════════════════════════════════════════════════════════════
# SHARED LLM HELPERS
# ═════════════════════════════════════════════════════════════════════════════


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
        openai_api_key=OPENAI_API_KEY,
    )

@traceable(name="llm_call_standard", run_type="llm")
def _llm_call(system: str, human: str) -> str:
    llm = get_llm()
    try:
        response = llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=human),
        ])
        return response.content.strip()
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        return f"[LLM Error: {e}]"

@traceable(name="llm_call_high_tokens", run_type="llm",
           metadata={"max_tokens": 8000})
def _llm_call_high_tokens(system: str, human: str, max_tokens: int = 8000) -> str:
    """Dedicated high-token call for itinerary agent."""
    llm = ChatOpenAI(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        max_tokens=max_tokens,
        openai_api_key=OPENAI_API_KEY,
    )
    try:
        response = llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=human),
        ])
        return response.content.strip()
    except Exception as e:
        logger.error("High-token LLM call failed: %s", e)
        return f"[LLM Error: {e}]"


def _parse_json_robust(raw: str) -> dict:
    """Parse LLM JSON with smart quote fixes + json_repair fallback."""
    clean = raw.strip()
    if "```" in clean:
        parts = clean.split("```")
        clean = parts[1] if len(parts) > 1 else clean
        if clean.startswith("json"):
            clean = clean[4:]
    clean = clean.strip()
    clean = clean.replace('\u201c', '"').replace('\u201d', '"')
    clean = clean.replace('\u2018', "'").replace('\u2019', "'")
    clean = _re.sub(r',\s*([}\]])', r'\1', clean)
    try:
        return json.loads(clean)
    except json.JSONDecodeError as e:
        logger.warning("JSON parse failed at char %d — attempting repair", e.pos)
        if JSON_REPAIR_AVAILABLE:
            try:
                result = json.loads(repair_json(clean))
                logger.info("JSON repair successful ✓")
                return result
            except Exception as re_err:
                logger.error("JSON repair also failed: %s", re_err)
        raise


def _tool_allowed(tool_name: str, params: dict) -> bool:
    if not GUARDRAILS_AVAILABLE:
        return True
    result = tool_guard(tool_name, params)
    if result.blocked:
        logger.warning("[ToolGuard] Blocked '%s': %s", tool_name, result.reason)
        return False
    return True


def _apply_output_guard(text: str, prefs: dict) -> str:
    if not GUARDRAILS_AVAILABLE:
        return text
    result = output_guard(text, prefs)
    if result.blocked:
        return "{}"
    return result.clean


def _f(val, default: float = 0.0) -> float:
    try:    return float(val)
    except: return default


# ═════════════════════════════════════════════════════════════════════════════
# 1. USER INPUT AGENT
# ═════════════════════════════════════════════════════════════════════════════
@traceable(name="UserInputAgent", run_type="chain")
def user_input_agent(state: TripState) -> Dict[str, Any]:
    """
    Parse raw user query into structured preferences.
    """
    logger.info("[UserInputAgent] Parsing: %s", state.get("user_query", "")[:100])

    system = """You are a travel assistant. Extract ALL trip details from the user query.
Return ONLY a JSON object (no markdown, no explanation, no array):
{
  "source": "origin city or null",
  "destination": "final destination city/country",
  "stopovers": ["city1", "city2"],
  "start_date": "YYYY-MM-DD or description or null",
  "end_date": "YYYY-MM-DD or description or null",
  "num_days": integer or null,
  "budget": numeric or null,
  "currency": "INR or USD or EUR",
  "travelers": integer or null,
  "travel_type": "solo/couple/family/friends/business or null",
  "transport_preference": "flight/train/bus/car or null",
  "hotel_preference": "resort/hotel/hostel/villa/houseboat or null",
  "food_preference": "vegetarian/non-veg/vegan/seafood/any or null",
  "interests": ["list", "of", "interests"],
  "special_requests": "any extra notes or null"
}"""

    history_text = ""
    if state.get("conversation_history"):
        history_text = "\n\nConversation history:\n" + "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in state["conversation_history"][-6:]
        )

    raw = _llm_call(system, f"User query: {state.get('user_query', '')}{history_text}")

    # Parse with full safety guards
    prefs = {}
    try:
        parsed = _parse_json_robust(raw)
        # Guard 1: unwrap list if LLM returned [{...}] instead of {...}
        if isinstance(parsed, list):
            parsed = parsed[0] if parsed else {}
        # Guard 2: ensure it's a dict
        if isinstance(parsed, dict):
            prefs = parsed
        else:
            logger.warning("Parsed result is %s, not dict — using empty", type(parsed))
            prefs = {}
    except Exception as e:
        logger.warning("Could not parse user input JSON: %s", e)
        prefs = {}

    existing = state.get("trip_preferences", {})
    merged = {**existing}
    for k, v in prefs.items():
        if v is not None and v != "" and v != []:
            merged[k] = v

    # Normalise vague date descriptions → concrete YYYY-MM-DD
    if merged.get("start_date") and not _re.match(r"\d{4}-\d{2}-\d{2}", str(merged.get("start_date", ""))):
        from datetime import datetime as _dt, timedelta as _td
        _today = _dt.now()
        _vague = str(merged["start_date"]).lower()
        _month_map = {
            "january": "01", "february": "02", "march": "03", "april": "04",
            "may": "05", "june": "06", "july": "07", "august": "08",
            "september": "09", "october": "10", "november": "11", "december": "12"
        }
        _resolved = None
        for _month_name, _month_num in _month_map.items():
            if _month_name in _vague:
                _yr  = _today.year if int(_month_num) >= _today.month else _today.year + 1
                _day = "15" if "mid" in _vague else ("01" if "early" in _vague else "25")
                _resolved = f"{_yr}-{_month_num}-{_day}"
                break
        if not _resolved:
            if "next week"   in _vague: _resolved = (_today + _td(weeks=1)).strftime("%Y-%m-%d")
            elif "next month" in _vague:
                _nm = (_today.replace(day=1) + _td(days=32)).replace(day=1)
                _resolved = _nm.strftime("%Y-%m-%d")
            elif "tomorrow"  in _vague: _resolved = (_today + _td(days=1)).strftime("%Y-%m-%d")
        if _resolved:
            logger.info("[UserInputAgent] Normalised date '%s' → '%s'", merged["start_date"], _resolved)
            merged["start_date"] = _resolved
            if merged.get("num_days") and not merged.get("end_date"):
                _start = _dt.strptime(_resolved, "%Y-%m-%d")
                merged["end_date"] = (_start + _td(days=int(merged["num_days"]) - 1)).strftime("%Y-%m-%d")

    # Derive currency
    raw_query = state.get("user_query", "").lower()
    if not merged.get("currency"):
        if "$" in raw_query or "usd" in raw_query:      merged["currency"] = "USD"
        elif "€" in raw_query or "eur" in raw_query:    merged["currency"] = "EUR"
        else:                                            merged["currency"] = "INR"

    logger.info(
        "[UserInputAgent] Extracted: dest=%s source=%s days=%s budget=%s travelers=%s transport=%s",
        merged.get("destination"), merged.get("source"), merged.get("num_days"),
        merged.get("budget"), merged.get("travelers"), merged.get("transport_preference")
    )

    return {"trip_preferences": merged, "current_agent": "user_input_agent"}

# ═════════════════════════════════════════════════════════════════════════════
# 1b. CLARIFICATION AGENT
# ═════════════════════════════════════════════════════════════════════════════

REQUIRED_FIELDS = ["destination", "num_days", "budget", "travelers", "source"]

FIELD_QUESTIONS = {
    "destination":  "Where do you want to go? (e.g. Goa, Dubai, Bali)",
    "source":       "Where are you travelling from? (your departure city)",
    "num_days":     "How many days is your trip?",
    "budget":       "What is your total budget? (e.g. ₹30,000 or $2,000)",
    "travelers":    "How many people are travelling (including yourself)?",
}


@traceable(name="ClarificationAgent", run_type="chain") 
def clarification_agent(state: TripState) -> Dict[str, Any]:
    """
    Check ONLY for genuinely missing fields.
    Never asks about something the user already provided.
    """
    prefs   = state.get("trip_preferences", {})
    answers = state.get("clarification_answers", {})
    merged  = {**prefs, **answers}

    def _missing(field: str) -> bool:
        val = merged.get(field)
        if val is None:                  return True
        if isinstance(val, str) and val.strip().lower() in ("", "null", "none", "unknown"): return True
        if isinstance(val, (int, float)) and val == 0:  return True
        return False

    missing = [f for f in REQUIRED_FIELDS if _missing(f)]

    if missing:
        nxt      = missing[0]
        question = FIELD_QUESTIONS.get(nxt, f"Could you tell me your {nxt}?")
        logger.info("[ClarificationAgent] Still missing: %s — asking about %s", missing, nxt)
        return {
            "flow_stage":             "clarifying",
            "missing_fields":         missing,
            "clarification_question": question,
            "trip_preferences":       merged,
            "current_agent":          "clarification_agent",
        }

    logger.info("[ClarificationAgent] All required fields present — ready to plan")
    return {
        "flow_stage":             "ready",
        "missing_fields":         [],
        "clarification_question": "",
        "trip_preferences":       merged,
        "current_agent":          "clarification_agent",
    }


def absorb_clarification_answer(state: TripState, field: str, answer: str) -> Dict[str, Any]:
    """Parse a clarification answer into the correct type."""
    answers = dict(state.get("clarification_answers", {}))
    prefs   = dict(state.get("trip_preferences", {}))

    if field == "num_days":
        try:    answers[field] = int("".join(filter(str.isdigit, answer))) or 5
        except: answers[field] = 5
    elif field == "budget":
        nums = _re.findall(r"[\d,]+", answer.replace(",", ""))
        answers[field] = int(nums[0]) if nums else 0
        if any(c in answer for c in ["$", "USD", "usd"]):   prefs["currency"] = "USD"
        elif any(c in answer for c in ["€", "EUR", "eur"]): prefs["currency"] = "EUR"
        else: prefs.setdefault("currency", "INR")
    elif field == "travelers":
        try:    answers[field] = int("".join(filter(str.isdigit, answer))) or 1
        except: answers[field] = 1
    elif field == "interests":
        answers[field] = [w.strip() for w in answer.replace(",", " ").split() if len(w) > 2]
    else:
        answers[field] = answer.strip()

    prefs.update(answers)
    return {
        "clarification_answers": answers,
        "trip_preferences":      prefs,
        "user_query":            f"Updated: {field}={answer}",
    }


# ═════════════════════════════════════════════════════════════════════════════
# 2. MEMORY AGENT  (+ Retrieval Guardrail)
# ═════════════════════════════════════════════════════════════════════════════
@traceable(name="MemoryAgent", run_type="retriever")
def memory_agent(state: TripState) -> Dict[str, Any]:
    """FAISS retrieval with retrieval guardrail filtering."""
    logger.info("[MemoryAgent] Retrieving knowledge…")

    prefs       = state.get("trip_preferences", {})
    destination = prefs.get("destination", state.get("user_query", ""))
    query       = f"{destination} travel hotels transport attractions"

    from data.knowledge_base import similarity_search

    try:
        raw_docs  = similarity_search(query, k=8)
        doc_dicts = [{"content": d.page_content, "metadata": d.metadata} for d in raw_docs]

        if GUARDRAILS_AVAILABLE:
            doc_dicts = retrieval_guard(doc_dicts, destination=destination)
            logger.info("[MemoryAgent] Retrieval guardrail: %d docs passed", len(doc_dicts))

        retrieved = [
            {"content": d["content"], "metadata": d["metadata"], "relevance_score": None}
            for d in doc_dicts
        ]
        logger.info("[MemoryAgent] Retrieved %d documents", len(retrieved))

    except Exception as e:
        logger.error("[MemoryAgent] Retrieval failed: %s", e)
        retrieved = []

    categorised: Dict[str, List[str]] = {}
    for doc in retrieved:
        cat = doc["metadata"].get("category", "general")
        categorised.setdefault(cat, []).append(doc["content"])

    return {
        "retrieved_docs": retrieved,
        "memory_context": {
            "categorised": categorised,
            "destination": destination,
            "doc_count":   len(retrieved),
        },
        "current_agent": "memory_agent",
    }


# ═════════════════════════════════════════════════════════════════════════════
# 3. WEATHER AGENT  (+ Tool Guardrail)
# ═════════════════════════════════════════════════════════════════════════════

@traceable(name="WeatherAgent", run_type="chain",
           metadata={"uses_live_api": True})
def weather_agent(state: TripState) -> Dict[str, Any]:
    """Live weather via Open-Meteo → OWM → LLM fallback."""
    logger.info("[WeatherAgent] Fetching weather…")

    prefs       = state.get("trip_preferences", {})
    destination = prefs.get("destination", "")
    start_date  = prefs.get("start_date", "")
    num_days    = prefs.get("num_days", 7)
    dates       = f"{prefs.get('start_date','upcoming')} to {prefs.get('end_date','')}"

    if LIVE_APIS_AVAILABLE:
        params = {"destination": destination, "num_days": num_days}
        if _tool_allowed("fetch_weather", params):
            live = fetch_weather(destination, start_date or None, num_days)
            if live:
                logger.info("[WeatherAgent] ✅ Live weather from %s", live.get("source"))
                return {"weather_data": live, "current_agent": "weather_agent"}

    # LLM fallback
    memory       = state.get("memory_context", {})
    weather_docs = memory.get("categorised", {}).get("weather", [])
    context      = "\n".join(weather_docs[:2]) if weather_docs else ""

    system = """You are a travel weather expert. Return ONLY JSON:
{"source":"LLM estimate","destination":"...","travel_period":"...","avg_temp_day":"...","avg_temp_night":"...","conditions":"sunny/rainy/cold/snowy","rainfall":"low/moderate/high","clothing_advice":"...","weather_warnings":[],"beach_suitable":false,"outdoor_suitable":true,"weather_summary":"2-3 sentences"}"""

    raw = _llm_call(system, f"Destination:{destination} Dates:{dates}")
    try:
        weather = _parse_json_robust(raw)
    except Exception:
        weather = {
            "destination": destination, "travel_period": dates,
            "weather_summary": raw[:300], "outdoor_suitable": True,
            "beach_suitable": False, "source": "LLM estimate",
            "conditions": "unknown", "clothing_advice": "Pack for all weather.",
        }

    return {"weather_data": weather, "current_agent": "weather_agent"}


# ═════════════════════════════════════════════════════════════════════════════
# 4. TRANSPORT AGENT  (+ Tool Guardrail, respects transport_preference)
# ═════════════════════════════════════════════════════════════════════════════

@traceable(name="TransportAgent", run_type="chain")
def transport_agent(state: TripState) -> Dict[str, Any]:
    """
    Live route via ORS → LLM enrichment.
    Passes transport_preference to ORS so 'car' trips get car recommendation.
    """
    logger.info("[TransportAgent] Finding transport…")

    prefs            = state.get("trip_preferences", {})
    memory           = state.get("memory_context", {})
    source           = prefs.get("source", "")
    destination      = prefs.get("destination", "")
    transport_pref   = (prefs.get("transport_preference") or "").lower()
    num_travelers    = prefs.get("travelers", 2)
    budget           = _f(prefs.get("budget", 0))
    currency         = prefs.get("currency", "INR")
    num_days         = prefs.get("num_days", 5)
    stopovers        = prefs.get("stopovers", [])
    transport_budget = budget * 0.25

    # Try ORS with transport preference
    route_data = None
    if LIVE_APIS_AVAILABLE and source and destination:
        params = {"origin": source, "destination": destination}
        if _tool_allowed("fetch_route_distance", params):
            route_data = fetch_route_distance(source, destination, transport_pref)
            if route_data:
                logger.info("[TransportAgent] ✅ Live route: %s", route_data.get("notes",""))

    context_parts = memory.get("categorised", {}).get("transport", [])
    context       = "\n".join(context_parts[:2]) if context_parts else ""

    route_context = ""
    if route_data:
        route_context = (
            f"\nLIVE ROUTE (ORS): {route_data['distance_km']}km, "
            f"{route_data['road_duration_h']}h drive, "
            f"recommended:{route_data['recommended_mode']}, "
            f"est:{currency}{route_data['estimated_cost_inr']}"
        )

    stopover_note = f" Stopovers:{stopovers}" if stopovers else ""

    # IMPORTANT: explicitly enforce user preference in prompt
    pref_instruction = ""
    if transport_pref:
        pref_instruction = (
            f"\nCRITICAL: User has specified transport mode = '{transport_pref}'. "
            f"The primary_option mode MUST be '{transport_pref}'. Do NOT change this."
        )

    system = (
        f"You are a travel transport expert. "
        f"Budget:{currency}{transport_budget:.0f} total. "
        f"{pref_instruction}"
        f"Return ONLY valid JSON: "
        f'{{"primary_option":{{"mode":"{transport_pref or "flight/train/bus/car"}",'
        f'"operator":"name","duration":"Xh","price_per_person":0,"total_price":0,'
        f'"schedule":"times","booking_platform":"platform","fits_budget":true,"budget_note":"note"}},'
        f'"alternative_options":[{{"mode":"","price_per_person":0,"duration":"","notes":""}}],'
        f'"local_transport":{{"recommended":"auto","daily_cost":0,"total_local_cost":0,"tips":"tip"}},'
        f'"total_transport_budget":0,"transport_summary":"summary"}}'
    )

    human = (
        f"From:{source} To:{destination}{stopover_note} "
        f"Travelers:{num_travelers} Days:{num_days} "
        f"Preference:{transport_pref or 'any'}"
        f"{route_context}"
    )
    raw = _llm_call(system, human)

    try:
        transport = _parse_json_robust(raw)
        transport["source"] = "OpenRouteService + LLM" if route_data else "LLM estimate"
        if route_data:
            transport["live_route"] = route_data
        # Enforce preference if LLM ignored it
        if transport_pref and transport.get("primary_option", {}).get("mode", "") != transport_pref:
            logger.warning("[TransportAgent] LLM ignored transport_pref=%s — correcting", transport_pref)
            if "primary_option" in transport:
                transport["primary_option"]["mode"] = transport_pref
    except Exception:
        transport = {
            "transport_summary":      raw[:400],
            "total_transport_budget": transport_budget,
            "source":                 "LLM estimate",
            "primary_option":         {"mode": transport_pref or "flight"},
        }
        if route_data:
            transport["live_route"] = route_data

    return {"transport_data": transport, "current_agent": "transport_agent"}


# ═════════════════════════════════════════════════════════════════════════════
# 5. HOTEL AGENT  (+ Tool Guardrail)
# ═════════════════════════════════════════════════════════════════════════════

@traceable(name="HotelAgent", run_type="chain")
def hotel_agent(state: TripState) -> Dict[str, Any]:
    """Live prices from Xotelo → 3-tier LLM recommendation within 40% budget."""
    logger.info("[HotelAgent] Finding accommodation…")

    prefs              = state.get("trip_preferences", {})
    memory             = state.get("memory_context", {})
    destination        = prefs.get("destination", "")
    hotel_pref         = prefs.get("hotel_preference", "hotel")
    num_days           = prefs.get("num_days", 5)
    total_budget       = _f(prefs.get("budget", 0))
    currency           = prefs.get("currency", "INR")
    num_travelers      = prefs.get("travelers", 2)
    start_date         = prefs.get("start_date", "")
    end_date           = prefs.get("end_date", "")
    hotel_budget_total = total_budget * 0.40
    max_per_night      = hotel_budget_total / max(num_days, 1)

    live_hotels_context = ""
    if LIVE_APIS_AVAILABLE and start_date and end_date:
        params = {"destination": destination, "limit": 8}
        if _tool_allowed("fetch_hotel_prices", params):
            try:
                live_hotels = fetch_hotel_prices(destination, start_date, end_date, limit=8)
                if live_hotels:
                    rate = 83.0 if currency == "INR" else 1.0
                    live_hotels_context = "\nLIVE HOTEL PRICES (Xotelo):\n"
                    for h in live_hotels[:5]:
                        price_local = h["best_price"] * rate
                        live_hotels_context += f"  - {h['name']}: {currency}{price_local:.0f}/night\n"
                    logger.info("[HotelAgent] ✅ Live prices from Xotelo")
            except Exception as e:
                logger.warning("[HotelAgent] Xotelo failed: %s", e)

    hotel_docs = memory.get("categorised", {}).get("hotels", [])
    context    = "\n".join(hotel_docs[:2]) if hotel_docs else ""

    system = (
        f"You are a hotel expert. Max per night={currency}{max_per_night:.0f}. "
        f"ALL 3 options price_per_night<={max_per_night:.0f}. "
        f"Use real names from live data if provided. Return ONLY valid JSON: "
        f'{{"hotel_options":['
        f'{{"tier":"Budget Pick","name":"...","category":"2★","location":"area",'
        f'"price_per_night":0,"total_cost":0,"amenities":["wifi"],"rating":3.5,'
        f'"booking_platform":"Booking.com","why_pick":"..."}},'
        f'{{"tier":"Best Value",...same fields...}},'
        f'{{"tier":"Comfort Choice",...same fields...}}'
        f'],"recommended_index":1,"total_accommodation_cost":0,'
        f'"hotel_tips":"...","within_budget":true}}'
    )

    human = (
        f"Destination:{destination} Type:{hotel_pref} "
        f"Nights:{num_days} Travelers:{num_travelers} "
        f"Budget cap:{currency}{max_per_night:.0f}/night"
        f"{live_hotels_context}"
    )
    raw = _llm_call(system, human)

    try:
        hotel = _parse_json_robust(raw)
        opts  = hotel.get("hotel_options", [])
        idx   = min(hotel.get("recommended_index", 1), max(len(opts) - 1, 0))
        if opts:
            hotel["recommended_hotel"] = opts[idx]
            hotel["alternatives"]      = [o for i, o in enumerate(opts) if i != idx]
        hotel["source"] = "Xotelo + LLM" if live_hotels_context else "LLM estimate"
    except Exception as e:
        logger.warning("Hotel JSON parse failed: %s", e)
        hotel = {
            "hotel_tips":               raw[:400],
            "within_budget":            True,
            "total_accommodation_cost": hotel_budget_total,
            "hotel_options":            [],
            "source":                   "LLM estimate",
        }

    return {"hotel_data": hotel, "current_agent": "hotel_agent"}


# ═════════════════════════════════════════════════════════════════════════════
# 6. PLACES AGENT  (+ Tool Guardrail, better fallback handling)
# ═════════════════════════════════════════════════════════════════════════════

@traceable(name="PlacesAgent", run_type="chain")
def places_agent(state: TripState) -> Dict[str, Any]:
    """
    Live places from Geoapify → LLM enrichment.
    If LLM returns fewer places than Geoapify gave, falls back to raw Geoapify data.
    """
    logger.info("[PlacesAgent] Discovering places…")

    prefs       = state.get("trip_preferences", {})
    weather     = state.get("weather_data", {})
    destination = prefs.get("destination", "")
    interests   = prefs.get("interests", [])
    food_pref   = prefs.get("food_preference", "any")
    travel_type = prefs.get("travel_type", "couple")
    outdoor_ok  = weather.get("outdoor_suitable", True)
    beach_ok    = weather.get("beach_suitable", True)

    live_places = None

    if LIVE_APIS_AVAILABLE:
        params = {"destination": destination, "radius_m": 20000, "limit": 25}
        if _tool_allowed("fetch_places", params):
            live_places = fetch_places(destination, interests, radius_m=20000, limit=25)
            if live_places:
                logger.info("[PlacesAgent] ✅ Geoapify: %s", live_places.get("places_summary",""))

    # Build LLM enrichment context — CAPPED to prevent token truncation
    live_context = ""
    if live_places:
        att_names  = [a["name"] for a in live_places.get("top_attractions", [])[:5]]
        rest_names = [r["name"] for r in live_places.get("restaurants", [])[:4]]
        act_names  = [a["name"] for a in live_places.get("activities", [])[:3]]
        live_context = (
            f"Real places from Geoapify:\n"
            f"Attractions:{att_names}\nRestaurants:{rest_names}\nActivities:{act_names}"
        )

    memory      = state.get("memory_context", {})
    cats        = memory.get("categorised", {})
    llm_context = " ".join(cats.get("destination_overview", [])[:1])[:200]

    system = """You are a destination expert. Enrich the real place names with costs, tips, durations.
Return ONLY valid JSON (no markdown):
{"top_attractions":[{"name":"exact name","type":"heritage/beach/adventure","duration":"2h","entry_fee":null,"best_time":"morning","rating":4.2,"location":"area"}],"restaurants":[{"name":"exact name","cuisine":"local","avg_cost_per_person":0,"must_try_dish":"dish","location":"area","rating":4.0}],"activities":[{"name":"activity","type":"adventure","cost_per_person":0,"duration":"2h","suitable_for":"couple"}],"hidden_gems":["tip"],"places_summary":"overview"}"""

    human = (
        f"Destination:{destination} Type:{travel_type} "
        f"Interests:{interests[:3]} Food:{food_pref} "
        f"Outdoor:{outdoor_ok} Beach:{beach_ok}\n"
        f"{live_context or llm_context}"
    )
    raw = _llm_call(system, human)

    try:
        enriched = _parse_json_robust(raw)

        # If LLM returned fewer attractions than Geoapify gave — use Geoapify's raw list
        if live_places:
            geoapify_att_count = len(live_places.get("top_attractions", []))
            enriched_att_count = len(enriched.get("top_attractions", []))
            if enriched_att_count < min(geoapify_att_count, 3):
                logger.info(
                    "[PlacesAgent] LLM returned %d attractions vs Geoapify's %d — using Geoapify list",
                    enriched_att_count, geoapify_att_count
                )
                enriched["top_attractions"] = live_places["top_attractions"]

            geoapify_rest_count = len(live_places.get("restaurants", []))
            enriched_rest_count = len(enriched.get("restaurants", []))
            if enriched_rest_count == 0 and geoapify_rest_count > 0:
                enriched["restaurants"] = live_places["restaurants"]

        enriched["source"] = "Geoapify + LLM" if live_places else "LLM estimate"

    except Exception:
        enriched = live_places or {
            "places_summary":  raw[:400],
            "top_attractions": [],
            "restaurants":     [],
            "activities":      [],
            "source":          "LLM estimate",
        }

    return {"places_data": enriched, "current_agent": "places_agent"}


# ═════════════════════════════════════════════════════════════════════════════
# 7. BUDGET AGENT
# ═════════════════════════════════════════════════════════════════════════════

@traceable(name="BudgetAgent", run_type="chain")
def budget_agent(state: TripState) -> Dict[str, Any]:
    """Estimate costs from upstream agent data, produce breakdown."""
    logger.info("[BudgetAgent] Calculating budget…")

    prefs         = state.get("trip_preferences", {})
    transport     = state.get("transport_data", {})
    hotel         = state.get("hotel_data", {})
    places        = state.get("places_data", {})
    total_budget  = _f(prefs.get("budget", 0))
    currency      = prefs.get("currency", "INR")
    num_travelers = prefs.get("travelers", 2)
    num_days      = prefs.get("num_days", 5)

    transport_cost = _f(transport.get("total_transport_budget", 0))
    if transport_cost == 0:
        prim           = transport.get("primary_option", {})
        transport_cost = _f(prim.get("total_price", 0)) + _f(
            transport.get("local_transport", {}).get("total_local_cost", 0)
        )

    hotel_cost = _f(hotel.get("total_accommodation_cost", 0))
    if hotel_cost == 0:
        rec        = hotel.get("recommended_hotel", {})
        hotel_cost = _f(rec.get("total_cost", 0) or _f(rec.get("price_per_night", 0)) * num_days)

    activity_cost = sum(
        _f(a.get("cost_per_person", 0)) * num_travelers
        for a in places.get("activities", [])[:4]
    )
    for att in places.get("top_attractions", [])[:5]:
        if att.get("entry_fee"):
            activity_cost += _f(att["entry_fee"]) * num_travelers

    daily_food    = max(300, min(1200, total_budget * 0.008)) if currency == "INR" else max(15, min(80, total_budget * 0.008))
    food_cost     = daily_food * num_days * num_travelers
    misc_cost     = total_budget * 0.06
    estimated     = transport_cost + hotel_cost + activity_cost + food_cost + misc_cost
    surplus       = total_budget - estimated

    system = """Return ONLY valid JSON budget report:
{"breakdown":{"transport":0,"accommodation":0,"food":0,"activities":0,"miscellaneous":0,"estimated_total":0},"budget_provided":0,"surplus_or_deficit":0,"within_budget":true,"budget_status":"on_track","optimization_tips":["tip1","tip2"],"daily_budget":0,"budget_summary":"summary"}"""

    human = (
        f"Budget:{currency}{total_budget} Transport:{currency}{transport_cost:.0f} "
        f"Hotel:{currency}{hotel_cost:.0f} Food:{currency}{food_cost:.0f} "
        f"Activities:{currency}{activity_cost:.0f} Misc:{currency}{misc_cost:.0f} "
        f"Total:{currency}{estimated:.0f} Surplus:{currency}{surplus:.0f}"
    )
    raw = _llm_call(system, human)

    try:
        budget_result = _parse_json_robust(raw)
    except Exception:
        budget_result = {
            "budget_summary":  raw[:300],
            "within_budget":   surplus >= 0,
            "budget_status":   "on_track" if surplus >= 0 else "over_budget",
            "breakdown": {
                "transport":       transport_cost, "accommodation": hotel_cost,
                "food":            food_cost,      "activities":    activity_cost,
                "miscellaneous":   misc_cost,      "estimated_total": estimated,
            },
            "surplus_or_deficit": surplus,
            "budget_provided":    total_budget,
        }

    return {"budget_summary": budget_result, "current_agent": "budget_agent"}


# ═════════════════════════════════════════════════════════════════════════════
# 8. ITINERARY AGENT  (compact prompt + 8000-token LLM + output guard)
# ═════════════════════════════════════════════════════════════════════════════

@traceable(name="ItineraryAgent", run_type="chain",
           metadata={"max_tokens": 8000, "critical": True})
def itinerary_agent(state: TripState) -> Dict[str, Any]:
    """
    Build complete day-wise itinerary.
    Uses dedicated high-token LLM + compact prompt to prevent JSON truncation.
    Supports multi-stop routes via stopovers field.
    """
    logger.info("[ItineraryAgent] Building itinerary…")

    prefs     = state.get("trip_preferences", {})
    weather   = state.get("weather_data", {})
    transport = state.get("transport_data", {})
    hotel     = state.get("hotel_data", {})
    places    = state.get("places_data", {})
    budget    = state.get("budget_summary", {})

    num_days    = prefs.get("num_days", 5)
    destination = prefs.get("destination", "")
    source      = prefs.get("source", "")
    travel_type = prefs.get("travel_type", "couple")
    currency    = prefs.get("currency", "INR")
    stopovers   = prefs.get("stopovers", [])

    selected_hotels = prefs.get("selected_hotels", {})
    if selected_hotels:
        hotel_name = " | ".join(f"{loc}:{name}" for loc, name in selected_hotels.items())
    else:
        hotel_name = hotel.get("recommended_hotel", {}).get("name", "hotel")

    transport_mode = transport.get("primary_option", {}).get("mode", "car")
    daily_budget   = budget.get("daily_budget", 0)
    conditions     = weather.get("conditions", "pleasant")

    # Minimal attraction list to save tokens
    attractions = [a.get("name","") for a in places.get("top_attractions", [])[:3]]
    restaurants = [r.get("name","") for r in places.get("restaurants", [])[:2]]

    hotel_note = ""
    if selected_hotels:
        hotel_note = " HOTELS:" + ",".join(f"{l}={n}" for l, n in selected_hotels.items())

    # Multi-stop route context
    route_note = ""
    if stopovers:
        all_stops = [source] + stopovers + [destination]
        route_note = f" ROUTE:{' → '.join(s for s in all_stops if s)}"

    system = (
        f"You are an expert travel planner. Create a COMPLETE {num_days}-day itinerary.\n"
        f"RULES:\n"
        f"1. Output ALL {num_days} days — do NOT stop early\n"
        f"2. Use COMPACT JSON — no pretty-printing, no extra whitespace\n"
        f"3. Hotel every day: {hotel_name}\n"
        f"4. Transport mode: {transport_mode}\n"
        f"5. Return ONLY this JSON (compact):\n"
        f'{{"trip_title":"...","days":['
        f'{{"day":1,"date_label":"Day 1","theme":"...",'
        f'"morning":{{"activity":"...","duration":"2h","location":"..."}},'
        f'"afternoon":{{"activity":"...","duration":"3h","location":"..."}},'
        f'"evening":{{"activity":"...","duration":"2h","location":"..."}},'
        f'"night":{{"activity":"...","location":"..."}},'
        f'"meals":{{"breakfast":"...","lunch":"...","dinner":"..."}},'
        f'"accommodation":"{hotel_name}",'
        f'"daily_highlights":["..."],"estimated_day_cost":0}}],'
        f'"packing_checklist":["item1","item2"],'
        f'"emergency_contacts":{{"police":"100","ambulance":"108","tourist_helpline":"1363"}},'
        f'"travel_tips":["tip1","tip2"]}}'
        f"{hotel_note}"
    )

    human = (
        f"Route:{source}→{destination}{route_note} "
        f"Days:{num_days} Type:{travel_type} "
        f"Transport:{transport_mode} Budget:{currency}{daily_budget}/day "
        f"Weather:{conditions} Attractions:{attractions} Restaurants:{restaurants}"
    )

    logger.info("[ItineraryAgent] Calling LLM (max_tokens=8000) for %d-day itinerary", num_days)
    raw = _llm_call_high_tokens(system, human, max_tokens=8000)

    try:
        itinerary  = _parse_json_robust(raw)
        days_count = len(itinerary.get("days", []))
        logger.info("[ItineraryAgent] Parsed %d days ✓", days_count)
    except Exception as parse_err:
        logger.error("[ItineraryAgent] Parse failed: %s | Raw[:400]: %s", parse_err, raw[:400])
        itinerary = {
            "trip_title":        f"{num_days}-Day Trip",
            "days":              [],
            "raw_plan":          raw[:1000],
            "packing_checklist": [],
            "emergency_contacts":{},
            "travel_tips":       [],
        }

    # ── Attach daily weather forecast to each itinerary day ─────────────────────
    weather_data   = state.get("weather_data", {})
    daily_lookup   = weather_data.get("daily_lookup", {})
    start_date_str = prefs.get("start_date", "")

    if itinerary.get("days"):
        if daily_lookup and start_date_str:
            try:
                from datetime import datetime as _dt2, timedelta as _td2
                start_dt = _dt2.strptime(start_date_str, "%Y-%m-%d")
                for i, day in enumerate(itinerary["days"]):
                    day_date = (start_dt + _td2(days=i)).strftime("%Y-%m-%d")
                    day["date"] = day_date
                    day["date_label"] = (start_dt + _td2(days=i)).strftime("%d %b")
                    if day_date in daily_lookup:
                        day["weather"] = daily_lookup[day_date]
                    else:
                        # Beyond 16-day forecast window — use trip average
                        day["weather"] = {
                            "max_temp":      weather_data.get("avg_temp_day",   "N/A"),
                            "min_temp":      weather_data.get("avg_temp_night", "N/A"),
                            "conditions":    weather_data.get("conditions",     "N/A"),
                            "precipitation": "N/A",
                            "emoji":         "🌤️",
                        }
                logger.info("[ItineraryAgent] Weather attached to %d days ✓", len(itinerary["days"]))
            except Exception as e:
                logger.warning("[ItineraryAgent] Weather date matching failed: %s", e)
        else:
            # No dates or no forecast — attach overall conditions to every day
            overall_weather = {
                "max_temp":      weather_data.get("avg_temp_day",   "N/A"),
                "min_temp":      weather_data.get("avg_temp_night", "N/A"),
                "conditions":    weather_data.get("conditions",     "N/A"),
                "precipitation": "N/A",
                "emoji":         "🌤️",
            }
            for day in itinerary["days"]:
                day.setdefault("weather", overall_weather)

    # Full output guard — deep scan all string fields for PII
    if GUARDRAILS_AVAILABLE and itinerary.get("days"):
        try:
            itinerary = output_guard_itinerary(itinerary, prefs)
            logger.info("[ItineraryAgent] Output guard scan complete ✓")
        except Exception as og_err:
            logger.warning("[ItineraryAgent] Output guard failed (non-fatal): %s", og_err)

    return {"itinerary": itinerary, "current_agent": "itinerary_agent"}


# ═════════════════════════════════════════════════════════════════════════════
# 9. FINAL REVIEW AGENT  (+ Hallucination Guard)
# ═════════════════════════════════════════════════════════════════════════════

@traceable(name="FinalReviewAgent", run_type="chain")
def final_review_agent(state: TripState) -> Dict[str, Any]:
    """Validate plan completeness and run hallucination guard."""
    logger.info("[FinalReviewAgent] Validating…")

    prefs   = state.get("trip_preferences", {})
    budget  = state.get("budget_summary", {})
    weather = state.get("weather_data", {})
    hotel   = state.get("hotel_data", {})
    itin    = state.get("itinerary", {})

    conflicts, warnings = [], []

    if not budget.get("within_budget", True):
        deficit = abs(_f(budget.get("surplus_or_deficit", 0)))
        conflicts.append(f"Budget overrun by {prefs.get('currency','INR')}{deficit:.0f}")
    if not hotel.get("within_budget", True):
        conflicts.append("Hotel exceeds budget")
    for w in weather.get("weather_warnings", []):
        if w and len(w) > 3:
            warnings.append(f"Weather: {w}")

    days_planned = len(itin.get("days", []))
    num_days     = prefs.get("num_days", 5)
    if days_planned < num_days:
        warnings.append(f"Itinerary has {days_planned} days, expected {num_days}")
    if not state.get("transport_data"):
        conflicts.append("Transport data missing")

    approved = len(conflicts) == 0

    # Hallucination guard
    hallucination_report = {}
    if GUARDRAILS_AVAILABLE:
        try:
            hallucination_report = hallucination_guard(state)
            if not hallucination_report.get("passed", True):
                for flag in hallucination_report.get("flags", []):
                    warnings.append(f"🔍 {flag}")
        except Exception as e:
            logger.warning("[FinalReviewAgent] Hallucination guard error: %s", e)

    return {
        "review_status": {
            "approved":             approved,
            "status":               "approved" if approved else "needs_revision",
            "conflicts":            conflicts,
            "warnings":             warnings,
            "hallucination_report": hallucination_report,
            "hallucination_score":  hallucination_report.get("score", 1.0),
            "review_summary": (
                "✅ All checks passed."
                if approved
                else f"⚠️ {len(conflicts)} conflict(s): {'; '.join(conflicts)}"
            ),
        },
        "current_agent": "final_review_agent",
    }


# ═════════════════════════════════════════════════════════════════════════════
# 10. MEMORY UPDATE AGENT
# ═════════════════════════════════════════════════════════════════════════════

def memory_update_agent(state: TripState) -> Dict[str, Any]:
    """Save current trip preferences to user profile."""
    logger.info("[MemoryUpdateAgent] Saving to memory…")

    prefs   = state.get("trip_preferences", {})
    profile = state.get("user_profile", {})

    past_trips = profile.get("past_trips", [])
    dest       = prefs.get("destination", "")
    if dest and dest not in past_trips:
        past_trips.append(dest)

    updated_profile = {
        **profile,
        "past_trips":   past_trips,
        "last_trip":    prefs,
        "preferences": {
            "food":          prefs.get("food_preference"),
            "accommodation": prefs.get("hotel_preference"),
            "transport":     prefs.get("transport_preference"),
        },
        "last_updated": datetime.now().isoformat(),
    }

    return {"user_profile": updated_profile, "current_agent": "memory_update_agent"}


# ═════════════════════════════════════════════════════════════════════════════
# 11. HOTEL OPTIONS PER LOCATION AGENT
# ═════════════════════════════════════════════════════════════════════════════

@traceable(name="HotelOptionsAgent", run_type="chain")
def hotel_options_per_location_agent(state: TripState) -> Dict[str, Any]:
    """Generate 3 hotel options per unique location in the itinerary."""
    logger.info("[HotelLocationAgent] Generating hotel options per location…")

    prefs    = state.get("trip_preferences", {})
    itin     = state.get("itinerary", {})
    days     = itin.get("days", [])
    currency = prefs.get("currency", "INR")
    total    = _f(prefs.get("budget", 0))
    num_days = prefs.get("num_days", max(len(days), 1))
    travelers= prefs.get("travelers", 2)

    hotel_budget  = total * 0.40
    max_per_night = hotel_budget / max(num_days, 1)

    locations_seen = []
    for day in days:
        loc = (
            day.get("accommodation") or
            day.get("morning", {}).get("location", "") or
            prefs.get("destination", "")
        )
        loc = loc.split(",")[0].strip() if loc else prefs.get("destination", "")
        if loc and loc not in locations_seen:
            locations_seen.append(loc)

    if not locations_seen:
        locations_seen = [prefs.get("destination", "Destination")]

    options_by_loc: Dict[str, List[Dict]] = {}

    for loc in locations_seen:
        system = (
            f"Hotel expert for {loc}. Max {currency}{max_per_night:.0f}/night. "
            f"3 DIFFERENT real hotels. Return ONLY compact JSON: "
            f'{{"options":['
            f'{{"tier":"Budget","name":"real name","stars":"3★","location":"area",'
            f'"price_per_night":0,"total_for_stay":0,"amenities":["wifi","ac"],'
            f'"rating":3.5,"book_on":"Booking.com","highlight":"reason"}},'
            f'{{"tier":"Mid-range",...}},'
            f'{{"tier":"Premium",...}}'
            f']}}'
        )
        human  = f"Location:{loc} Nights:{num_days} Travelers:{travelers} Max:{currency}{max_per_night:.0f}/night"
        raw    = _llm_call(system, human)

        try:
            data = _parse_json_robust(raw)
            options_by_loc[loc] = data.get("options", [])
        except Exception as e:
            logger.warning("Hotel options parse failed for %s: %s", loc, e)
            options_by_loc[loc] = [
                {"tier":"Budget",    "name":f"Budget Hotel {loc}",  "stars":"3★","location":loc,"price_per_night":max_per_night*0.5,  "amenities":["wifi"],"rating":3.5,"book_on":"Booking.com","highlight":"Affordable"},
                {"tier":"Mid-range", "name":f"Comfort Inn {loc}",   "stars":"3★","location":loc,"price_per_night":max_per_night*0.75, "amenities":["wifi","breakfast"],"rating":4.0,"book_on":"MakeMyTrip","highlight":"Good value"},
                {"tier":"Premium",   "name":f"Grand Hotel {loc}",   "stars":"4★","location":loc,"price_per_night":max_per_night,      "amenities":["wifi","pool","breakfast"],"rating":4.5,"book_on":"Booking.com","highlight":"Best comfort"},
            ]

    return {
        "hotel_options_by_location": options_by_loc,
        "itinerary_locations":       locations_seen,
        "hotel_selection_step":      0,
        "hotel_selections":          {},
        "flow_stage":                "selecting_hotels",
        "current_agent":             "hotel_options_per_location_agent",
    }
