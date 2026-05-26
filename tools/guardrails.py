"""
tools/guardrails.py  —  Thrillophilia AI Trip Planner Guardrails
=================================================================
All 9 guardrail layers:
  1. PII MASKER          — Masks phone, card, email, Aadhaar, PAN, UPI, IFSC
  2. ABUSE GUARD         — Blocks profane / threatening language
  3. HATE GUARD          — Blocks racist / discriminatory content
  4. SCOPE GUARD         — Travel-only, blocks jailbreaks & role hijacking
  5. OUTPUT GUARD (FULL) — Scans ALL itinerary fields for PII + unsafe content
  6. HALLUCINATION GUARD — Validates prices, day count, destination, budget
  7. RETRIEVAL GUARD     — Filters unsafe / injected FAISS chunks
  8. TOOL GUARD          — Allowlist + bounds for live API calls
  9. RATE LIMITER        — Session-level query cooldown
"""

import re
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from langsmith import traceable

logger = logging.getLogger("trip_planner.guardrails")


# ─────────────────────────────────────────────────────────────────────────────
# RESULT DATACLASS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GuardrailResult:
    blocked:  bool
    reason:   str
    clean:    str
    category: str   # scope | abuse | hate | pii | output | hallucination | tool | rate | ok


# ═════════════════════════════════════════════════════════════════════════════
# 1. PII MASKER
# ═════════════════════════════════════════════════════════════════════════════

PII_RULES = [
    (re.compile(r"(?:\+91[-\s]?|91[-\s]?|0)?[6-9]\d{9}\b"),               "📵 [PHONE MASKED]"),
    (re.compile(r"\+\d{1,3}[-\s]?\(?\d{1,4}\)?[-\s]?\d{1,4}[-\s]?\d{4,9}"), "📵 [PHONE MASKED]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"),                                  "💳 [CARD MASKED]"),
    (re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),                    "🪪 [AADHAAR MASKED]"),
    (re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),                               "🪪 [PAN MASKED]"),
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "📧 [EMAIL MASKED]"),
    (re.compile(r"\b[A-Za-z0-9.\-_]+@(okaxis|oksbi|okicici|okhdfcbank|ybl|upi)\b"), "💳 [UPI MASKED]"),
    (re.compile(r"(?i)(?:cvv|cvc|security\s+code)[\s:]+\d{3,4}\b"),          "💳 [CVV MASKED]"),
    (re.compile(r"(?i)(?:account|a/?c|acct)[\s#:]+\d{9,18}\b"),              "🏦 [ACCOUNT MASKED]"),
    (re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),                                "🏦 [IFSC MASKED]"),
    (re.compile(r"\b[A-Z]{1,2}[0-9]{7}\b"),                                  "🛂 [PASSPORT MASKED]"),
]

@traceable(name="Guardrail.pii_masker", run_type="tool")
def pii_masker(text: str) -> GuardrailResult:
    """Scan and mask all PII. Never blocks — always returns clean version."""
    masked, found = text, []
    for pattern, replacement in PII_RULES:
        new_text, count = pattern.subn(replacement, masked)
        if count > 0:
            found.append(replacement)
            masked = new_text
    if found:
        logger.info("PII_MASKER: masked %d item(s)", len(found))
    return GuardrailResult(
        blocked=False, reason="", clean=masked,
        category="pii" if found else "ok",
    )


def _mask_string(text: str) -> str:
    """Apply PII masking to a single string. Returns masked version."""
    return pii_masker(text).clean


# ═════════════════════════════════════════════════════════════════════════════
# 2. ABUSE GUARD
# ═════════════════════════════════════════════════════════════════════════════

