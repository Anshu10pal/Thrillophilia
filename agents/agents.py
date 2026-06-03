"""
agents/agents.py — Trip Planner Agents
=======================================
Version: Final (all bugs fixed)
Fixes applied:
  - timeout=30, max_retries=0 (fail fast during gateway overload)
  - _llm_call returns "" on failure (triggers fallbacks correctly)
  - _parse_json_robust raises on empty/error input
  - CITY_ALIASES: Banglore→Bangalore, Bombay→Mumbai etc
  - _normalise_city applied to source + destination
  - Transport fallback uses live route data for real price estimates
  - Itinerary fallback uses themed day structure with activity pool
  - Places generates stub attractions/restaurants when APIs fail
  - hotel_agent: travel_type defined before use (no NameError)
  - LLM activity bank for unique per-day activities (any destination)
  - Per-day itinerary generation (stays within 500-token gateway limit)
  - Budget calculated directly (no LLM, no tip1/tip2 placeholders)
  - Hotels: 3 separate calls per tier (Budget/Best Value/Comfort)
  - Places: deduplicated, 3 separate calls with real prices
  - end_date derived from start_date + num_days for Xotelo
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

from config import (
    OPENAI_API_KEY, OPENAI_BASE_URL,
    LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS,
)
from state import TripState

logger = logging.getLogger("trip_planner.agents")

# ── City name aliases — normalise misspellings before geocoding ───────────────
CITY_ALIASES: dict = {
    "banglore": "Bangalore", "bengaluru": "Bangalore", "bangaluru": "Bangalore",
    "bombay": "Mumbai", "calcutta": "Kolkata", "kolkatta": "Kolkata",
    "madras": "Chennai", "new delhi": "Delhi", "hydrabad": "Hyderabad",
    "mysore": "Mysuru", "pondicherry": "Puducherry", "simla": "Shimla",
    "mussorie": "Mussoorie", "mussoori": "Mussoorie", "dehra dun": "Dehradun",
    "cochin": "Kochi", "trivandrum": "Thiruvananthapuram", "ooty": "Udhagamandalam",
}


def _normalise_city(name: str) -> str:
    """Normalise city name — fix common misspellings."""
    if not name: return name
    return CITY_ALIASES.get(name.strip().lower(), name.strip().title())


# ── json_repair ───────────────────────────────────────────────────────────────
JSON_REPAIR_AVAILABLE = False
try:
    from json_repair import repair_json
    JSON_REPAIR_AVAILABLE = True
except ImportError:
    pass

# ── Live APIs ─────────────────────────────────────────────────────────────────
LIVE_APIS_AVAILABLE = False
try:
    from tools.live_apis import (
        fetch_weather, fetch_places, fetch_route_distance,
        fetch_hotel_prices, geocode_city,
    )
    LIVE_APIS_AVAILABLE = True
except ImportError:
    logger.warning("live_apis not found — LLM fallback only")

# ── Guardrails ────────────────────────────────────────────────────────────────
GUARDRAILS_AVAILABLE = False
try:
    from tools.guardrails import (
        retrieval_guard, output_guard, output_guard_itinerary,
        tool_guard, pii_masker, hallucination_guard,
    )
    GUARDRAILS_AVAILABLE = True
except ImportError:
    pass


# ═════════════════════════════════════════════════════════════════════════════
# LLM FACTORY
# ═════════════════════════════════════════════════════════════════════════════

def get_llm(max_tokens: int = None) -> ChatOpenAI:
    kwargs = dict(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        max_tokens=max_tokens or LLM_MAX_TOKENS,
        openai_api_key=OPENAI_API_KEY,
        timeout=30,
        max_retries=0,   # fail fast — no retry during gateway overload
    )
    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL
    return ChatOpenAI(**kwargs)


def _llm_call(system: str, human: str) -> str:
    try:
        llm  = get_llm()
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=human)])
        return resp.content.strip()
    except Exception as e:
        logger.error("[LLM] Call failed: %s", e)
        return ""   # empty string triggers except in every agent → fallback runs


def _llm_call_high_tokens(system: str, human: str, max_tokens: int = 500) -> str:
    try:
        llm  = get_llm(max_tokens=max_tokens)
        resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=human)])
        return resp.content.strip()
    except Exception as e:
        logger.error("[LLM] High-token call failed: %s", e)
        return ""


def _parse_json_robust(raw: str) -> dict:
    if not raw or not raw.strip() or raw.startswith("[LLM Error"):
        raise json.JSONDecodeError("Empty or error response — using fallback", raw or "", 0)
    clean = raw.strip()
    for fence in ["```json", "```"]:
        if fence in clean:
            parts = clean.split(fence)
            clean = parts[1] if len(parts) > 1 else clean
    clean = clean.strip().strip("`")
    clean = clean.replace('\u201c', '"').replace('\u201d', '"')
    clean = _re.sub(r',\s*([}\]])', r'\1', clean)
    try:
        result = json.loads(clean)
        if isinstance(result, list): result = result[0] if result else {}
        if not isinstance(result, dict): return {}
        return result
    except json.JSONDecodeError as e:
        logger.warning("JSON parse failed at char %d — attempting repair", e.pos)
    if JSON_REPAIR_AVAILABLE:
        try:
            result = json.loads(repair_json(clean))
            if isinstance(result, list): result = result[0] if result else {}
            if not isinstance(result, dict): return {}
            if result.get("days") and len(result["days"]) < 3:
                extracted_days = _extract_days_from_broken_json(clean)
                if len(extracted_days) > len(result["days"]):
                    result["days"] = extracted_days
            return result
        except Exception:
            pass
    raise json.JSONDecodeError("Could not parse", clean, 0)


def _extract_days_from_broken_json(text: str) -> list:
    days = []
    pattern = _re.compile(r'\{"day"\s*:\s*(\d+)[^}]*(?:\{[^}]*\}[^}]*)*\}', _re.DOTALL)
    for match in pattern.finditer(text):
        try:
            day_obj = json.loads(repair_json(match.group(0)))
            if isinstance(day_obj, dict) and "day" in day_obj:
                days.append(day_obj)
        except Exception:
            pass
    return sorted(days, key=lambda d: d.get("day", 0))


def _f(val, default: float = 0.0) -> float:
    try:    return float(val)
    except: return default


def _tool_allowed(tool_name: str, params: dict) -> bool:
    if not GUARDRAILS_AVAILABLE:
        return True
    try:
        result = tool_guard(tool_name, params)
        return not result.blocked
    except Exception:
        return True


# ═════════════════════════════════════════════════════════════════════════════
# 1. USER INPUT AGENT
# ═════════════════════════════════════════════════════════════════════════════

def _regex_extract(text: str) -> Dict[str, Any]:
    t   = text.lower()
    out = {}

    m = _re.search(r'(\d+)\s*(?:-?\s*day|days?|night|nights?)', t)
    if m: out["num_days"] = int(m.group(1))

    m = _re.search(r'(?:budget|₹|rs\.?|inr|usd|\$)\s*([\d,]+)', t)
    if m:
        out["budget"]   = int(m.group(1).replace(",", ""))
        out["currency"] = "INR" if any(x in t for x in ["₹","inr","rs"]) else "USD"

    m = _re.search(r'(\d+)\s+(?:people|persons?|travelers?|pax|of us)', t)
    if m: out["travelers"] = int(m.group(1))
    if "wife" in t or "husband" in t or "partner" in t or "honeymoon" in t:
        out.setdefault("travelers", 2); out["travel_type"] = "couple"
    if "family" in t: out.setdefault("travel_type", "family")
    if "solo" in t:   out.setdefault("travelers", 1); out["travel_type"] = "solo"
    if any(x in t for x in ["friends","friend","group","gang"]):
        out.setdefault("travel_type", "friends")

    for kw, mode in [("by car","car"),("my car","car"),("road trip","car"),
                     ("by train","train"),("by flight","flight"),("by bus","bus")]:
        if kw in t: out["transport_preference"] = mode; break

    m = _re.search(r'\bfrom\s+([A-Za-z\s]+?)(?:\s+to|\s+for|\s+with|\s+budget|\s+in\s+\d|$)', text, _re.I)
    if m:
        src = m.group(1).strip().title()
        if len(src) > 2 and src.lower() not in ("a","the","my","our"):
            out["source"] = src

    m = _re.search(r'stopping\s+at\s+([^,\.]+(?:,\s*[^,\.]+)*)', text, _re.I)
    if m:
        out["stopovers"] = [s.strip().title() for s in m.group(1).split(",")]

    return out


def user_input_agent(state: TripState) -> Dict[str, Any]:
    logger.info("[UserInputAgent] Parsing: %s", str(state.get("user_query",""))[:100])

    query    = state.get("user_query", "")
    existing = state.get("trip_preferences", {}) or {}

    regex_prefs = _regex_extract(query)

    system = """Extract ALL trip details from the user query.
