import os, sys, logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
    return {"status": "ok", "service": "Thrillophilia API v2.0"}


@app.get("/health")
async def health():
    from services.cache_service import cache
    ok = await cache.ping()
    return {"status": "healthy" if ok else "degraded", "redis": "connected" if ok else "disconnected"}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"error": str(exc)})