_ABUSE = re.compile(
    r"\b(f+u+c+k+\w*|s+h+i+t+\w*|b+i+t+c+h+\w*|a+s+s+h+o+l+e+\w*"
    r"|b+a+s+t+a+r+d+\w*|c+u+n+t+\w*|d+i+c+k+\w*|wh+o+r+e+\w*"
    r"|s+l+u+t+\w*|m+o+r+o+n+\w*|d+u+m+b+a+s+s+\w*|i+d+i+o+t"
    r"|b+c|m+c|b+k+l|m+a+d+a+r+c+h+\w*|b+h+e+n+c+h+\w*"
    r"|c+h+u+t+i+y+\w*|g+a+n+d+u+\w*)\b"
    r"|\b(kill|harm|hurt|attack)\s+your?self\b"
    r"|\bi\s+will\s+(kill|hurt|harm|attack)\b",
    re.IGNORECASE
)

@traceable(name="Guardrail.abuse_guard", run_type="tool")
def abuse_guard(text: str) -> GuardrailResult:
    if _ABUSE.search(text):
        logger.warning("ABUSE_GUARD triggered")
        return GuardrailResult(
            blocked=True,
            reason=(
                "⚠️ Please keep our conversation respectful. "
                "Thrillophilia is committed to a safe and welcoming experience. "
                "Let's start fresh — where would you like to travel? 🌏"
            ),
            clean=text, category="abuse",
        )
    return GuardrailResult(blocked=False, reason="", clean=text, category="ok")


# ═════════════════════════════════════════════════════════════════════════════
# 3. HATE GUARD
# ═════════════════════════════════════════════════════════════════════════════

_HATE = re.compile(
    r"\b(n+i+g+g+\w*|ch+i+n+k+\w*|sp+i+c+\w*|k+y+k+e+\w*|p+a+k+i+\w*)\b"
    r"|\b(master\s+race|white\s+supremacy|ethnic\s+cleansing|aryan\s+race)\b"
    r"|\b(kill|eliminate|remove)\s+all\s+(muslims?|hindus?|christians?|sikhs?|jews?)\b"
    r"|\b(women|girls)\s+(belong|should\s+be)\s+in\s+the\s+kitchen\b",
    re.IGNORECASE
)

@traceable(name="Guardrail.hate_guard", run_type="tool")
def hate_guard(text: str) -> GuardrailResult:
    if _HATE.search(text):
        logger.warning("HATE_GUARD triggered")
        return GuardrailResult(
            blocked=True,
            reason=(
                "🚫 Thrillophilia celebrates the diversity of our world. "
                "We do not tolerate discriminatory or hateful language. "
                "Ready to explore the world together? 🌍"
            ),
            clean=text, category="hate",
        )
    return GuardrailResult(blocked=False, reason="", clean=text, category="ok")


# ═════════════════════════════════════════════════════════════════════════════
# 4. SCOPE GUARD (competitor block + role hijacking)
# ═════════════════════════════════════════════════════════════════════════════

_TRAVEL_KW = {
    "trip","travel","tour","visit","plan","book","explore","holiday","vacation",
    "journey","itinerary","route","fly","flight","train","hotel","resort","stay",
    "accommodation","hostel","destination","airport","beach","mountain","trek",
    "adventure","nightlife","culture","heritage","food","restaurant","sightseeing",
    "budget","luxury","honeymoon","family","solo","couple","friends","group","days",
    "nights","week","weather","visa","passport","packing","goa","kerala","manali",
    "rajasthan","mumbai","delhi","bangalore","bengaluru","hyderabad","chennai",
    "kolkata","jaipur","udaipur","shimla","darjeeling","andaman","bali","bangkok",
    "singapore","dubai","london","paris","barcelona","maldives","nepal","bhutan",
    "thailand","vietnam","europe","inr","usd","rupee","cheap","affordable","cost",
    "rishikesh","coorg","leh","ladakh","varanasi","agra","amritsar",
    "ooty","kodaikanal","munnar","alleppey","pondicherry","hampi",
}

