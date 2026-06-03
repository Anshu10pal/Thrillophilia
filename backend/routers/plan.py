"""
backend/routers/plan.py — Planning endpoints
"""
import asyncio
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from models.schemas import PlanRequest, PlanResponse, AddCityRequest
from services.planning_service import run_planning_job, _make_job_id
from services.cache_service import cache

logger = logging.getLogger("thrillophilia.routers.plan")
router = APIRouter()


@router.post("/plan", response_model=PlanResponse)
async def create_plan(request: PlanRequest, background_tasks: BackgroundTasks):
    """Start an async trip planning job. Returns job_id immediately."""
    job_id = _make_job_id()
    await cache.set_job_status(job_id, {"status": "queued", "progress": 0})

    background_tasks.add_task(
        run_planning_job,
        job_id,
        request.model_dump(),
    )
    logger.info("Plan job %s queued for: %s", job_id, request.query[:60])
    return PlanResponse(job_id=job_id, status="queued")


@router.get("/plan/{job_id}")
async def get_plan_result(job_id: str):
    """Get the full result of a completed plan."""
    result = await cache.get_plan_result(job_id)
    if not result:
        status = await cache.get_job_status(job_id)
        if not status:
            raise HTTPException(404, detail="Job not found")
        return JSONResponse({"status": status.get("status", "unknown"), "result": None})
    return JSONResponse({"status": "complete", "result": result})


@router.get("/plan/{job_id}/status")
async def get_plan_status(job_id: str):
    """Get current status of a planning job."""
    status = await cache.get_job_status(job_id)
    if not status:
        raise HTTPException(404, detail="Job not found")
    return status


@router.post("/plan/add-city")
async def add_city_to_plan(request: AddCityRequest, background_tasks: BackgroundTasks):
    """Add a nearby city to an existing plan and rebuild itinerary."""
    existing = await cache.get_plan_result(request.job_id)
    if not existing:
        raise HTTPException(404, detail="Plan not found")

    new_job_id = _make_job_id()
    prefs = existing.get("trip_preferences", {})
    stopovers = prefs.get("stopovers", [])
    stopovers.append(request.city)

    new_request = {
        "query": f"Add {request.city} to the trip",
        "preferences": {**prefs, "stopovers": stopovers,
                        "num_days": prefs.get("num_days", 5) + request.num_days},
        "travel_style": prefs.get("travel_style", "balanced"),
        "session_id":   request.job_id,
    }
    await cache.set_job_status(new_job_id, {"status": "queued"})
    background_tasks.add_task(run_planning_job, new_job_id, new_request)
    return {"job_id": new_job_id, "status": "queued", "message": f"Adding {request.city} to your plan…"}