Return ONLY valid JSON (no markdown):
{"source":"city or null","destination":"city","stopovers":[],"start_date":"YYYY-MM-DD or null","end_date":null,"num_days":null,"budget":null,"currency":"INR","travelers":null,"travel_type":"couple/solo/family/friends or null","transport_preference":"flight/train/bus/car or null","hotel_preference":null,"food_preference":null,"interests":[],"special_requests":null}"""

    history      = state.get("conversation_history", [])
    history_text = ""
    if history:
        history_text = "\n\nHistory:\n" + "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in history[-4:]
        )

    raw       = _llm_call(system, f"Query: {query}{history_text}")
    llm_prefs = {}
    if raw:
        try:
            llm_prefs = _parse_json_robust(raw)
        except Exception:
            logger.warning("[UserInputAgent] Could not parse LLM JSON — using regex only")

    merged = {**existing}
    for k, v in regex_prefs.items():
        if v is not None: merged[k] = v
    for k, v in llm_prefs.items():
        if v is not None and v != "" and v != [] and str(v).lower() not in ("null","none","unknown"):
            merged[k] = v

    # Travel type fallback — never let it be None (crashes pdf_generator)
    if not merged.get("travel_type"):
        q_lower = query.lower()
        if any(x in q_lower for x in ["wife","husband","honeymoon","partner","couple"]):
            merged["travel_type"] = "couple"
        elif any(x in q_lower for x in ["family","kids","children"]):
            merged["travel_type"] = "family"
        elif any(x in q_lower for x in ["solo","alone","myself"]):
            merged["travel_type"] = "solo"
        elif any(x in q_lower for x in ["friends","friend","group","gang"]):
            merged["travel_type"] = "friends"
        else:
            merged["travel_type"] = "general"

    if not merged.get("currency"):
        merged["currency"] = "USD" if any(x in query.lower() for x in ["$","usd"]) else "INR"

    sd = str(merged.get("start_date","")).lower()
    if sd and not _re.match(r"\d{4}-\d{2}-\d{2}", sd):
        from datetime import datetime as _dt, timedelta as _td
        today     = _dt.now()
        month_map = {"january":"01","february":"02","march":"03","april":"04","may":"05",
                     "june":"06","july":"07","august":"08","september":"09",
                     "october":"10","november":"11","december":"12"}
        resolved  = None
        for mn, mm in month_map.items():
            if mn in sd:
                yr       = today.year if int(mm) >= today.month else today.year + 1
                day      = "15" if "mid" in sd else ("01" if any(x in sd for x in ["early","start"]) else "20")
                resolved = f"{yr}-{mm}-{day}"
                break
        if not resolved:
            if "next week"   in sd: resolved = (_dt.now() + _td(weeks=1)).strftime("%Y-%m-%d")
            elif "next month" in sd:
                nm = (_dt.now().replace(day=1) + _td(days=32)).replace(day=1)
                resolved = nm.strftime("%Y-%m-%d")
        if resolved:
            merged["start_date"] = resolved
            if merged.get("num_days") and not merged.get("end_date"):
                from datetime import datetime as _dt2, timedelta as _td2
                s = _dt2.strptime(resolved, "%Y-%m-%d")
                merged["end_date"] = (s + _td2(days=int(merged["num_days"])-1)).strftime("%Y-%m-%d")

    # Normalise city names (fix misspellings)
    if merged.get("destination"):
        merged["destination"] = _normalise_city(merged["destination"])
    if merged.get("source"):
        merged["source"] = _normalise_city(merged["source"])

    # Guard: source == destination means planning_service rewrote the query
    if merged.get("source") and merged.get("destination"):
        if merged["source"].lower().strip() == merged["destination"].lower().strip():
            logger.warning("[UserInputAgent] source==destination (%s) — clearing source", merged["source"])
            merged.pop("source", None)

    logger.info(
        "[UserInputAgent] dest=%s src=%s days=%s budget=%s travelers=%s transport=%s",
        merged.get("destination"), merged.get("source"), merged.get("num_days"),
        merged.get("budget"), merged.get("travelers"), merged.get("transport_preference"),
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


def clarification_agent(state: TripState) -> Dict[str, Any]:
    prefs   = state.get("trip_preferences", {}) or {}
    answers = state.get("clarification_answers", {}) or {}
    merged  = {**prefs, **answers}

    def _missing(field: str) -> bool:
        val = merged.get(field)
        if val is None: return True
        if isinstance(val, str) and val.strip().lower() in ("","null","none","unknown"): return True
        if isinstance(val, (int,float)) and val == 0: return True
        return False

    missing = [f for f in REQUIRED_FIELDS if _missing(f)]

    if missing:
        nxt      = missing[0]
        question = FIELD_QUESTIONS.get(nxt, f"Could you tell me your {nxt}?")
        return {
            "flow_stage": "clarifying", "missing_fields": missing,
            "clarification_question": question, "trip_preferences": merged,
            "current_agent": "clarification_agent",
        }

    return {
        "flow_stage": "ready", "missing_fields": [],
        "clarification_question": "", "trip_preferences": merged,
        "current_agent": "clarification_agent",
    }


def absorb_clarification_answer(state: TripState, field: str, answer: str) -> Dict[str, Any]:
    answers = dict(state.get("clarification_answers", {}))
    prefs   = dict(state.get("trip_preferences", {}))
    if field == "num_days":
        try:    answers[field] = int("".join(filter(str.isdigit, answer))) or 5
        except: answers[field] = 5
    elif field == "budget":
        nums = _re.findall(r"[\d]+", answer.replace(",",""))
        answers[field] = int(nums[0]) if nums else 0
        if any(c in answer for c in ["$","USD","usd"]): prefs["currency"] = "USD"
        else: prefs.setdefault("currency","INR")
    elif field == "travelers":
        try:    answers[field] = int("".join(filter(str.isdigit, answer))) or 1
        except: answers[field] = 1
    else:
        answers[field] = answer.strip()
    prefs.update(answers)
    return {"clarification_answers": answers, "trip_preferences": prefs}


# ═════════════════════════════════════════════════════════════════════════════
# 2. MEMORY AGENT
# ═════════════════════════════════════════════════════════════════════════════

def memory_agent(state: TripState) -> Dict[str, Any]:
    logger.info("[MemoryAgent] Retrieving knowledge…")
    prefs       = state.get("trip_preferences", {})
    destination = prefs.get("destination", state.get("user_query",""))
    retrieved   = []
    try:
        from data.knowledge_base import similarity_search
        raw_docs  = similarity_search(f"{destination} travel hotels transport attractions", k=6)
        doc_dicts = [{"content": d.page_content, "metadata": d.metadata} for d in raw_docs]
        if GUARDRAILS_AVAILABLE:
            doc_dicts = retrieval_guard(doc_dicts, destination=destination)
        retrieved = [{"content":d["content"],"metadata":d["metadata"]} for d in doc_dicts]
    except Exception as e:
        logger.warning("[MemoryAgent] Retrieval failed (non-fatal): %s", e)

    categorised: Dict[str, List[str]] = {}
    for doc in retrieved:
        cat = doc["metadata"].get("category","general")
        categorised.setdefault(cat,[]).append(doc["content"])

    return {
        "retrieved_docs": retrieved,
        "memory_context": {"categorised": categorised, "destination": destination, "doc_count": len(retrieved)},
        "current_agent": "memory_agent",
    }


# ═════════════════════════════════════════════════════════════════════════════
# 3. WEATHER AGENT
# ═════════════════════════════════════════════════════════════════════════════

def weather_agent(state: TripState) -> Dict[str, Any]:
    logger.info("[WeatherAgent] Fetching weather…")
    prefs       = state.get("trip_preferences", {})
    destination = prefs.get("destination","")
    start_date  = prefs.get("start_date","")
    num_days    = prefs.get("num_days", 7)

    if LIVE_APIS_AVAILABLE and destination:
        try:
            if _tool_allowed("fetch_weather", {"destination": destination}):
                live = fetch_weather(destination, start_date or None, num_days)
                if live:
                    logger.info("[WeatherAgent] ✅ Live: %s", live.get("source",""))
                    return {"weather_data": live, "current_agent": "weather_agent"}
        except Exception as e:
            logger.warning("[WeatherAgent] Live API failed: %s", e)

    system = 'Travel weather expert. Return ONLY valid JSON: {"source":"LLM estimate","destination":"...","avg_temp_day":"...","avg_temp_night":"...","conditions":"sunny/rainy/cold/snowy","rainfall":"low/moderate/high","clothing_advice":"...","weather_warnings":[],"beach_suitable":false,"outdoor_suitable":true,"weather_summary":"2-3 sentence summary"}'
    raw    = _llm_call(system, f"Destination:{destination} StartDate:{start_date} Days:{num_days}")
    try:
        weather = _parse_json_robust(raw)
    except Exception:
        weather = {
            "destination": destination, "source": "LLM estimate",
            "conditions": "pleasant", "outdoor_suitable": True,
            "beach_suitable": False, "clothing_advice": "Pack for all weather.",
            "weather_summary": f"Weather for {destination} is generally pleasant.",
            "weather_warnings": [], "avg_temp_day": "28°C", "avg_temp_night": "20°C",
        }
    return {"weather_data": weather, "current_agent": "weather_agent"}


# ═════════════════════════════════════════════════════════════════════════════
# 4. TRANSPORT AGENT
# ═════════════════════════════════════════════════════════════════════════════

def transport_agent(state: TripState) -> Dict[str, Any]:
    logger.info("[TransportAgent] Finding transport…")
    prefs          = state.get("trip_preferences", {})
    source         = prefs.get("source","")
    destination    = prefs.get("destination","")
    transport_pref = (prefs.get("transport_preference") or "").lower()
    num_travelers  = int(prefs.get("travelers") or 2)
    budget         = _f(prefs.get("budget",0))
    currency       = prefs.get("currency","INR")
    num_days       = int(prefs.get("num_days") or 5)
    stopovers      = prefs.get("stopovers",[])
    transport_bgt  = budget * 0.25

    route_data = None
    if LIVE_APIS_AVAILABLE and source and destination:
        try:
            if _tool_allowed("fetch_route_distance",{"origin":source,"destination":destination}):
                route_data = fetch_route_distance(source, destination, transport_pref)
        except Exception as e:
            logger.warning("[TransportAgent] ORS failed: %s", e)

    route_context    = ""
    pref_instruction = ""
    if route_data:
        route_context = f"\nLIVE ROUTE: {route_data['distance_km']}km, {route_data['road_duration_h']}h, recommended:{route_data['recommended_mode']}"
    if transport_pref:
        pref_instruction = f"\nCRITICAL: User specified mode='{transport_pref}'. primary_option.mode MUST be '{transport_pref}'."

    stopover_note = f" Stopovers:{stopovers}" if stopovers else ""

    # Call 1: primary option
    system = (
        f"Transport expert. {currency} prices only.{pref_instruction}"
        f' Return ONLY minified JSON: {{"mode":"flight","operator":"IndiGo","duration":"3h","price_per_person":12000,"total_price":24000,"schedule":"Multiple daily","booking_platform":"MakeMyTrip","fits_budget":true,"local_transport_mode":"Metro/Taxi","local_daily_cost":800}}'
    )
    human = f"From:{source} To:{destination}{stopover_note} Travelers:{num_travelers} Budget:{currency}{transport_bgt:.0f} Pref:{transport_pref or 'any'}{route_context}"
    raw   = _llm_call(system, human)

    # Call 2: alternatives
    system2 = f'Transport alternatives from {source} to {destination}. Return ONLY minified JSON: {{"alternatives":[{{"mode":"train","operator":"Railway","duration":"...","price_per_person":0,"notes":"..."}},{{"mode":"bus","operator":"...","duration":"...","price_per_person":0,"notes":"..."}}]}}'
    raw2    = _llm_call(system2, f"From:{source} To:{destination} Travelers:{num_travelers}")

    try:
        if not raw: raise ValueError("Empty LLM response")
        prim_data  = _parse_json_robust(raw)
        price_pp   = _f(prim_data.get("price_per_person", 0))
        local_cost = _f(prim_data.get("local_daily_cost", 800)) * num_days
        transport  = {
            "source": "OpenRouteService + LLM" if route_data else "LLM estimate",
            "primary_option": {
                "mode":             prim_data.get("mode", transport_pref or "flight"),
                "operator":         prim_data.get("operator", "Multiple operators"),
                "duration":         prim_data.get("duration", "Varies"),
                "price_per_person": price_pp,
                "total_price":      _f(prim_data.get("total_price", price_pp * num_travelers)),
                "schedule":         prim_data.get("schedule", "Check booking platform"),
                "booking_platform": prim_data.get("booking_platform", "MakeMyTrip"),
                "fits_budget":      prim_data.get("fits_budget", True),
            },
            "local_transport": {
                "recommended":      prim_data.get("local_transport_mode", "Metro/Taxi"),
                "daily_cost":       _f(prim_data.get("local_daily_cost", 800)),
                "total_local_cost": local_cost,
                "tips":             "Use metro for short distances, taxi for comfort",
            },
            "total_transport_budget": _f(prim_data.get("total_price", price_pp * num_travelers)) + local_cost,
            "transport_summary": f"{prim_data.get('mode','Flight')} from {source} to {destination}",
        }
        if route_data: transport["live_route"] = route_data
        try:
            alt_data = _parse_json_robust(raw2)
            transport["alternative_options"] = alt_data.get("alternatives", [])
        except Exception:
            transport["alternative_options"] = []
        logger.info("[TransportAgent] %s %s%d/person ✓", transport["primary_option"]["mode"], currency, int(price_pp))
    except Exception as e:
        logger.warning("[TransportAgent] Parse failed: %s — using route-data fallback", e)
        if route_data:
            dist  = route_data.get("distance_km", 500)
            mode  = transport_pref or ("flight" if dist > 700 else "train" if dist > 200 else "bus")
            price_map = {"flight": int(transport_bgt/num_travelers*0.65),
                         "train":  int(transport_bgt/num_travelers*0.15),
                         "bus":    int(transport_bgt/num_travelers*0.08),
                         "car":    int(transport_bgt/num_travelers*0.25)}
            price_pp  = price_map.get(mode, int(transport_bgt/num_travelers*0.5))
        else:
            mode     = transport_pref or "flight"
            price_pp = int(transport_bgt/num_travelers*0.6)

        local_daily = 800 if currency=="INR" else 25
        transport = {
            "transport_summary":    f"{mode.title()} from {source} to {destination}",
            "total_transport_budget": price_pp*num_travelers + local_daily*num_days,
            "source":               "Route calculation fallback",
            "primary_option": {
                "mode": mode, "operator": "Multiple operators",
                "duration": "Varies by schedule",
                "price_per_person": price_pp, "total_price": price_pp*num_travelers,
                "schedule": "Check booking platform for schedules",
                "booking_platform": "MakeMyTrip / Booking.com",
                "fits_budget": price_pp*num_travelers <= transport_bgt,
            },
            "alternative_options": [],
            "local_transport": {
                "recommended": "Auto/Taxi", "daily_cost": local_daily,
                "total_local_cost": local_daily*num_days,
                "tips": f"Use local auto-rickshaws and taxis in {destination}",
            },
        }
        if route_data: transport["live_route"] = route_data

    return {"transport_data": transport, "current_agent": "transport_agent"}


# ═════════════════════════════════════════════════════════════════════════════
# 5. HOTEL AGENT
# ═════════════════════════════════════════════════════════════════════════════

def hotel_agent(state: TripState) -> Dict[str, Any]:
    logger.info("[HotelAgent] Finding accommodation…")
    prefs         = state.get("trip_preferences", {})
    destination   = prefs.get("destination","")
    hotel_pref    = prefs.get("hotel_preference","hotel")
    travel_type   = prefs.get("travel_type") or "general"
    num_days      = int(prefs.get("num_days") or 5)
    total_budget  = _f(prefs.get("budget",0))
    currency      = prefs.get("currency","INR")
    num_travelers = int(prefs.get("travelers") or 2)
    start_date    = prefs.get("start_date","")
    end_date      = prefs.get("end_date","")
    hotel_bgt     = total_budget * 0.40
    max_ppn       = hotel_bgt / max(num_days,1)

    if start_date and not end_date and num_days:
        try:
            from datetime import datetime as _dth, timedelta as _tdh
            end_date = (_dth.strptime(start_date, "%Y-%m-%d") + _tdh(days=int(num_days))).strftime("%Y-%m-%d")
        except Exception:
            pass

    live_context = ""
    if LIVE_APIS_AVAILABLE and start_date and end_date:
        try:
            if _tool_allowed("fetch_hotel_prices",{"destination":destination}):
                live_hotels = fetch_hotel_prices(destination, start_date, end_date, limit=5)
                if live_hotels:
                    rate = 83.0 if currency == "INR" else 1.0
                    live_context = "\nLIVE PRICES (Xotelo):\n"
                    for h in live_hotels[:4]:
                        live_context += f"  - {h['name']}: {currency}{h['best_price']*rate:.0f}/night\n"
        except Exception as e:
            logger.warning("[HotelAgent] Xotelo failed: %s", e)

    hotel_options = []
    tiers = [
        ("Budget Pick",    "3*", int(max_ppn * 0.55), ["wifi","ac"]),
        ("Best Value",     "4*", int(max_ppn * 0.75), ["wifi","ac","breakfast","gym"]),
        ("Comfort Choice", "5*", int(max_ppn * 0.95), ["wifi","ac","pool","spa","breakfast","concierge"]),
    ]

    for tier_name, stars, ppn, amenities in tiers:
        sys_h = (
            f"Suggest ONE real {stars} hotel in {destination} under {currency}{ppn}/night for {travel_type}."
            f" Return ONLY minified JSON:"
            f' {{"name":"actual hotel name","location":"specific area","price_per_night":{ppn},"rating":4.0,"why_pick":"one reason","booking_url":"booking.com"}}'
        )
        human_h = f"{destination} {stars} hotel under {currency}{ppn}/night for {num_travelers} people {num_days} nights.{live_context}"
        raw_h   = _llm_call(sys_h, human_h)
        try:
            if not raw_h: raise ValueError("Empty response")
            h          = _parse_json_robust(raw_h)
            ppn_actual = _f(h.get("price_per_night", ppn))
            hotel_options.append({
                "tier":            tier_name,
                "name":            h.get("name", f"{stars} Hotel {destination}"),
                "category":        stars,
                "location":        h.get("location", destination),
                "price_per_night": ppn_actual,
                "total_cost":      ppn_actual * num_days,
                "amenities":       amenities,
                "rating":          _f(h.get("rating", 4.0)),
                "booking_platform": h.get("booking_url", "Booking.com"),
                "why_pick":        h.get("why_pick", f"Good {stars} option in {destination}"),
            })
            logger.info("[HotelAgent] %s: %s @ %s%d/night", tier_name, h.get("name",""), currency, ppn_actual)
        except Exception as e:
            logger.warning("[HotelAgent] %s parse failed: %s", tier_name, e)
            hotel_options.append({
                "tier": tier_name, "name": f"{tier_name} Hotel in {destination}",
                "category": stars, "location": destination,
                "price_per_night": ppn, "total_cost": ppn * num_days,
                "amenities": amenities, "rating": 3.5 + [t[0] for t in tiers].index(tier_name) * 0.3,
                "booking_platform": "Booking.com",
                "why_pick": f"Affordable {stars} accommodation in {destination}",
            })

    rec_idx         = 1
    recommended     = hotel_options[rec_idx] if len(hotel_options) > 1 else (hotel_options[0] if hotel_options else {"name": f"Hotel in {destination}", "price_per_night": max_ppn * 0.7})
    total_stay_cost = recommended.get("price_per_night", max_ppn * 0.7) * num_days

    hotel = {
        "hotel_options":            hotel_options,
        "recommended_index":        rec_idx,
        "recommended_hotel":        recommended,
        "total_accommodation_cost": total_stay_cost,
        "hotel_tips":               f"Book 30+ days in advance for {destination}. Weekdays are cheaper.",
        "within_budget":            total_stay_cost <= hotel_bgt,
        "source":                   "Xotelo + LLM" if live_context else "LLM estimate",
    }
    logger.info("[HotelAgent] %d options generated, recommended: %s", len(hotel_options), recommended.get("name",""))
    return {"hotel_data": hotel, "current_agent": "hotel_agent"}


# ═════════════════════════════════════════════════════════════════════════════
# 6. PLACES AGENT
# ═════════════════════════════════════════════════════════════════════════════

def places_agent(state: TripState) -> Dict[str, Any]:
    logger.info("[PlacesAgent] Discovering places…")
    prefs       = state.get("trip_preferences", {})
    weather     = state.get("weather_data", {})
    destination = prefs.get("destination","")
    interests   = prefs.get("interests",[])
    food_pref   = prefs.get("food_preference","any")
    travel_type = prefs.get("travel_type") or "general"
    currency    = prefs.get("currency","INR")
    outdoor_ok  = weather.get("outdoor_suitable", True)
    beach_ok    = weather.get("beach_suitable", False)

    live_places = None
    if LIVE_APIS_AVAILABLE and destination:
        try:
            if _tool_allowed("fetch_places",{"destination":destination}):
                live_places = fetch_places(destination, interests, radius_m=20000, limit=20)
                if live_places:
                    logger.info("[PlacesAgent] ✅ Geoapify: %s", live_places.get("places_summary",""))
        except Exception as e:
            logger.warning("[PlacesAgent] Geoapify failed: %s", e)

    if live_places:
        seen_names = set()
        unique_att = []
        for a in live_places.get("top_attractions", []):
            name = a.get("name","").strip()
            if name and name not in seen_names:
                seen_names.add(name); unique_att.append(a)
        live_places["top_attractions"] = unique_att
        logger.info("[PlacesAgent] After dedup: %d unique attractions", len(unique_att))

    att_names  = [a.get("name","") for a in (live_places or {}).get("top_attractions",[])[:5] if a.get("name")]
    rest_names = [r.get("name","") for r in (live_places or {}).get("restaurants",[])[:6] if r.get("name")]
    rate_note  = currency

    sys_att = (
        f"List 5 top attractions in {destination} for {travel_type} trip. All prices in {rate_note}."
        f' Return ONLY minified JSON: {{"attractions":[{{"name":"place","type":"heritage/beach/cultural","duration":"2h","entry_fee":500,"best_time":"morning","rating":4.5,"location":"area","tip":"insider tip"}}]}}'
    )
    raw_att = _llm_call(sys_att, f"Known places: {att_names}. Give 5 DIFFERENT specific places with real {rate_note} entry fees.")

    sys_rest = (
        f"List 5 restaurants in {destination} for {travel_type}. All prices in {rate_note}."
        f' Return ONLY minified JSON: {{"restaurants":[{{"name":"restaurant","cuisine":"type","avg_cost_per_person":1500,"must_try_dish":"dish","location":"area","rating":4.2}}]}}'
    )
    raw_rest = _llm_call(sys_rest, f"Known restaurants: {rest_names}. Give 5 restaurants with REAL {rate_note} prices per person.")

    sys_act = (
        f"List 3 activities in {destination} for {travel_type}. All prices in {rate_note}."
        f' Return ONLY minified JSON: {{"activities":[{{"name":"activity","type":"adventure/relaxation","cost_per_person":2000,"duration":"3h","suitable_for":"couple","tip":"booking tip"}}]}}'
    )
    raw_act = _llm_call(sys_act, f"{destination} {travel_type} activities. Real {rate_note} prices.")

    def _safe_list(raw, key):
        try:
            if not raw: raise ValueError("Empty")
            d = _parse_json_robust(raw)
            return [x for x in d.get(key, []) if isinstance(x, dict) and x.get("name")]
        except Exception:
            return []

    attractions = _safe_list(raw_att, "attractions")
    restaurants = _safe_list(raw_rest, "restaurants")
    activities  = _safe_list(raw_act,  "activities")

    final_attractions = attractions if attractions else (live_places or {}).get("top_attractions", [])
    final_restaurants = restaurants if restaurants else (live_places or {}).get("restaurants", [])

    if not final_attractions:
        logger.warning("[PlacesAgent] No attractions found — generating stubs for %s", destination)
        final_attractions = [
            {"name": f"{destination} Main Attraction",  "type":"sightseeing","duration":"2h","entry_fee":0,"best_time":"morning","rating":4.0,"location":destination,"tip":"Ask locals for the best spots"},
            {"name": f"{destination} Heritage Site",    "type":"heritage",   "duration":"2h","entry_fee":0,"best_time":"morning","rating":4.0,"location":destination,"tip":"Hire a local guide for context"},
            {"name": f"{destination} Nature Viewpoint", "type":"nature",     "duration":"1h","entry_fee":0,"best_time":"evening", "rating":4.2,"location":destination,"tip":"Golden hour is the best time"},
        ]
    if not final_restaurants:
        final_restaurants = [
            {"name":"Local Restaurant","cuisine":"Regional","avg_cost_per_person":300 if currency=="INR" else 15,"must_try_dish":"Regional specialty","location":destination,"rating":4.0},
            {"name":"Hotel Restaurant","cuisine":"Multi-cuisine","avg_cost_per_person":400 if currency=="INR" else 20,"must_try_dish":"Chef special","location":destination,"rating":3.8},
        ]

    enriched = {
        "top_attractions": final_attractions,
        "restaurants":     final_restaurants,
        "activities":      activities,
        "places_summary":  f"Top spots in {destination} for a {travel_type} trip",
        "source":          "Geoapify + LLM" if live_places else "LLM estimate",
    }
    logger.info("[PlacesAgent] Final: %d attractions, %d restaurants, %d activities",
                len(enriched["top_attractions"]), len(enriched["restaurants"]), len(enriched["activities"]))
    return {"places_data": enriched, "current_agent": "places_agent"}


# ═════════════════════════════════════════════════════════════════════════════
# 7. BUDGET AGENT
# ═════════════════════════════════════════════════════════════════════════════

def budget_agent(state: TripState) -> Dict[str, Any]:
    logger.info("[BudgetAgent] Calculating budget…")
    prefs         = state.get("trip_preferences", {})
    transport     = state.get("transport_data", {})
    hotel         = state.get("hotel_data", {})
    places        = state.get("places_data", {})
    total_budget  = _f(prefs.get("budget",0))
    currency      = prefs.get("currency","INR")
    num_travelers = int(prefs.get("travelers") or 2)
    num_days      = int(prefs.get("num_days") or 5)
    destination   = prefs.get("destination","")

    transport_cost = _f(transport.get("total_transport_budget",0))
    if transport_cost == 0:
        prim           = transport.get("primary_option",{})
        transport_cost = _f(prim.get("total_price",0)) + _f(transport.get("local_transport",{}).get("total_local_cost",0))

    hotel_cost = _f(hotel.get("total_accommodation_cost",0))
    if hotel_cost == 0:
        rec        = hotel.get("recommended_hotel",{})
        hotel_cost = _f(rec.get("total_cost",0) or _f(rec.get("price_per_night",0))*num_days)

    activity_cost = sum(_f(a.get("cost_per_person",0))*num_travelers for a in places.get("activities",[])[:4])
    for att in places.get("top_attractions",[])[:5]:
        if att.get("entry_fee"): activity_cost += _f(att["entry_fee"])*num_travelers

    daily_food  = max(300, min(1500, total_budget*0.008)) if currency=="INR" else max(15, min(100, total_budget*0.008))
    food_cost   = daily_food * num_days * num_travelers
    misc_cost   = total_budget * 0.06
    estimated   = transport_cost + hotel_cost + activity_cost + food_cost + misc_cost
    surplus     = total_budget - estimated

    logger.info("[BudgetAgent] transport=%d hotel=%d food=%d activities=%d total=%d",
                transport_cost, hotel_cost, food_cost, activity_cost, estimated)

    budget_result = {
        "budget_summary":    f"Estimated {currency}{estimated:,.0f} of {currency}{total_budget:,.0f} total budget",
        "within_budget":     surplus >= 0,
        "budget_status":     "on_track" if surplus >= 0 else "over_budget",
        "breakdown": {
            "transport":      round(transport_cost),
            "accommodation":  round(hotel_cost),
            "food":           round(food_cost),
            "activities":     round(activity_cost),
            "miscellaneous":  round(misc_cost),
            "estimated_total":round(estimated),
        },
        "surplus_or_deficit": round(surplus),
        "budget_provided":    total_budget,
        "daily_budget":       round(estimated / max(num_days,1)),
        "optimization_tips": [
            f"Book flights to {destination} at least 60 days in advance to save 20-30%",
            f"Use public transport — saves approx {currency}{int(daily_food*0.4)}/day vs taxis",
            "Visit free attractions early in the trip to offset paid activity costs",
        ],
    }
    return {"budget_summary": budget_result, "current_agent": "budget_agent"}


# ═════════════════════════════════════════════════════════════════════════════
# 8. ITINERARY AGENT — LLM activity bank, unique per day, any destination
# ═════════════════════════════════════════════════════════════════════════════

def itinerary_agent(state: TripState) -> Dict[str, Any]:
    logger.info("[ItineraryAgent] Building itinerary…")
    prefs       = state.get("trip_preferences", {})
    weather     = state.get("weather_data", {})
    transport   = state.get("transport_data", {})
    hotel       = state.get("hotel_data", {})
    places      = state.get("places_data", {})
    budget      = state.get("budget_summary", {})

    num_days       = int(prefs.get("num_days") or 5)
    destination    = prefs.get("destination", "")
    source         = prefs.get("source", "")
    travel_type    = prefs.get("travel_type") or "general"
    currency       = prefs.get("currency", "INR")
    transport_mode = transport.get("primary_option", {}).get("mode", "flight")
    daily_budget   = budget.get("daily_budget", 0)
    conditions     = weather.get("conditions", "pleasant")
    hotel_name     = hotel.get("recommended_hotel", {}).get("name") or f"Hotel in {destination}"
    if hotel_name in ("the hotel", "Hotel in "):
        hotel_name = f"Hotel in {destination}"

    all_attractions = [a.get("name","") for a in places.get("top_attractions",[])[:12] if a.get("name")]
    all_restaurants = [r.get("name","") for r in places.get("restaurants",[])[:8] if r.get("name")]
    all_activities  = [a.get("name","") for a in places.get("activities",[])[:6] if a.get("name")]

    # Step 1: LLM generates activity bank for this destination
    count = min(num_days * 3, 15)
    system_bank = (
        f"You are a {destination} travel expert. "
        f"List {count} unique, specific things to do in {destination} for a {travel_type} trip. "
        f"Each must be a specific named place or experience. Mix landmarks, hidden gems, food, culture, outdoors. "
        f'Return ONLY minified JSON: {{"activities":["activity 1","activity 2",...]}}'
    )
    dest_bank = []
    try:
        raw_bank  = _llm_call(system_bank, f"Destination:{destination} Style:{travel_type} Weather:{conditions}. Give {count} completely different specific activities.")
        if raw_bank:
            bank_data = _parse_json_robust(raw_bank)
            dest_bank = [a for a in bank_data.get("activities", []) if isinstance(a, str) and len(a) > 3]
            logger.info("[ItineraryAgent] Activity bank: %d activities for %s", len(dest_bank), destination)
    except Exception as e:
        logger.warning("[ItineraryAgent] Activity bank failed: %s — using Geoapify only", e)

    activity_pool = []
    for item in (dest_bank + all_attractions + all_activities):
        if item and item not in activity_pool:
            activity_pool.append(item)
    logger.info("[ItineraryAgent] Total activity pool: %d items", len(activity_pool))

    # Step 2: Generate each day
    used_activities: List[str] = []
    days: List[Dict] = []

    for day_num in range(1, num_days + 1):
        available = [a for a in activity_pool if a not in used_activities]
        day_picks = available[:3] if len(available) >= 3 else (available + [f"Free exploration in {destination}"])
        used_activities.extend(day_picks[:2])

        rest_idx    = (day_num - 1) % max(len(all_restaurants), 1)
        dinner_rest = all_restaurants[rest_idx] if all_restaurants else f"local {destination} restaurant"

        is_first = day_num == 1
        is_last  = day_num == num_days

        system = (
            f"Output ONLY minified JSON. No spaces. Max 450 tokens."
            f' Format: {{"day":{day_num},"theme":"unique theme for this day",'
            f'"morning":{{"activity":"specific place","location":"area","tip":"insider tip"}},'
            f'"afternoon":{{"activity":"specific place","location":"area","tip":"insider tip"}},'
            f'"evening":{{"activity":"specific place","location":"area","tip":"insider tip"}},'
            f'"night":{{"activity":"activity","location":"area"}},'
            f'"meals":{{"breakfast":"place","lunch":"place","dinner":"{dinner_rest}"}},'
            f'"accommodation":"{hotel_name}","estimated_day_cost":0}}'
        )

        travel_note = f"Day 1: arrive from {source} by {transport_mode}. Check in first. " if is_first and source else ""
        depart_note = f"Last day: morning activity then checkout and airport. " if is_last else ""
        human = (
            f"{travel_note}{depart_note}"
            f"Day {day_num}/{num_days} in {destination}. {travel_type} trip. "
            f"MUST USE these specific places (different from all other days): {day_picks}. "
            f"Weather:{conditions} {weather.get('avg_temp_day','28C')}. Add insider tips."
        )

        raw = _llm_call(system, human)

        try:
            if not raw: raise ValueError("Empty response")
            day_obj = _parse_json_robust(raw)
            if not isinstance(day_obj, dict): raise ValueError("Not a dict")
            day_obj["day"] = day_num
            days.append(day_obj)
            logger.info("[ItineraryAgent] Day %d/%d: %s ✓", day_num, num_days, day_obj.get("theme",""))
        except Exception as e:
            logger.warning("[ItineraryAgent] Day %d parse failed: %s — using structured fallback", day_num, e)
            themes = ["Arrival & Exploration","Sightseeing & Culture","Nature & Adventure",
                      "Local Experiences","Relaxation & Shopping","Hidden Gems","Farewell Day"]
            theme  = themes[(day_num-1) % len(themes)]
            if is_first: theme = "Arrival & First Impressions"
            if is_last:  theme = "Farewell & Departure"
            days.append({
                "day": day_num, "theme": theme,
                "morning":   {"activity": day_picks[0] if day_picks else f"Explore {destination}", "location": destination, "tip": "Start early to beat the crowds"},
                "afternoon": {"activity": day_picks[1] if len(day_picks)>1 else f"Discover local attractions", "location": destination, "tip": "Take a break and try a local cafe"},
                "evening":   {"activity": day_picks[2] if len(day_picks)>2 else f"Sunset views in {destination}", "location": destination, "tip": "Golden hour offers the best photography light"},
                "night":     {"activity": f"Dinner at {dinner_rest}", "location": destination},
                "meals":     {"breakfast": f"Breakfast at {hotel_name}", "lunch": "Local restaurant", "dinner": dinner_rest},
                "accommodation": hotel_name,
                "estimated_day_cost": int(daily_budget) if daily_budget else 2000,
            })

    # Step 3: Trip meta
    system2 = (
        f'Output minified JSON: {{"trip_title":"catchy title for {destination} {travel_type} trip",'
        f'"packing_checklist":["item1","item2","item3","item4","item5"],'
        f'"travel_tips":["specific tip1","tip2","tip3"],'
        f'"emergency_contacts":{{"police":"local number","ambulance":"local number","tourist_helpline":"local number"}}}}'
    )
    raw2 = _llm_call(system2, f"{num_days}-day {destination} {travel_type} trip. {conditions} weather.")
    try:
        if not raw2: raise ValueError("Empty")
        meta = _parse_json_robust(raw2)
    except Exception:
        meta = {
            "trip_title":        f"{num_days}-Day {destination} Trip",
            "packing_checklist": ["Passport & visa","Sunscreen SPF50+","Light breathable clothing","Comfortable walking shoes","Power bank & adaptor"],
            "travel_tips":       [f"Visit popular {destination} attractions early morning", "Book activities 2 days in advance", "Keep copies of all documents"],
            "emergency_contacts":{"police":"100","ambulance":"108","tourist_helpline":"1363"},
        }

    itinerary = {
        "trip_title":        meta.get("trip_title", f"{num_days}-Day {destination} Trip"),
        "days":              days,
        "packing_checklist": meta.get("packing_checklist", []),
        "travel_tips":       meta.get("travel_tips", []),
        "emergency_contacts":meta.get("emergency_contacts", {}),
    }
    logger.info("[ItineraryAgent] Complete — %d/%d days generated", len(days), num_days)

    # Step 4: Attach weather
    daily_lookup   = weather.get("daily_lookup", {})
    start_date_str = prefs.get("start_date", "")
    if itinerary.get("days"):
        if daily_lookup and start_date_str:
            try:
                from datetime import datetime as _dt2, timedelta as _td2
                start_dt = _dt2.strptime(start_date_str, "%Y-%m-%d")
                for i, day in enumerate(itinerary["days"]):
                    day_date          = (start_dt + _td2(days=i)).strftime("%Y-%m-%d")
                    day["date"]       = day_date
                    day["date_label"] = (start_dt + _td2(days=i)).strftime("%d %b")
                    day["weather"]    = daily_lookup.get(day_date, {
                        "max_temp": weather.get("avg_temp_day","N/A"),
                        "min_temp": weather.get("avg_temp_night","N/A"),
                        "conditions": conditions, "emoji": "🌤️",
                    })
            except Exception as e:
                logger.warning("[ItineraryAgent] Weather date matching failed: %s", e)
        else:
            overall = {"max_temp": weather.get("avg_temp_day","N/A"), "min_temp": weather.get("avg_temp_night","N/A"), "conditions": conditions, "emoji": "🌤️"}
            for day in itinerary["days"]:
                day.setdefault("weather", overall)

    if GUARDRAILS_AVAILABLE and itinerary.get("days"):
        try:
            itinerary = output_guard_itinerary(itinerary, prefs)
        except Exception:
            pass

    return {"itinerary": itinerary, "current_agent": "itinerary_agent"}


# ═════════════════════════════════════════════════════════════════════════════
# 9. FINAL REVIEW AGENT
# ═════════════════════════════════════════════════════════════════════════════

def final_review_agent(state: TripState) -> Dict[str, Any]:
    logger.info("[FinalReviewAgent] Validating…")
    prefs   = state.get("trip_preferences",{})
    budget  = state.get("budget_summary",{})
    weather = state.get("weather_data",{})
    hotel   = state.get("hotel_data",{})
    itin    = state.get("itinerary",{})

    conflicts, warnings = [], []
    if not budget.get("within_budget", True):
        deficit = abs(_f(budget.get("surplus_or_deficit",0)))
        conflicts.append(f"Budget overrun by {prefs.get('currency','INR')}{deficit:.0f}")
    if not hotel.get("within_budget", True):
        conflicts.append("Hotel exceeds budget")
    for w in weather.get("weather_warnings",[]):
        if w and len(w) > 3: warnings.append(f"Weather: {w}")

    days_planned = len(itin.get("days",[]))
    num_days     = int(prefs.get("num_days") or 5)
    if days_planned < num_days:
        warnings.append(f"Itinerary has {days_planned} days, expected {num_days}")

    hallucination_report = {}
    if GUARDRAILS_AVAILABLE:
        try:
            hallucination_report = hallucination_guard(state)
            if not hallucination_report.get("passed", True):
                for flag in hallucination_report.get("flags",[]):
                    warnings.append(f"🔍 {flag}")
        except Exception:
            pass

    approved = len(conflicts) == 0
    return {
        "review_status": {
            "approved": approved,
            "status":   "approved" if approved else "needs_revision",
            "conflicts": conflicts, "warnings": warnings,
            "hallucination_report": hallucination_report,
            "review_summary": "✅ All checks passed." if approved else f"⚠️ {'; '.join(conflicts)}",
        },
        "current_agent": "final_review_agent",
    }


# ═════════════════════════════════════════════════════════════════════════════
# 10. MEMORY UPDATE AGENT
# ═════════════════════════════════════════════════════════════════════════════

def memory_update_agent(state: TripState) -> Dict[str, Any]:
    prefs   = state.get("trip_preferences",{})
    profile = state.get("user_profile",{})
    past    = profile.get("past_trips",[])
    dest    = prefs.get("destination","")
    if dest and dest not in past: past.append(dest)
    return {
        "user_profile": {**profile, "past_trips": past, "last_trip": prefs,
                         "last_updated": datetime.now().isoformat()},
        "current_agent": "memory_update_agent",
    }


# ═════════════════════════════════════════════════════════════════════════════
# 11. HOTEL OPTIONS PER LOCATION AGENT
# ═════════════════════════════════════════════════════════════════════════════

def hotel_options_per_location_agent(state: TripState) -> Dict[str, Any]:
    logger.info("[HotelLocationAgent] Generating hotel options per location…")
    prefs    = state.get("trip_preferences",{})
    itin     = state.get("itinerary",{})
    days     = itin.get("days",[])
    currency = prefs.get("currency","INR")
    total    = _f(prefs.get("budget",0))
    num_days = int(prefs.get("num_days") or max(len(days),1))
    travelers= int(prefs.get("travelers") or 2)
    max_ppn  = (total*0.40) / max(num_days,1)

    locations_seen = []
    for day in days:
        loc = (day.get("accommodation") or day.get("morning",{}).get("location","") or prefs.get("destination",""))
        loc = loc.split(",")[0].strip() if loc else prefs.get("destination","")
        if loc and loc not in locations_seen: locations_seen.append(loc)
    if not locations_seen:
        locations_seen = [prefs.get("destination","Destination")]

    options_by_loc = {}
    for loc in locations_seen:
        system = (
            f"Hotel expert for {loc}. Max {currency}{max_ppn:.0f}/night. 3 real hotels."
            f' Return ONLY JSON: {{"options":[{{"tier":"Budget","name":"real name","stars":"3*","location":"area","price_per_night":0,"total_for_stay":0,"amenities":["wifi","ac"],"rating":3.5,"book_on":"Booking.com","highlight":"reason"}},{{"tier":"Mid-range","name":"...","stars":"4*","location":"area","price_per_night":0,"total_for_stay":0,"amenities":["wifi","breakfast"],"rating":4.0,"book_on":"MakeMyTrip","highlight":"reason"}},{{"tier":"Premium","name":"...","stars":"5*","location":"area","price_per_night":0,"total_for_stay":0,"amenities":["wifi","pool","spa"],"rating":4.5,"book_on":"Booking.com","highlight":"reason"}}]}}'
        )
        raw = _llm_call(system, f"Location:{loc} Nights:{num_days} Travelers:{travelers} Max:{currency}{max_ppn:.0f}/night")
        try:
            if not raw: raise ValueError("Empty")
            options_by_loc[loc] = _parse_json_robust(raw).get("options",[])
        except Exception:
            options_by_loc[loc] = [
                {"tier":"Budget",    "name":f"Budget Hotel {loc}",  "stars":"3*", "location":loc, "price_per_night":max_ppn*0.5,  "amenities":["wifi"],"rating":3.5,"book_on":"Booking.com","highlight":"Affordable"},
                {"tier":"Mid-range", "name":f"Comfort Inn {loc}",   "stars":"4*", "location":loc, "price_per_night":max_ppn*0.75, "amenities":["wifi","breakfast"],"rating":4.0,"book_on":"MakeMyTrip","highlight":"Good value"},
                {"tier":"Premium",   "name":f"Grand Hotel {loc}",   "stars":"5*", "location":loc, "price_per_night":max_ppn,      "amenities":["wifi","pool","breakfast"],"rating":4.5,"book_on":"Booking.com","highlight":"Best comfort"},
            ]

    return {
        "hotel_options_by_location": options_by_loc,
        "itinerary_locations":       locations_seen,
        "hotel_selection_step":      0,
        "hotel_selections":          {},
        "flow_stage":                "selecting_hotels",
        "current_agent":             "hotel_options_per_location_agent",
    }