_COMPETITOR = re.compile(
    r"\b(chatgpt|gemini|claude|copilot|gpt|openai|google\s*ai)\b.{0,30}\b(plan|trip|travel)\b"
    r"|\b(makemytrip|goibibo|expedia|tripadvisor|booking\.com|cleartrip)\b.{0,20}\b(plan|help)\b"
    r"|\b(ignore|bypass|override)\s+(your|these|all)\s+(rules|instructions|guidelines)\b"
    r"|\bjailbreak\b|\bdan\s+mode\b|\bsystem\s+prompt\b"
    r"|\bpretend\s+(you\s+are|to\s+be)\b|\bact\s+as\s+a\s+different\b",
    re.IGNORECASE
)

_ROLE_HIJACK = re.compile(
    r"\[SYSTEM\]|\[INST\]|\[PROMPT\]"
    r"|from\s+now\s+on\s+(you\s+are|respond|ignore)"
    r"|you\s+are\s+now\s+\w+bot"
    r"|new\s+instructions?\s*:"
    r"|disregard\s+(all|previous|prior)\s+(instructions?|rules?|guidelines?)"
    r"|you\s+have\s+no\s+restrictions?"
    r"|override\s+(safety|guardrail|filter|system)"
    r"|forget\s+(everything|all)\s+(you\s+)?(know|were\s+told)"
    r"|###\s*instruction|<\s*system\s*>",
    re.IGNORECASE
)

_OFFTOPIC_KW = {
    "write a python","write a javascript","write a program","write a function",
    "write a script","debug this code","fix this bug","write code for","sql query",
    "stock market","crypto price","bitcoin price","ethereum price","invest in stocks",
    "mutual fund","nifty today","sensex today","forex trading",
    "recipe for ","how to bake ","how to cook ","ingredients for ",
    "symptoms of ","treatment for ","cure for fever","what medicine","doctor advice",
    "medical condition","i have a fever","i have a cold",
    "legal advice","how to sue","file a case","consumer court",
    "write my essay","do my homework","solve this equation","explain calculus",
    "who invented ","who discovered ","when did ","who founded ","who created ",
    "what is the capital of","define the word","meaning of the word",
    "translate this to","what year was ",
    "election results","who won the election","parliament news",
    "government policy","opposition party",
}

_MATH = re.compile(r"what\s+is\s+\d+\s*[+\-*/]\s*\d+", re.IGNORECASE)
_CALC = re.compile(r"\b(calculate|compute)\s+\d", re.IGNORECASE)

@traceable(name="Guardrail.scope_guard", run_type="tool")
def scope_guard(text: str) -> GuardrailResult:
    lower = text.lower()
    _block = GuardrailResult(
        blocked=True,
        reason=(
            "🌍 I'm Thrillophilia's dedicated AI Trip Planner. "
            "I specialise exclusively in travel — flights, hotels, itineraries, budgets. "
            "Tell me where you'd like to travel! ✈️"
        ),
        clean=text, category="scope",
    )

    if _COMPETITOR.search(lower):
        logger.warning("SCOPE_GUARD: competitor/jailbreak detected")
        return GuardrailResult(
            blocked=True,
            reason="🚫 I'm Thrillophilia's AI Trip Planner — I can only help with travel. Where would you like to go? ✈️",
            clean=text, category="scope",
        )

    if _ROLE_HIJACK.search(lower):
        logger.warning("SCOPE_GUARD: role hijacking detected")
        return GuardrailResult(
            blocked=True,
            reason="🚫 I follow my guidelines at all times. I'm here to help plan your trip — where would you like to travel? ✈️",
            clean=text, category="scope",
        )

    if _MATH.search(lower) or _CALC.search(lower):
        return _block

    for kw in _OFFTOPIC_KW:
        if kw in lower:
            logger.warning("SCOPE_GUARD: off-topic '%s'", kw)
            return _block

    if len(text.split()) <= 5:
        return GuardrailResult(blocked=False, reason="", clean=text, category="ok")

    words = set(re.findall(r"\b\w+\b", lower))
    if words & _TRAVEL_KW:
        return GuardrailResult(blocked=False, reason="", clean=text, category="ok")

    logger.warning("SCOPE_GUARD: no travel intent")
    return _block


