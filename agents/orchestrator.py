"""
agents/orchestrator.py — Orchestrator / Supervisor Agent
=========================================================
The Orchestrator is the "brain" of the multi-agent system.

Responsibilities:
  ● Understand user goal and missing information
  ● Route the workflow to the correct next node
  ● Detect and resolve conflicts (budget overrun, weather clash, etc.)
  ● Decide when to retry failed agents (up to MAX_RETRY_PER_AGENT)
  ● Give final approval before PDF generation
  ● Compile the human-readable final response

LangGraph calls the orchestrator after each batch of agents to decide
what happens next (returned as the "next" node name string).
"""

import json
import logging
from typing import Any, Dict, Literal

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import OPENAI_API_KEY, LLM_MODEL, LLM_TEMPERATURE, MAX_RETRY_PER_AGENT, MAX_ORCHESTRATOR_ITERATIONS
from state import TripState

logger = logging.getLogger("trip_planner.orchestrator")


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=LLM_MODEL,
        temperature=0.1,           # Low temp for deterministic routing
        max_tokens=500,
        openai_api_key=OPENAI_API_KEY,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ORCHESTRATOR DECISION NODE
# ─────────────────────────────────────────────────────────────────────────────

def orchestrator_agent(state: TripState) -> Dict[str, Any]:
    """
    Analyse current state and decide the next step.
    Sets orchestrator_decision dict which the conditional edge reads.

    Decision keys:
      next_step: "run_agents" | "retry_hotel" | "retry_transport" | 
                 "retry_budget" | "generate_pdf" | "respond"
      approved: bool
      conflicts: list[str]
      iteration: int
    """
    iteration = state.get("iteration", 0) + 1
    logger.info("[Orchestrator] Iteration %d", iteration)

    prefs = state.get("trip_preferences", {})
    review = state.get("review_status", {})
    budget_data = state.get("budget_summary", {})
    retry_count = state.get("retry_count", {})
    errors = state.get("errors", [])

    # ── Safety: prevent infinite loops ───────────────────────────────────────
    if iteration > MAX_ORCHESTRATOR_ITERATIONS:
        logger.warning("[Orchestrator] Max iterations reached, forcing PDF generation")
        return {
            "orchestrator_decision": {
                "next_step": "generate_pdf",
                "approved": True,
                "conflicts": ["Max iterations reached"],
                "iteration": iteration,
                "reason": "Safety limit reached",
            },
            "iteration": iteration,
        }

    # ── First iteration: gather all data ─────────────────────────────────────
    if iteration == 1:
        return {
            "orchestrator_decision": {
                "next_step": "run_agents",
                "approved": False,
                "conflicts": [],
                "iteration": iteration,
                "reason": "Initial data gathering",
            },
            "iteration": iteration,
        }

    # ── Check for conflicts from Final Review Agent ───────────────────────────
    conflicts = review.get("conflicts", [])
    approved = review.get("approved", False)

    # ── Budget overrun → retry hotel agent ───────────────────────────────────
    if any("budget" in c.lower() for c in conflicts):
        hotel_retries = retry_count.get("hotel_agent", 0)
        if hotel_retries < MAX_RETRY_PER_AGENT:
            logger.info("[Orchestrator] Budget conflict → retry Hotel Agent")
            return {
                "orchestrator_decision": {
                    "next_step": "retry_hotel",
                    "approved": False,
                    "conflicts": conflicts,
                    "iteration": iteration,
                    "reason": "Budget overrun detected, requesting cheaper hotel options",
                },
                "retry_count": {**retry_count, "hotel_agent": hotel_retries + 1},
                "iteration": iteration,
            }

    # ── Transport failure → retry transport agent ─────────────────────────────
    if any("transport" in c.lower() for c in conflicts):
        transport_retries = retry_count.get("transport_agent", 0)
        if transport_retries < MAX_RETRY_PER_AGENT:
            logger.info("[Orchestrator] Transport conflict → retry Transport Agent")
            return {
                "orchestrator_decision": {
                    "next_step": "retry_transport",
                    "approved": False,
                    "conflicts": conflicts,
                    "iteration": iteration,
                    "reason": "Transport issue detected, finding alternatives",
                },
                "retry_count": {**retry_count, "transport_agent": transport_retries + 1},
                "iteration": iteration,
            }

    # ── If all checks pass → generate PDF ────────────────────────────────────
    if approved or iteration >= 3:
        logger.info("[Orchestrator] Plan approved → triggering PDF generation")
        return {
            "orchestrator_decision": {
                "next_step": "generate_pdf",
                "approved": True,
                "conflicts": conflicts,
                "iteration": iteration,
                "reason": "Plan validated and approved",
            },
            "iteration": iteration,
        }

    # ── Default: re-run agents with adjusted parameters ──────────────────────
    return {
        "orchestrator_decision": {
            "next_step": "run_agents",
            "approved": False,
            "conflicts": conflicts,
            "iteration": iteration,
            "reason": "Gathering additional data",
        },
        "iteration": iteration,
    }


# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE FORMATTER
# ─────────────────────────────────────────────────────────────────────────────

