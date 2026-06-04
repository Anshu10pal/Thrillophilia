import os, sys, logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Load .env from backend folder
load_dotenv(Path(__file__).parent / ".env", override=True)
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger("thrillophilia.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from services.cache_service import cache
    await cache.connect()
    ok = await cache.ping()
    logger.info("Redis %s", "connected ✓" if ok else "NOT connected — NullCache mode")
    yield
    await cache.disconnect()


app = FastAPI(title="Thrillophilia API", version="2.0.0", lifespan=lifespan)

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers.plan    import router as plan_router
from routers.stream  import router as stream_router
from routers.clarify import router as clarify_router
from routers.recent  import router as recent_router
from routers.nearby  import router as nearby_router
from routers.styles  import router as styles_router

app.include_router(plan_router,    prefix="/api", tags=["Planning"])
app.include_router(stream_router,  prefix="/api", tags=["Streaming"])
app.include_router(clarify_router, prefix="/api", tags=["Clarification"])
app.include_router(recent_router,  prefix="/api", tags=["Recent Plans"])
app.include_router(nearby_router,  prefix="/api", tags=["Nearby Cities"])
app.include_router(styles_router,  prefix="/api", tags=["Travel Styles"])


@app.get("/")
async def root():
    index = Path(__file__).parent.parent / "frontend" / "dist" / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"status": "ok", "service": "Thrillophilia API v2.0"}


@app.get("/health")
async def health():
    from services.cache_service import cache
    ok = await cache.ping()
    return {"status": "healthy" if ok else "degraded", "redis": "connected" if ok else "disconnected"}


@app.get("/api/debug/config")
async def debug_config():
    """Shows which env vars are set (values masked). Useful for diagnosing missing keys."""
    import os
    keys = ["OPENAI_API_KEY", "OPENAI_BASE_URL", "UPSTASH_REDIS_URL",
            "LANGCHAIN_API_KEY", "LANGCHAIN_TRACING_V2", "LLM_MODEL"]
    return {
        k: ("✓ set" if os.getenv(k) else "✗ NOT SET")
        for k in keys
    }


@app.get("/api/debug/job/{job_id}")
async def debug_job(job_id: str):
    """Shows full status + events for a job. Paste job_id from the UI."""
    from services.cache_service import cache
    status = await cache.get_job_status(job_id)
    events = await cache.get_job_events(job_id)
    result = await cache.get_plan_result(job_id)
    return {
        "job_id": job_id,
        "status": status,
        "event_count": len(events),
        "events": events[-10:],   # last 10 events
        "has_result": result is not None,
        "result_keys": list(result.keys()) if result else [],
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"error": str(exc)})


# ── Serve React frontend (must be last) ───────────────────────────────────────
_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _DIST.exists():
    if (_DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        target = _DIST / full_path
        if target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(_DIST / "index.html"))