# ═════════════════════════════════════════════════════════════════════════════
# 5. OUTPUT GUARD — FULL SCAN of all itinerary fields
# ═════════════════════════════════════════════════════════════════════════════

_UNSAFE_OUTPUT = re.compile(
    r"\b(make\s+a\s+bomb|how\s+to\s+kill|illegal\s+weapon|smuggl)"
    r"|\b(hack|crack|exploit)\s+(this|the)\s+(system|account|password)",
    re.IGNORECASE
)

@traceable(name="Guardrail.output_guard", run_type="tool")
def output_guard(response: str, prefs: dict = None) -> GuardrailResult:
    """
    Validate a plain-text LLM response (e.g. trip title, tips, summary).
    Checks for unsafe content and re-masks PII.
    """
    if _UNSAFE_OUTPUT.search(response):
        logger.warning("OUTPUT_GUARD: unsafe content in response")
        return GuardrailResult(
            blocked=True,
            reason="⚠️ Response contained unsafe content and was blocked.",
            clean=response, category="output",
        )
    pii_result = pii_masker(response)
    return GuardrailResult(
        blocked=False, reason="", clean=pii_result.clean, category="output",
    )


def output_guard_itinerary(itinerary: dict, prefs: dict = None) -> dict:
    """
    Full scan of every string field inside the itinerary dict.
    Masks PII in activity descriptions, meal names, accommodation,
    travel tips, packing checklist — everywhere the LLM wrote text.
    Returns a fully sanitised itinerary dict.
    """
    if not itinerary:
        return itinerary

    pii_found = 0

    def _clean(val):
        nonlocal pii_found
        if not isinstance(val, str):
            return val
        result = pii_masker(val)
        if result.category == "pii":
            pii_found += 1
        if _UNSAFE_OUTPUT.search(val):
            logger.warning("OUTPUT_GUARD: unsafe content in itinerary field — cleared")
            return "[content removed]"
        return result.clean

    def _deep_clean(obj):
        """Recursively clean all string values in a dict/list."""
        if isinstance(obj, str):
            return _clean(obj)
        if isinstance(obj, dict):
            return {k: _deep_clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_deep_clean(item) for item in obj]
        return obj

    cleaned = _deep_clean(itinerary)

    if pii_found > 0:
        logger.warning("OUTPUT_GUARD_ITINERARY: masked PII in %d itinerary fields", pii_found)

    return cleaned


