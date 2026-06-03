"""backend/routers/clarify.py"""
import re
import logging
from fastapi import APIRouter
from models.schemas import ClarifyRequest, ClarifyResponse, ClarifyQuestion, TripPreferences

logger = logging.getLogger("thrillophilia.routers.clarify")
router = APIRouter()

REQUIRED_FIELDS = ["destination", "num_days", "budget", "travelers", "source"]
FIELD_QUESTIONS = {
    "destination": "Where do you want to go?",
    "source":      "Where are you travelling from?",
    "num_days":    "How many days is your trip?",
    "budget":      "What is your total budget? (e.g. ₹50,000 or $1,000)",
    "travelers":   "How many people are travelling?",
}

# Known cities for destination/source extraction
KNOWN_CITIES = [
    "dubai","goa","kerala","rajasthan","manali","andaman","darjeeling","ladakh","leh",
    "rishikesh","coorg","udaipur","varanasi","mumbai","delhi","bangalore","chennai",
    "kolkata","jaipur","bali","thailand","maldives","paris","singapore","switzerland",
    "japan","barcelona","london","new york","santorini","shimla","pathankot","kargil",
    "spiti","kasol","dharamshala","amritsar","chandigarh","dehradun","mussoorie",
    "nainital","pondicherry","hampi","coorg","ooty","mysore","agra","varanasi",
]


def _regex_extract(text: str) -> dict:
    """Extract trip fields from query text using regex — no LLM needed."""
    t   = text.lower()
    out = {}

    # ── Destination ───────────────────────────────────────────────
    for city in KNOWN_CITIES:
        if city in t:
            # Prefer "to X" pattern, fall back to any mention
            m = re.search(rf'\bto\s+{city}\b', t)
            if m or city in t:
                out["destination"] = city.title()
                break

    # ── Source — "from X" ─────────────────────────────────────────
    m = re.search(r'\bfrom\s+([a-zA-Z\s]+?)(?:\s+(?:with|for|in|on|budget|plan|to)\b|,|$)', text, re.I)
    if m:
        src = m.group(1).strip().title()
        # Check it's a real city name (not "from Delhi with" → "Delhi")
        if len(src.split()) <= 3 and len(src) > 2:
            out["source"] = src

    # ── Days ──────────────────────────────────────────────────────
    m = re.search(r'(\d+)\s*[-\s]?\s*(?:day|days|night|nights)', t)
    if m:
        out["num_days"] = int(m.group(1))

    # ── Budget ────────────────────────────────────────────────────
    m = re.search(r'(?:budget\s+(?:of\s+)?|₹|rs\.?\s*|inr\s*)(\d[\d,]*)', t)
    if not m:
        m = re.search(r'(\d[\d,]+)\s*(?:budget|rupees|inr)', t)
    if m:
        out["budget"]   = int(m.group(1).replace(",", ""))
        out["currency"] = "INR"
    m2 = re.search(r'\$\s*(\d[\d,]*)', t)
    if m2:
        out["budget"]   = int(m2.group(1).replace(",",""))
        out["currency"] = "USD"

    # ── Travelers ─────────────────────────────────────────────────
    if any(x in t for x in ["wife","husband","partner","honeymoon","couple"]):
        out.setdefault("travelers", 2)
        out["travel_type"] = "couple"
    if "family" in t:
        out.setdefault("travel_type", "family")
    if "solo" in t or "alone" in t:
        out.setdefault("travelers", 1)
        out["travel_type"] = "solo"
    m = re.search(r'(\d+)\s+(?:people|persons?|travelers?|pax|of us)', t)
    if m:
        out["travelers"] = int(m.group(1))
    out.setdefault("travelers", 2)  # default 2 if not specified

    # ── Date ──────────────────────────────────────────────────────
    month_map = {
        "january":"01","february":"02","march":"03","april":"04","may":"05","june":"06",
        "july":"07","august":"08","september":"09","october":"10","november":"11","december":"12"
    }
    for month_name, month_num in month_map.items():
        if month_name in t:
            from datetime import datetime
            yr   = datetime.now().year
            if int(month_num) < datetime.now().month:
                yr += 1
            day  = "15" if "mid" in t else ("01" if "early" in t else "20")
            out["start_date"] = f"{yr}-{month_num}-{day}"
            break

    # ── Currency fallback ─────────────────────────────────────────
    out.setdefault("currency", "INR")

    return out


def _is_missing(val) -> bool:
    if val is None: return True
    if isinstance(val, str) and val.strip().lower() in ("","null","none","unknown"): return True
    if isinstance(val, (int,float)) and val == 0: return True
    return False


@router.post("/clarify", response_model=ClarifyResponse)
async def clarify_query(request: ClarifyRequest):
    """
    Extract trip fields from query using FAST regex first.
    Only calls LLM if regex fails to extract enough.
    This means the popup never appears for complete queries.
    """
    # Step 1 — fast regex extraction (no LLM, instant)
    regex_extracted = _regex_extract(request.query)

    # Step 2 — merge with any already-extracted fields from frontend
    existing = request.extracted.model_dump() if request.extracted else {}
    merged   = {}
    for k, v in existing.items():
        if not _is_missing(v):
            merged[k] = v
    for k, v in regex_extracted.items():
        if not _is_missing(v):
            merged[k] = v

    # Step 3 — check what's still missing
    missing   = [f for f in REQUIRED_FIELDS if _is_missing(merged.get(f))]
    questions = [ClarifyQuestion(field=f, question=FIELD_QUESTIONS[f]) for f in missing]

    logger.info(
        "[Clarify] Query: '%s...' → extracted: %s → missing: %s",
        request.query[:60], {k:v for k,v in merged.items() if k in REQUIRED_FIELDS}, missing
    )

    # Step 4 — if still missing fields, try LLM as fallback (non-blocking)
    if missing:
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from dotenv import load_dotenv
            load_dotenv(Path(__file__).parent.parent / ".env", override=True)
            from agents.agents import user_input_agent
            fake_state = {
                "user_query":            request.query,
                "trip_preferences":      merged,
                "clarification_answers": {},
                "conversation_history":  [],
            }
            import asyncio
            loop   = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, user_input_agent, fake_state),
                timeout=8.0   # 8 second max — don't make user wait longer
            )
            llm_prefs = result.get("trip_preferences", {})
            for k, v in llm_prefs.items():
                if not _is_missing(v) and k in REQUIRED_FIELDS:
                    merged[k] = v
            # Recheck missing after LLM
            missing   = [f for f in REQUIRED_FIELDS if _is_missing(merged.get(f))]
            questions = [ClarifyQuestion(field=f, question=FIELD_QUESTIONS[f]) for f in missing]
        except Exception as e:
            logger.warning("[Clarify] LLM fallback failed or timed out (%s) — using regex only", e)
            # Still proceed with regex results

    # Build TripPreferences response
    pref_fields = TripPreferences.model_fields.keys()
    extracted_obj = TripPreferences(**{k: merged.get(k) for k in pref_fields if k in merged})

    return ClarifyResponse(
        missing_fields = missing,
        questions      = questions,
        show_popup     = len(missing) > 0,
        extracted      = extracted_obj,
    )