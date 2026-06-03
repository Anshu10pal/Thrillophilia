"""
backend/services/planning_service.py — Planning Orchestration
=============================================================
Wraps the existing workflow.py TripPlanner with:
  - Redis cache checks at each layer
  - SSE event emission during planning
  - Travel style injection into agents
  - Sub-region and nearby city logic
  - Job state management
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from services.cache_service import cache
from services.nearby_service import get_sub_regions, should_auto_split
from services.style_service import get_style_config, interpret_custom_style

logger = logging.getLogger("thrillophilia.planning")

AGENT_MESSAGES = {
    "user_input_agent":    ("🔍", "Parsing your trip details…"),
    "memory_agent":        ("🧠", "Retrieving travel knowledge…"),
    "weather_agent":       ("🌤️", "Checking weather…"),
    "transport_agent":     ("✈️",  "Finding transport options…"),
    "hotel_agent":         ("🏨", "Searching hotels within budget…"),
    "places_agent":        ("📍", "Discovering attractions & restaurants…"),
    "budget_agent":        ("💰", "Calculating budget breakdown…"),
    "itinerary_agent":     ("📅", "Building your personalised itinerary…"),
    "final_review_agent":  ("✅", "Reviewing your plan…"),
    "memory_update_agent": ("💾", "Saving your preferences…"),
}


def _make_job_id() -> str:
    return f"plan_{uuid.uuid4().hex[:8]}"


def _get_month(prefs: Dict) -> Optional[str]:
    start = prefs.get("start_date", "")
    if start and len(start) >= 7:
        return start[:7]
    return None


async def _emit(job_id: str, event: str, **kwargs) -> Dict:
    ev = {"event": event, "job_id": job_id, **kwargs}
    await cache.append_job_event(job_id, ev)
    return ev


async def run_planning_job(job_id: str, request_data: Dict):
    """
    Background task: runs full planning pipeline with cache + SSE events.
    Called via asyncio.create_task from the /plan endpoint.
    """
    logger.info("[Job %s] Starting planning", job_id)
    await cache.set_job_status(job_id, {"status": "running", "progress": 0})

    try:
        prefs       = request_data.get("preferences", {})
        style_id    = request_data.get("travel_style", "balanced")
        custom_style= request_data.get("custom_style")
        session_id  = request_data.get("session_id", "default")
        query       = request_data.get("query", "")

        dest    = prefs.get("destination", "")
        src     = prefs.get("source", "")
        days    = prefs.get("num_days", 5) or 5
        budget  = prefs.get("budget", 50000) or 50000
        currency= prefs.get("currency", "INR")
        month   = _get_month(prefs)

        # ── Interpret custom travel style ──────────────────────────────────
        if style_id == "other" and custom_style:
            await _emit(job_id, "status", message=f"✨ Interpreting your travel style: {custom_style}")
            style_config = await interpret_custom_style(custom_style)
        else:
            style_config = get_style_config(style_id)

        await _emit(job_id, "status",
                    message=f"🎯 Style: {style_config.get('label','Custom')} — {style_config.get('tone','')}")

        # ── Check full plan cache ──────────────────────────────────────────
        if month and dest and src:
            cached_plan = await cache.get_plan(dest, src, days, budget, currency, style_id, month)
            if cached_plan:
                logger.info("[Job %s] Full plan cache HIT", job_id)
                await _emit(job_id, "cache_hit", message="⚡ Found a matching plan in cache!")
                await _save_and_complete(job_id, session_id, cached_plan, prefs, style_id, dest, days)
                return

        # ── Sub-region splitting ──────────────────────────────────────────
        stopovers = prefs.get("stopovers", [])
        if not stopovers and dest:
            if should_auto_split(dest, days):
                sub_regions = get_sub_regions(dest)
                if sub_regions:
                    prefs["stopovers"] = sub_regions
                    await _emit(job_id, "sub_regions",
                                message=f"🗺️ Splitting across {', '.join(sub_regions)}",
                                detail={"sub_regions": sub_regions})

        # ── Inject style config into preferences ──────────────────────────
        prefs["interests"]        = list(set(
            prefs.get("interests", []) + style_config.get("interests", [])
        ))
        prefs["hotel_preference"] = prefs.get("hotel_preference") or style_config.get("hotel_preference", "hotel")
        prefs["travel_style"]     = style_id
        prefs["style_tone"]       = style_config.get("itinerary_tone", "")
        prefs["budget_split"]     = style_config.get("budget_split", {})

        # ── Build full query string for the planner ────────────────────────
        full_query = _build_query(query, prefs)

        # ── Run agents with SSE events ────────────────────────────────────
        await _emit(job_id, "status", message="🚀 AI agents starting…", progress=5)
        result = await _run_agents_with_events(job_id, full_query, prefs, style_config)

        if not result:
            raise RuntimeError("Planning returned empty result")

        # ── Store in cache ────────────────────────────────────────────────
        if month and dest and src:
            await cache.set_plan(dest, src, days, budget, currency, style_id, month, result)

        await _save_and_complete(job_id, session_id, result, prefs, style_id, dest, days)

    except Exception as e:
        logger.error("[Job %s] Planning failed: %s", job_id, e, exc_info=True)
        await _emit(job_id, "error", message=f"Planning failed: {str(e)}")
        await cache.set_job_status(job_id, {"status": "failed", "error": str(e)})


async def _run_agents_with_events(
    job_id: str, query: str, prefs: Dict, style_config: Dict
) -> Optional[Dict]:
    """Run TripPlanner in a thread, emitting SSE events as agents complete."""
    import concurrent.futures

    loop     = asyncio.get_event_loop()
    result   = {}
    progress = 10

    def on_agent_complete(agent_name: str, agent_result: Dict):
        """Called synchronously from worker thread — schedules async emit."""
        emoji, msg = AGENT_MESSAGES.get(agent_name, ("⚙️", f"{agent_name} done"))
        detail = _extract_agent_detail(agent_name, agent_result)
        asyncio.run_coroutine_threadsafe(
            _emit(job_id, "agent_done",
                  agent=agent_name,
                  message=f"{emoji} {_get_completion_message(agent_name, agent_result)}",
                  detail=detail),
            loop
        )

    def run_planner():
        """Runs in thread pool — calls existing workflow."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from workflow import TripPlanner

        class InstrumentedPlanner(TripPlanner):
            def plan(self, query, thread_id=None):
                import logging as _log
                _log = _log.getLogger("thrillophilia.planning")
                # Run parent plan but intercept agent completions
                from langchain_core.messages import HumanMessage as LCHuman
                initial = self._initial_state(query)
                # Inject enriched preferences
                initial["trip_preferences"] = {**initial.get("trip_preferences", {}), **prefs}
                config = {"configurable": {"thread_id": thread_id or self.thread_id}}
                final_state = None
                for event in self.app.stream(initial, config=config, stream_mode="values"):
                    final_state = event
                    agent = event.get("current_agent", "")
                    if agent:
                        on_agent_complete(agent, event)
                return final_state or {}

        planner = InstrumentedPlanner()
        return planner.plan(query)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_planner)
        while not future.done():
            await asyncio.sleep(0.5)
        result = future.result()

    return result