# ═════════════════════════════════════════════════════════════════════════════
# 6. HALLUCINATION GUARD
# ═════════════════════════════════════════════════════════════════════════════
@traceable(name="Guardrail.hallucination_guard", run_type="tool")
def hallucination_guard(result: dict) -> Dict[str, Any]:
    """
    Validate LLM-generated content against known constraints.
    Returns a report dict with:
      - passed: bool  (True = no hallucinations detected)
      - flags:  list of detected issues
      - score:  float 0.0-1.0 (1.0 = fully clean)

    Checks:
      1. Day count matches num_days
      2. Destination mentioned in itinerary
      3. Hotel prices within 40% budget slice
      4. Budget estimate is non-zero and reasonable
      5. All itinerary days have required fields
      6. Transport mode is realistic for the route distance
    """
    flags = []
    checks_run = 0
    checks_passed = 0

    prefs    = result.get("trip_preferences", {})
    itin     = result.get("itinerary", {})
    hotel    = result.get("hotel_data", {})
    budget   = result.get("budget_summary", {})
    transport= result.get("transport_data", {})
    days     = itin.get("days", [])

    currency     = prefs.get("currency", "INR")
    num_days     = int(prefs.get("num_days", 0))
    total_budget = float(prefs.get("budget", 0) or 0)
    destination  = prefs.get("destination", "").lower()

    # ── Check 1: Day count ────────────────────────────────────────────────────
    if num_days > 0:
        checks_run += 1
        days_generated = len(days)
        if days_generated == num_days:
            checks_passed += 1
        else:
            flags.append(
                f"DAY_COUNT: Expected {num_days} days, got {days_generated}"
            )
            logger.warning("HALLUCINATION_GUARD: day count mismatch %d vs %d",
                           days_generated, num_days)

    # ── Check 2: Destination present in itinerary ─────────────────────────────
    if destination and days:
        checks_run += 1
        itin_text = str(itin).lower()
        if destination in itin_text:
            checks_passed += 1
        else:
            flags.append(
                f"DESTINATION: '{destination}' not found in itinerary content"
            )
            logger.warning("HALLUCINATION_GUARD: destination '%s' missing from itinerary",
                           destination)

    # ── Check 3: Hotel prices within budget ───────────────────────────────────
    if total_budget > 0 and num_days > 0:
        checks_run += 1
        max_ppn = (total_budget * 0.40) / num_days
        hotel_opts = hotel.get("hotel_options", [])
        bad_prices = [
            o for o in hotel_opts
            if float(o.get("price_per_night", 0) or 0) > max_ppn * 1.15
        ]
        if not bad_prices:
            checks_passed += 1
        else:
            for o in bad_prices:
                flags.append(
                    f"HOTEL_PRICE: {o.get('name','?')} at "
                    f"{currency}{o.get('price_per_night',0):,.0f}/night "
                    f"exceeds max {currency}{max_ppn:,.0f}/night"
                )
            logger.warning("HALLUCINATION_GUARD: %d hotel(s) exceed budget", len(bad_prices))

    # ── Check 4: Budget estimate is non-zero and reasonable ───────────────────
    if total_budget > 0:
        checks_run += 1
        breakdown = budget.get("breakdown", {})
        estimated = float(breakdown.get("estimated_total", 0) or 0)
        if estimated <= 0:
            flags.append("BUDGET: Estimated total is zero — budget agent may have failed")
            logger.warning("HALLUCINATION_GUARD: estimated_total is 0")
        elif estimated > total_budget * 3:
            flags.append(
                f"BUDGET: Estimate {currency}{estimated:,.0f} is 3× the budget "
                f"{currency}{total_budget:,.0f} — likely hallucinated"
            )
            logger.warning("HALLUCINATION_GUARD: estimated cost 3× budget")
        else:
            checks_passed += 1

    # ── Check 5: Itinerary days have required fields ──────────────────────────
    if days:
        checks_run += 1
        required_day_keys = {"day", "morning", "afternoon", "meals", "accommodation"}
        incomplete = [
            d.get("day", "?")
            for d in days
            if not required_day_keys.issubset(d.keys())
        ]
        if not incomplete:
            checks_passed += 1
        else:
            flags.append(f"ITINERARY_FIELDS: Days {incomplete} missing required fields")
            logger.warning("HALLUCINATION_GUARD: %d incomplete days", len(incomplete))

    # ── Check 6: Transport mode realistic for distance ────────────────────────
    live_route = transport.get("live_route", {})
    prim       = transport.get("primary_option", {})
    if live_route and prim:
        checks_run += 1
        dist_km = float(live_route.get("distance_km", 0) or 0)
        mode    = prim.get("mode", "").lower()
        if dist_km > 1000 and mode in ("bus", "car"):
            flags.append(
                f"TRANSPORT: Mode '{mode}' suggested for {dist_km:.0f}km route — "
                f"flight/train would be more realistic"
            )
            logger.warning("HALLUCINATION_GUARD: unrealistic transport mode for distance")
        elif dist_km < 100 and mode == "flight":
            flags.append(
                f"TRANSPORT: Flight suggested for only {dist_km:.0f}km — likely hallucinated"
            )
        else:
            checks_passed += 1

    # ── Score ─────────────────────────────────────────────────────────────────
    score = (checks_passed / checks_run) if checks_run > 0 else 1.0
    passed = len(flags) == 0

    if not passed:
        logger.warning(
            "HALLUCINATION_GUARD: %d issue(s) found, score=%.2f", len(flags), score
        )
    else:
        logger.info("HALLUCINATION_GUARD: all checks passed ✓ score=1.0")

    return {
        "passed":        passed,
        "flags":         flags,
        "score":         round(score, 3),
        "checks_run":    checks_run,
        "checks_passed": checks_passed,
    }


