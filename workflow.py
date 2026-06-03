"""
workflow.py — LangGraph Multi-Agent Trip Planner Workflow
=========================================================

Graph Topology:
  START
    └─► orchestrator_agent          (decides routing)
          ├─► parallel_agents       (weather, transport, hotel, places, budget, itinerary)
          │     └─► final_review_agent
          │           └─► orchestrator_agent  (loop back)
          ├─► hotel_agent           (retry on budget overrun)
          ├─► transport_agent       (retry on transport failure)
          └─► pdf_generator
                └─► format_response
                      └─► END

State is TripState (TypedDict) — all agents read/write to it.
LangGraph handles merging partial state updates automatically.
"""

import logging
from typing import Any, Dict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from state import TripState

from config import validate_config, logger
try:
    from langsmith import traceable
except ImportError:
    def traceable(**kwargs):
        def decorator(fn): return fn
        return decorator

# ── Agent imports ─────────────────────────────────────────────────────────────
from agents.agents import (
    user_input_agent,
    memory_agent,
    weather_agent,
    transport_agent,
    hotel_agent,
    places_agent,
    budget_agent,
    itinerary_agent,
    final_review_agent,
    memory_update_agent,
)
from agents.orchestrator import (
    orchestrator_agent,
    format_final_response,
    route_after_orchestrator,
)
from tools.pdf_generator import generate_pdf


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSITE NODES (run multiple agents sequentially as one graph node)
# ─────────────────────────────────────────────────────────────────────────────

def initial_processing_node(state: TripState) -> Dict[str, Any]:
    """Node 1: Parse user input then retrieve memory/knowledge."""
    logger.info("=== Node: initial_processing ===")
    s = {**state}
    s.update(user_input_agent(s))
    s.update(memory_agent(s))
    return {k: s[k] for k in s if k in TripState.__annotations__}


def parallel_agents_node(state: TripState) -> Dict[str, Any]:
    """
    Node 2: Run all data-gathering agents.
    In production these would run in true parallel (asyncio / threads).
    Here they run sequentially for clarity and debuggability.
    """
    logger.info("=== Node: parallel_agents ===")
    s = {**state}
    for agent_fn in [weather_agent, transport_agent, hotel_agent,
                     places_agent, budget_agent, itinerary_agent]:
        try:
            result = agent_fn(s)
            s.update(result)
        except Exception as e:
            errors = s.get("errors", [])
            errors.append(f"{agent_fn.__name__}: {str(e)}")
            s["errors"] = errors
            logger.error("[%s] Error: %s", agent_fn.__name__, e)
    return {k: s[k] for k in s if k in TripState.__annotations__}


def review_node(state: TripState) -> Dict[str, Any]:
    """Node 3: Final review agent validates the complete plan."""
    logger.info("=== Node: review ===")
    return final_review_agent(state)


def hotel_retry_node(state: TripState) -> Dict[str, Any]:
    """
    Node: Retry hotel + budget agents when budget is exceeded.
    Adjusts luxury_budget preference before retry.
    """
    logger.info("=== Node: hotel_retry ===")
    s = {**state}
    # Downgrade luxury setting to find cheaper hotels
    prefs = s.get("trip_preferences", {})
    luxury_map = {"luxury": "mid-range", "mid-range": "budget", "budget": "budget"}
    prefs["luxury_budget"] = luxury_map.get(prefs.get("luxury_budget", "mid-range"), "budget")
    s["trip_preferences"] = prefs
    s.update(hotel_agent(s))
    s.update(budget_agent(s))
    return {k: s[k] for k in s if k in TripState.__annotations__}


def transport_retry_node(state: TripState) -> Dict[str, Any]:
    """Node: Retry transport agent with alternative transport mode."""
    logger.info("=== Node: transport_retry ===")
    s = {**state}
    prefs = s.get("trip_preferences", {})
    # Switch transport preference to alternative
    alt_map = {"flight": "train", "train": "bus", "bus": "car", "car": "bus"}
    prefs["transport_preference"] = alt_map.get(prefs.get("transport_preference", "flight"), "train")
    s["trip_preferences"] = prefs
    s.update(transport_agent(s))
    return {k: s[k] for k in s if k in TripState.__annotations__}


def pdf_node(state: TripState) -> Dict[str, Any]:
    """Node: Generate PDF report, then update memory."""
    logger.info("=== Node: pdf_generator ===")
    s = {**state}
    s.update(generate_pdf(s))
    s.update(memory_update_agent(s))
    return {k: s[k] for k in s if k in TripState.__annotations__}


def format_response_node(state: TripState) -> Dict[str, Any]:
    """Node: Compile human-readable final response."""
    logger.info("=== Node: format_response ===")
    return format_final_response(state)


# ─────────────────────────────────────────────────────────────────────────────
# CONDITIONAL EDGE
# ─────────────────────────────────────────────────────────────────────────────

def orchestrator_router(state: TripState) -> str:
    """
    Maps orchestrator_decision.next_step → graph node name.
    Called by LangGraph as a conditional edge after orchestrator_agent.
    """
    return route_after_orchestrator(state)


