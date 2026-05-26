"""
config.py — Centralised configuration for the Trip Planner system
=================================================================
Loads environment variables and exposes typed settings used by all modules.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env if it exists (no-op in production where env vars are injected)
load_dotenv()


# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("trip_planner")


# ── OpenAI ────────────────────────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2000"))


# ── External APIs ─────────────────────────────────────────────────────────────
OPENWEATHER_API_KEY: str  = os.getenv("OPENWEATHER_API_KEY", "")
GEOAPIFY_API_KEY: str     = os.getenv("GEOAPIFY_API_KEY", "")
OPENROUTE_API_KEY: str    = os.getenv("OPENROUTE_API_KEY", "")
GOOGLE_MAPS_API_KEY: str  = os.getenv("GOOGLE_MAPS_API_KEY", "")  # optional, legacy

# Log which live APIs are active
_live_apis = []
if OPENWEATHER_API_KEY: _live_apis.append("OpenWeatherMap")
if GEOAPIFY_API_KEY:    _live_apis.append("Geoapify")
if OPENROUTE_API_KEY:   _live_apis.append("OpenRouteService")
_live_apis += ["Open-Meteo (no key)", "Xotelo (no key)"]


# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
FAISS_INDEX_PATH: str = os.getenv("FAISS_INDEX_PATH", str(BASE_DIR / "data" / "faiss_travel_index"))
PDF_OUTPUT_DIR: str = os.getenv("PDF_OUTPUT_DIR", str(BASE_DIR / "output"))

# Ensure directories exist
Path(FAISS_INDEX_PATH).parent.mkdir(parents=True, exist_ok=True)
Path(PDF_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)


# ── Agent settings ────────────────────────────────────────────────────────────
MAX_RETRY_PER_AGENT: int = int(os.getenv("MAX_RETRY_PER_AGENT", "2"))
MAX_ORCHESTRATOR_ITERATIONS: int = int(os.getenv("MAX_ORCHESTRATOR_ITERATIONS", "5"))
RETRIEVAL_TOP_K: int = int(os.getenv("RETRIEVAL_TOP_K", "8"))


def validate_config() -> bool:
    """Raise if critical config is missing."""
    if not OPENAI_API_KEY:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. "
            "Copy .env.example → .env and add your key."
        )
    logger.info("Configuration validated ✓  (model=%s, embedding=%s)", LLM_MODEL, EMBEDDING_MODEL)
    return True