# ═════════════════════════════════════════════════════════════════════════════
# 7. RETRIEVAL GUARD
# ═════════════════════════════════════════════════════════════════════════════

_RETRIEVAL_UNSAFE = re.compile(
    r"\b(bomb|weapon|terrorist|smuggl|illegal\s+drug|trafficking)\b",
    re.IGNORECASE
)
_RETRIEVAL_INJECT = re.compile(
    r"ignore\s+(previous|prior|all)\s+instructions?"
    r"|\[SYSTEM\]|\[INST\]|<\s*system\s*>"
    r"|you\s+are\s+now\s+\w+bot",
    re.IGNORECASE
)

@traceable(name="Guardrail.retrieval_guard", run_type="tool")
def retrieval_guard(docs: list, destination: str = "") -> list:
    """Filter FAISS chunks: removes unsafe content, injections, irrelevant docs."""
    safe_docs  = []
    dest_lower = destination.lower().split(",")[0].strip() if destination else ""
    generic    = {"budget","packing","emergency","visa","tip","checklist",
                  "adventure","general","international"}

    for doc in docs:
        content = doc.get("content","") if isinstance(doc, dict) else str(doc)
        cl      = content.lower()

        if _RETRIEVAL_UNSAFE.search(content):
            logger.warning("RETRIEVAL_GUARD: unsafe chunk removed")
            continue
        if _RETRIEVAL_INJECT.search(content):
            logger.warning("RETRIEVAL_GUARD: injection in chunk removed")
            continue
        if dest_lower:
            if not (dest_lower in cl or any(g in cl for g in generic)):
                continue

        safe_docs.append(doc)

    logger.info("RETRIEVAL_GUARD: %d/%d docs passed", len(safe_docs), len(docs))
    return safe_docs


# ═════════════════════════════════════════════════════════════════════════════
# 8. TOOL GUARD
# ═════════════════════════════════════════════════════════════════════════════

_APPROVED_TOOLS = {
    "fetch_weather","fetch_places","fetch_route_distance",
    "fetch_hotel_prices","geocode_city","fetch_nearby_restaurants",
    "similarity_search","build_index",
}
_MAX_RADIUS_M    = 50_000
_MAX_HOTEL_LIMIT = 20
_INJECT_PARAMS   = re.compile(r"\.\./|;\s*DROP|<script|UNION\s+SELECT", re.IGNORECASE)

@traceable(name="Guardrail.tool_guard", run_type="tool")
def tool_guard(tool_name: str, params: dict) -> GuardrailResult:
    """Validate tool calls: allowlist, bounds, injection detection."""
    if tool_name not in _APPROVED_TOOLS:
        logger.warning("TOOL_GUARD: blocked '%s'", tool_name)
        return GuardrailResult(
            blocked=True,
            reason=f"Tool '{tool_name}' is not approved.",
            clean="", category="tool",
        )
    if "radius_m" in params and params["radius_m"] > _MAX_RADIUS_M:
        params["radius_m"] = _MAX_RADIUS_M
    if "limit" in params and params["limit"] > _MAX_HOTEL_LIMIT:
        params["limit"] = _MAX_HOTEL_LIMIT
    for key, val in params.items():
        if isinstance(val, str) and _INJECT_PARAMS.search(val):
            logger.warning("TOOL_GUARD: injection in param '%s'", key)
            return GuardrailResult(
                blocked=True,
                reason=f"Unsafe value in parameter '{key}'.",
                clean="", category="tool",
            )
    return GuardrailResult(blocked=False, reason="", clean="", category="ok")


# ═════════════════════════════════════════════════════════════════════════════
# 9. RATE LIMITER  — session-level query cooldown
# ═════════════════════════════════════════════════════════════════════════════

