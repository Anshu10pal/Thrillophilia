"""
backend/routers/stream.py — Server-Sent Events streaming
"""
import asyncio
import json
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from services.cache_service import cache

logger = logging.getLogger("thrillophilia.routers.stream")
router = APIRouter()


@router.get("/stream/{job_id}")
async def stream_job_events(job_id: str):
    """
    SSE endpoint — streams agent progress events in real time.
    React polls this with EventSource.
    """
    async def event_generator():
        sent_index  = 0
        max_wait    = 600   # 3 minutes max
        elapsed     = 0
        poll_interval = 0.8

        while elapsed < max_wait:
            # Check for new events
            events = await cache.get_job_events(job_id, from_index=sent_index)
            for ev in events:
                yield f"data: {json.dumps(ev)}\n\n"
                sent_index += 1
                if ev.get("event") in ("complete", "error"):
                    return

            # Check job status
            status = await cache.get_job_status(job_id)
            if status and status.get("status") in ("complete", "failed"):
                if not events:
                    yield f"data: {json.dumps({'event': status['status']})}\n\n"
                return

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        yield f"data: {json.dumps({'event': 'timeout', 'message': 'Planning took too long'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":   "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":      "keep-alive",
        },
    )
