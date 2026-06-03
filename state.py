"""
state.py — Extended TripState with clarification + hotel selection support
"""
from typing import TypedDict, Annotated, Optional, List, Dict, Any
from langgraph.graph.message import add_messages


class TripState(TypedDict):
    # ── Conversation ──────────────────────────────────────────────────────
    messages: Annotated[list, add_messages]
    user_query: str
    conversation_history: List[Dict[str, str]]

    # ── Clarification flow ────────────────────────────────────────────────
    # "clarifying" | "ready" | "selecting_hotels" | "complete"
    flow_stage: str
    missing_fields: List[str]          # fields still needed
    clarification_question: str        # question to show user next
    clarification_answers: Dict[str, str]  # field -> answer collected so far

    # ── Preferences ───────────────────────────────────────────────────────
    user_profile: Dict[str, Any]
    trip_preferences: Dict[str, Any]

    # ── Hotel selection per location ───────────────────────────────────────
    # { "Barcelona": [option0, option1, option2] }
    hotel_options_by_location: Dict[str, List[Dict]]
    # { "Barcelona": 1 }  — index of chosen option
    hotel_selections: Dict[str, int]
    # list of locations in itinerary order
    itinerary_locations: List[str]
    # which location index we are currently picking hotel for
    hotel_selection_step: int

    # ── Agent Outputs ─────────────────────────────────────────────────────
    weather_data: Dict[str, Any]
    hotel_data: Dict[str, Any]
    transport_data: Dict[str, Any]
    places_data: Dict[str, Any]
    budget_summary: Dict[str, Any]
    itinerary: Dict[str, Any]
    review_status: Dict[str, Any]
    memory_context: Dict[str, Any]
    retrieved_docs: List[Dict[str, Any]]

    # ── Orchestrator ──────────────────────────────────────────────────────
    orchestrator_decision: Dict[str, Any]
    current_agent: str
    retry_count: Dict[str, int]
    errors: List[str]
    iteration: int

    # ── Output ────────────────────────────────────────────────────────────
    final_response: str
    pdf_status: Dict[str, Any]
    pdf_path: Optional[str]