def _get_completion_message(agent_name: str, state: Dict) -> str:
    """Generate human-readable completion message per agent."""
    if agent_name == "weather_agent":
        w = state.get("weather_data", {})
        cond = w.get("conditions", "")
        temp = w.get("avg_temp_day", "")
        dest = state.get("trip_preferences", {}).get("destination", "")
        return f"{dest}: {cond}, {temp}" if cond else "Weather data fetched"

    if agent_name == "transport_agent":
        t = state.get("transport_data", {})
        prim = t.get("primary_option", {})
        mode = prim.get("mode", "")
        dur  = prim.get("duration", "")
        cur  = state.get("trip_preferences", {}).get("currency", "INR")
        price= prim.get("price_per_person", 0)
        return f"{mode.title()} • {dur} • {cur} {price:,.0f}/person" if mode else "Transport options found"

    if agent_name == "hotel_agent":
        h    = state.get("hotel_data", {})
        opts = h.get("hotel_options", [])
        return f"{len(opts)} hotel options found within budget"

    if agent_name == "places_agent":
        p    = state.get("places_data", {})
        att  = len(p.get("top_attractions", []))
        rest = len(p.get("restaurants", []))
        return f"{att} attractions & {rest} restaurants discovered"

    if agent_name == "budget_agent":
        b   = state.get("budget_summary", {})
        cur = state.get("trip_preferences", {}).get("currency", "INR")
        est = b.get("breakdown", {}).get("estimated_total", 0)
        return f"Estimated total: {cur} {est:,.0f}"

    if agent_name == "itinerary_agent":
        days = len(state.get("itinerary", {}).get("days", []))
        return f"{days}-day itinerary created"

    if agent_name == "final_review_agent":
        r       = state.get("review_status", {})
        approved= r.get("approved", False)
        return "Plan approved ✓" if approved else "Plan reviewed with suggestions"

    return AGENT_MESSAGES.get(agent_name, ("", "Done"))[1]