# In-memory store: session_id → {"count": int, "window_start": float, "last_call": float}
_rate_store: Dict[str, Dict] = {}

RATE_LIMIT_MAX_QUERIES  = 10    # max planning queries per window
RATE_LIMIT_WINDOW_SECS  = 3600  # 1-hour window
RATE_LIMIT_COOLDOWN_SECS= 30    # min seconds between consecutive queries


def rate_limiter(session_id: str) -> GuardrailResult:
    """
    Enforce per-session rate limits.
    Blocks if:
      - User makes > 10 planning queries in 1 hour
      - User makes consecutive queries faster than 30 seconds apart

    session_id should be st.session_state's unique session identifier.
    """
    now = time.time()
    record = _rate_store.get(session_id, {"count": 0, "window_start": now, "last_call": 0.0})

    # Reset window if expired
    if now - record["window_start"] > RATE_LIMIT_WINDOW_SECS:
        record = {"count": 0, "window_start": now, "last_call": record["last_call"]}

    # Check cooldown between queries
    time_since_last = now - record["last_call"]
    if record["last_call"] > 0 and time_since_last < RATE_LIMIT_COOLDOWN_SECS:
        wait = int(RATE_LIMIT_COOLDOWN_SECS - time_since_last)
        logger.warning("RATE_LIMITER: cooldown active for session %s, %ds remaining", session_id, wait)
        return GuardrailResult(
            blocked=True,
            reason=f"⏳ Please wait {wait} seconds before planning another trip.",
            clean="", category="rate",
        )

    # Check hourly limit
    if record["count"] >= RATE_LIMIT_MAX_QUERIES:
        logger.warning("RATE_LIMITER: hourly limit reached for session %s", session_id)
        return GuardrailResult(
            blocked=True,
            reason=(
                f"⏳ You've planned {RATE_LIMIT_MAX_QUERIES} trips this hour. "
                f"Please try again in a little while."
            ),
            clean="", category="rate",
        )

    # Allow — update record
    record["count"]      += 1
    record["last_call"]   = now
    _rate_store[session_id] = record

    logger.info("RATE_LIMITER: session %s — query %d/%d this hour",
                session_id, record["count"], RATE_LIMIT_MAX_QUERIES)
    return GuardrailResult(blocked=False, reason="", clean="", category="ok")


def get_rate_status(session_id: str) -> Dict[str, Any]:
    """Return current rate limit status for a session (for UI display)."""
    now    = time.time()
    record = _rate_store.get(session_id, {"count": 0, "window_start": now, "last_call": 0.0})
    if now - record["window_start"] > RATE_LIMIT_WINDOW_SECS:
        return {"count": 0, "remaining": RATE_LIMIT_MAX_QUERIES, "cooldown_secs": 0}

    cooldown = max(0.0, RATE_LIMIT_COOLDOWN_SECS - (now - record["last_call"]))
    return {
        "count":         record["count"],
        "remaining":     max(0, RATE_LIMIT_MAX_QUERIES - record["count"]),
        "cooldown_secs": int(cooldown),
    }


# ═════════════════════════════════════════════════════════════════════════════
# MASTER INPUT PIPELINE
# ═════════════════════════════════════════════════════════════════════════════

try:
    from langsmith import traceable
except ImportError:
    def traceable(**kwargs):
        def decorator(fn): return fn
        return decorator

@traceable(name="Guardrails.run_guardrails", run_type="tool")
def run_guardrails(text: str) -> GuardrailResult:
    """
    Run all INPUT guardrails.
    Order: PII masking → Abuse → Hate → Scope
    Returns first blocking result or PII-masked OK.
    Note: Rate limiter, output guard, and hallucination guard
    are called separately by agents/app as needed.
    """
    pii_result = pii_masker(text)
    clean      = pii_result.clean

    for guard in (abuse_guard, hate_guard, scope_guard):
        result = guard(text)
        if result.blocked:
            return result

    return GuardrailResult(
        blocked=False, reason="", clean=clean,
        category=pii_result.category,
    )
