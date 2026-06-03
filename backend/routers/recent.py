"""backend/routers/recent.py"""
import logging
from fastapi import APIRouter
from models.schemas import RecentPlansResponse, PlanSummary
from services.cache_service import cache

logger = logging.getLogger("thrillophilia.routers.recent")
router = APIRouter()

@router.get("/recent/{session_id}", response_model=RecentPlansResponse)
async def get_recent_plans(session_id: str):
    plan_ids = await cache.get_recent_plan_ids(session_id)
    plans    = []
    for pid in plan_ids:
        meta = await cache.get_plan_meta(pid)
        if meta:
            plans.append(PlanSummary(**meta))
    return RecentPlansResponse(plans=plans)