# ─────────────────────────────────────────────────────────────────────────────
# BUILD GRAPH
# ─────────────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Construct and compile the LangGraph StateGraph.

    Graph edges:
      START → initial_processing
      initial_processing → orchestrator_agent
      orchestrator_agent --[conditional]--> parallel_agents | hotel_agent | transport_agent | pdf_generator
      parallel_agents → review → orchestrator_agent  (loop)
      hotel_agent → review → orchestrator_agent
      transport_agent → review → orchestrator_agent
      pdf_generator → format_response → END
    """
    graph = StateGraph(TripState)

    # ── Add nodes ─────────────────────────────────────────────────────────────
    graph.add_node("initial_processing", initial_processing_node)
    graph.add_node("orchestrator_agent", orchestrator_agent)
    graph.add_node("parallel_agents", parallel_agents_node)
    graph.add_node("review", review_node)
    graph.add_node("hotel_agent", hotel_retry_node)
    graph.add_node("transport_agent", transport_retry_node)
    graph.add_node("pdf_generator", pdf_node)
    graph.add_node("format_response", format_response_node)

    # ── Entry point ───────────────────────────────────────────────────────────
    graph.set_entry_point("initial_processing")

    # ── Linear edges ──────────────────────────────────────────────────────────
    graph.add_edge("initial_processing", "orchestrator_agent")

    # ── Conditional edge from orchestrator ────────────────────────────────────
    graph.add_conditional_edges(
        "orchestrator_agent",
        orchestrator_router,
        {
            "parallel_agents": "parallel_agents",
            "hotel_agent": "hotel_agent",
            "transport_agent": "transport_agent",
            "pdf_generator": "pdf_generator",
            "format_response": "format_response",
        },
    )

    # ── Agents loop back through review → orchestrator ────────────────────────
    graph.add_edge("parallel_agents", "review")
    graph.add_edge("hotel_agent", "review")
    graph.add_edge("transport_agent", "review")
    graph.add_edge("review", "orchestrator_agent")

    # ── Terminal path ─────────────────────────────────────────────────────────
    graph.add_edge("pdf_generator", "format_response")
    graph.add_edge("format_response", END)

    return graph


# ─────────────────────────────────────────────────────────────────────────────
# TRIP PLANNER CLASS
# ─────────────────────────────────────────────────────────────────────────────
from langsmith import traceable


class TripPlanner:
      
    """
    High-level interface to the multi-agent trip planning system.

    Usage:
        planner = TripPlanner()
        result = planner.plan("Plan a 5-day Goa trip from Bangalore, budget ₹30,000")
        print(result["final_response"])
    """
    @traceable(
        name="TripPlanner.plan",
        run_type="chain",
        tags=["production"],
    )
    def __init__(self):
        validate_config()
        checkpointer = MemorySaver()
        graph = build_graph()
        self.app = graph.compile(checkpointer=checkpointer)
        self.thread_id = "trip_001"
        self.conversation_history = []
        logger.info("TripPlanner initialised ✓")

    def _initial_state(self, query: str) -> TripState:
        """Build the initial TripState for a new query."""
        from langchain_core.messages import HumanMessage as LCHuman

        self.conversation_history.append({"role": "user", "content": query})

        return TripState(
            messages=[LCHuman(content=query)],
            user_query=query,
            conversation_history=self.conversation_history.copy(),
            user_profile={},
            trip_preferences={},
            weather_data={},
            hotel_data={},
            transport_data={},
            places_data={},
            budget_summary={},
            itinerary={},
            review_status={},
            memory_context={},
            retrieved_docs=[],
            orchestrator_decision={},
            current_agent="",
            retry_count={},
            errors=[],
            iteration=0,
            final_response="",
            pdf_status={},
            pdf_path=None,
        )

    @traceable(
        name="TripPlanner.plan",
        run_type="chain",
        tags=["production"],
        metadata={"version": "v16"}
    )
    def plan(self, query: str, thread_id: str = None) -> Dict[str, Any]:
        """
        Run the full multi-agent trip planning workflow.

        Args:
            query: Natural language trip planning request.
            thread_id: Optional session ID for conversation persistence.

        Returns:
            Final TripState dict with all agent outputs + final_response + pdf_path.
        """
        tid = thread_id or self.thread_id
        initial = self._initial_state(query)
        config = {"configurable": {"thread_id": tid}}

        logger.info("Starting trip planning for: %s", query[:80])

        final_state = None
        for event in self.app.stream(initial, config=config, stream_mode="values"):
            final_state = event
            agent = event.get("current_agent", "")
            if agent:
                logger.info("  ✓ %s completed", agent)

        if final_state and final_state.get("final_response"):
            self.conversation_history.append({
                "role": "assistant",
                "content": final_state["final_response"][:500],
            })
        
        return final_state or {}
    
    @traceable(
            name="TripPlanner.refine",
            run_type="chain",
            tags=["production", "refine"]
        )
    def refine(self, query: str) -> Dict[str, Any]:
        """
        Refine an existing trip plan based on user feedback.
        Preserves conversation history for multi-turn dialogue.
        """
        logger.info("Refining trip with: %s", query[:80])
        return self.plan(query)

    def get_pdf_path(self, result: Dict[str, Any]) -> str:
        """Extract PDF file path from result."""
        return result.get("pdf_path", "")
