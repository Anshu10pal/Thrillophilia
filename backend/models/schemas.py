"""
backend/models/schemas.py — Pydantic Request/Response Models
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ── Request Models ────────────────────────────────────────────────────────────

class TripPreferences(BaseModel):
    destination:          Optional[str]   = None
    source:               Optional[str]   = None
    num_days:             Optional[int]   = None
    budget:               Optional[float] = None
    currency:             str             = "INR"
    travelers:            Optional[int]   = None
    travel_type:          Optional[str]   = None
    transport_preference: Optional[str]   = None
    hotel_preference:     Optional[str]   = None
    food_preference:      Optional[str]   = None
    interests:            List[str]       = []
    stopovers:            List[str]       = []
    start_date:           Optional[str]   = None
    end_date:             Optional[str]   = None


class PlanRequest(BaseModel):
    query:        str
    preferences:  TripPreferences         = TripPreferences()
    travel_style: str                     = "balanced"
    custom_style: Optional[str]           = None
    session_id:   str                     = "default"


class ClarifyRequest(BaseModel):
    query:     str
    extracted: TripPreferences = TripPreferences()


class AnswerRequest(BaseModel):
    session_id: str
    field:      str
    answer:     str


class AddCityRequest(BaseModel):
    job_id:   str
    city:     str
    num_days: int = 2


# ── Response Models ───────────────────────────────────────────────────────────

class PlanResponse(BaseModel):
    job_id:  str
    status:  str = "queued"


class ClarifyQuestion(BaseModel):
    field:    str
    question: str


class ClarifyResponse(BaseModel):
    missing_fields: List[str]
    questions:      List[ClarifyQuestion]
    show_popup:     bool
    extracted:      TripPreferences


class NearbyCityItem(BaseModel):
    name:        str
    distance_km: float
    drive_hours: float
    description: str
    style_match: List[str] = []
    emoji:       str       = "📍"


class NearbyResponse(BaseModel):
    city:        str
    sub_regions: List[str]
    nearby:      List[NearbyCityItem]
    auto_split:  bool


class TravelStyle(BaseModel):
    id:          str
    label:       str
    emoji:       str
    description: str
    color:       str


class StylesResponse(BaseModel):
    styles: List[TravelStyle]


class PlanSummary(BaseModel):
    plan_id:       str
    destination:   str
    source:        str
    num_days:      int
    budget:        float
    currency:      str
    travel_style:  str
    trip_title:    str
    grade:         str
    overall_score: int
    created_at:    str
    thumbnail_emoji: str
    thumbnail_img: Optional[str] = None


class RecentPlansResponse(BaseModel):
    plans: List[PlanSummary]


class StreamEvent(BaseModel):
    event:   str
    agent:   Optional[str]  = None
    message: Optional[str]  = None
    detail:  Optional[Dict[str, Any]] = None
    job_id:  Optional[str]  = None
    cities:  Optional[List[NearbyCityItem]] = None