def _extract_agent_detail(agent_name: str, state: Dict) -> Dict:
    """Extract key data from agent result for SSE detail field."""
    if agent_name == "weather_agent":
        w = state.get("weather_data", {})
        return {k: w.get(k) for k in ["conditions","avg_temp_day","avg_temp_night","rainfall"] if w.get(k)}
    if agent_name == "transport_agent":
        t    = state.get("transport_data", {})
        prim = t.get("primary_option", {})
        return {"mode": prim.get("mode"), "duration": prim.get("duration"), "price": prim.get("price_per_person")}
    if agent_name == "budget_agent":
        return state.get("budget_summary", {}).get("breakdown", {})
    return {}


def _build_query(original: str, prefs: Dict) -> str:
    """Build a rich query string from preferences for the planner."""
    parts = []
    if prefs.get("num_days"):  parts.append(f"{prefs['num_days']}-day")
    if prefs.get("destination"): parts.append(f"trip to {prefs['destination']}")
    if prefs.get("stopovers"):   parts.append(f"via {', '.join(prefs['stopovers'])}")
    if prefs.get("source"):      parts.append(f"from {prefs['source']}")
    if prefs.get("travelers"):   parts.append(f"for {prefs['travelers']} travellers")
    if prefs.get("budget"):
        cur = prefs.get("currency", "INR")
        parts.append(f"budget {cur}{prefs['budget']}")
    if prefs.get("travel_type"): parts.append(prefs["travel_type"])
    if prefs.get("style_tone"):  parts.append(prefs["style_tone"])
    return " ".join(parts) if parts else original


async def _save_and_complete(
    job_id: str, session_id: str, result: Dict,
    prefs: Dict, style_id: str, dest: str, days: int
):
    """Save result, store metadata, emit nearby prompt, mark complete."""
    # Save full result
    await cache.set_plan_result(job_id, result)

    # Save plan metadata for recent plans display
    itin  = result.get("itinerary", {})
    eval_r= result.get("evaluation", {})
    meta  = {
        "plan_id":       job_id,
        "destination":   dest,
        "source":        prefs.get("source", ""),
        "num_days":      days,
        "budget":        prefs.get("budget", 0),
        "currency":      prefs.get("currency", "INR"),
        "travel_style":  style_id,
        "trip_title":    itin.get("trip_title", f"{days}-Day Trip to {dest}"),
        "grade":         eval_r.get("grade", "B"),
        "overall_score": eval_r.get("overall_pct", 75),
        "created_at":    datetime.now().isoformat(),
        "thumbnail_emoji": _dest_emoji(dest),
    }
    await cache.set_plan_meta(job_id, meta)
    await cache.add_recent_plan(session_id, job_id)

    # Emit completion
    await _emit(job_id, "complete",
                message="🎉 Your trip plan is ready!")

    # Emit nearby city suggestions
    from services.nearby_service import get_nearby_cities
    nearby = get_nearby_cities(dest, style_id)
    if nearby:
        await _emit(job_id, "nearby_prompt",
                    message="Want to explore nearby destinations?",
                    cities=[n.__dict__ if hasattr(n, "__dict__") else n for n in nearby[:3]])

    await cache.set_job_status(job_id, {"status": "complete", "progress": 100})
    logger.info("[Job %s] Planning complete", job_id)


def _dest_emoji(dest: str) -> str:
    emoji_map = {
        "goa": "🏖️", "kerala": "🌴", "rajasthan": "🏰", "manali": "🏔️",
        "andaman": "🐚", "darjeeling": "🍵", "ladakh": "🗻", "leh": "🗻",
        "rishikesh": "🕉️", "coorg": "☕", "udaipur": "🛶", "varanasi": "🪔",
        "mumbai": "🌆", "delhi": "🏛️", "bali": "🌺", "dubai": "🏙️",
        "thailand": "🐘", "maldives": "🐠", "paris": "🗼", "singapore": "🦁",
        "japan": "⛩️", "london": "🎡", "new york": "🗽",
    }
    return emoji_map.get(dest.lower().strip(), "✈️")