def format_final_response(state: TripState) -> Dict[str, Any]:
    """
    Compile all agent outputs into a polished human-readable response.
    This is shown to the user in the chat interface.
    """
    logger.info("[Orchestrator] Formatting final response…")

    prefs = state.get("trip_preferences", {})
    weather = state.get("weather_data", {})
    transport = state.get("transport_data", {})
    hotel = state.get("hotel_data", {})
    places = state.get("places_data", {})
    budget = state.get("budget_summary", {})
    itinerary = state.get("itinerary", {})
    review = state.get("review_status", {})
    pdf_path = state.get("pdf_path", "")

    dest = prefs.get("destination", "your destination")
    days = prefs.get("num_days", 5)
    currency = prefs.get("currency", "INR")
    total_budget = prefs.get("budget", 0)

    # Build structured response
    lines = [
        f"# 🗺️ {itinerary.get('trip_title', f'{days}-Day {dest} Trip Plan')}",
        "",
        "---",
        "",
        "## 🌤️ Weather",
        f"**{weather.get('conditions', 'Good').title()}** | Day: {weather.get('avg_temp_day', 'N/A')} | Night: {weather.get('avg_temp_night', 'N/A')}",
        weather.get("weather_summary", ""),
        "",
        "## ✈️ Transport",
    ]

    primary = transport.get("primary_option", {})
    if primary:
        lines += [
            f"**{primary.get('mode','').title()}** via {primary.get('operator', 'N/A')} | "
            f"Duration: {primary.get('duration','N/A')} | "
            f"Cost: {currency}{primary.get('total_price', 0):,}",
        ]
    local_t = transport.get("local_transport", {})
    if local_t:
        lines.append(f"Local: {local_t.get('recommended','taxi')} (~{currency}{local_t.get('daily_cost',0):,}/day)")

    lines += ["", "## 🏨 Accommodation"]
    rec_hotel = hotel.get("recommended_hotel", {})
    if rec_hotel:
        lines += [
            f"**{rec_hotel.get('name','N/A')}** ({rec_hotel.get('category','N/A')}) ⭐{rec_hotel.get('rating','N/A')}",
            f"📍 {rec_hotel.get('location','N/A')} | {currency}{rec_hotel.get('price_per_night',0):,}/night | "
            f"Total: {currency}{rec_hotel.get('total_cost',0):,}",
            f"*{rec_hotel.get('why_recommended','')}*",
        ]

    lines += ["", "## 🎯 Top Attractions"]
    for att in places.get("top_attractions", [])[:5]:
        lines.append(f"• **{att.get('name','')}** — {att.get('type','')} | ⏱ {att.get('duration','')} | ⭐{att.get('rating','')}")

    lines += ["", "## 🍽️ Recommended Restaurants"]
    for rest in places.get("restaurants", [])[:4]:
        lines.append(f"• **{rest.get('name','')}** ({rest.get('cuisine','')}) | ~{currency}{rest.get('avg_cost_per_person',0):,}/person | Try: {rest.get('must_try_dish','')}")

    lines += ["", "## 📅 Day-Wise Itinerary"]
    for day in itinerary.get("days", [])[:days]:
        d = day.get("day", 0)
        theme = day.get("theme", "")
        lines.append(f"**Day {d}: {theme}**")
        for period in ["morning", "afternoon", "evening"]:
            block = day.get(period, {})
            if block:
                lines.append(f"  🕐 {period.title()}: {block.get('activity','')} @ {block.get('location','')}")
        meals = day.get("meals", {})
        if meals:
            lines.append(f"  🍴 {meals.get('lunch','')} / {meals.get('dinner','')}")
        lines.append("")

    lines += ["## 💰 Budget Summary"]
    breakdown = budget.get("breakdown", {})
    if breakdown:
        lines += [
            f"| Category | Cost |",
            f"|----------|------|",
            f"| ✈️ Transport | {currency}{breakdown.get('transport',0):,.0f} |",
            f"| 🏨 Accommodation | {currency}{breakdown.get('accommodation',0):,.0f} |",
            f"| 🍽️ Food | {currency}{breakdown.get('food',0):,.0f} |",
            f"| 🎯 Activities | {currency}{breakdown.get('activities',0):,.0f} |",
            f"| 🛍️ Miscellaneous | {currency}{breakdown.get('miscellaneous',0):,.0f} |",
            f"| **TOTAL** | **{currency}{breakdown.get('estimated_total',0):,.0f}** |",
            f"| Budget | {currency}{total_budget:,} |",
        ]
        surplus = budget.get("surplus_or_deficit", 0)
        status_emoji = "✅" if surplus >= 0 else "⚠️"
        lines.append(f"{status_emoji} **{budget.get('budget_status','on_track').replace('_',' ').title()}** | Surplus/Deficit: {currency}{surplus:,.0f}")

    if budget.get("optimization_tips"):
        lines += ["", "**💡 Budget Tips:**"]
        for tip in budget["optimization_tips"][:3]:
            lines.append(f"• {tip}")

    # Warnings
    if review.get("warnings"):
        lines += ["", "⚠️ **Notes:**"]
        for w in review["warnings"]:
            lines.append(f"• {w}")

    if pdf_path:
        lines += ["", "---", f"📄 **Your detailed PDF report has been generated!** Download it to get the complete itinerary with all details."]

    response = "\n".join(lines)

    return {
        "final_response": response,
        "current_agent": "orchestrator_formatter",
    }


# ─────────────────────────────────────────────────────────────────────────────
# CONDITIONAL EDGE ROUTER
# ─────────────────────────────────────────────────────────────────────────────

def route_after_orchestrator(state: TripState) -> str:
    """
    LangGraph conditional edge function.
    Reads orchestrator_decision.next_step and returns the node name to go to.
    """
    decision = state.get("orchestrator_decision", {})
    next_step = decision.get("next_step", "run_agents")

    routing_map = {
        "run_agents": "parallel_agents",
        "retry_hotel": "hotel_agent",
        "retry_transport": "transport_agent",
        "retry_budget": "budget_agent",
        "generate_pdf": "pdf_generator",
        "respond": "format_response",
    }
    next_node = routing_map.get(next_step, "parallel_agents")
    logger.info("[Orchestrator Router] next_step=%s → node=%s", next_step, next_node)
    return next_node
