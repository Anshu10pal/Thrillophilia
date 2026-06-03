"""
config.py — Centralised configuration
Supports both direct OpenAI keys and API gateway (base_url).
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env from this file's directory, then parent
_here = Path(__file__).parent
for _p in [_here / ".env", _here.parent / ".env", _here / "backend" / ".env"]:
    if _p.exists():
        load_dotenv(_p, override=True)
        break
else:
    load_dotenv(override=True)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("trip_planner")

# ── OpenAI / Gateway ──────────────────────────────────────────────────────────
OPENAI_API_KEY:  str   = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL: str   = os.getenv("OPENAI_BASE_URL", "")   # e.g. https://keygateway.arshnivlabs.com/v1
LLM_MODEL:       str   = os.getenv("LLM_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL: str   = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS:  int   = int(os.getenv("LLM_MAX_TOKENS", "2000"))

# ── External APIs ─────────────────────────────────────────────────────────────
OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")
GEOAPIFY_API_KEY:    str = os.getenv("GEOAPIFY_API_KEY", "")
OPENROUTE_API_KEY:   str = os.getenv("OPENROUTE_API_KEY", "")

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR          = Path(__file__).parent
FAISS_INDEX_PATH  = os.getenv("FAISS_INDEX_PATH",  str(BASE_DIR / "data" / "faiss_travel_index"))
PDF_OUTPUT_DIR    = os.getenv("PDF_OUTPUT_DIR",    str(BASE_DIR / "output"))

Path(FAISS_INDEX_PATH).parent.mkdir(parents=True, exist_ok=True)
Path(PDF_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

# ── Agent settings ────────────────────────────────────────────────────────────
MAX_RETRY_PER_AGENT:          int = int(os.getenv("MAX_RETRY_PER_AGENT", "2"))
MAX_ORCHESTRATOR_ITERATIONS:  int = int(os.getenv("MAX_ORCHESTRATOR_ITERATIONS", "5"))
RETRIEVAL_TOP_K:               int = int(os.getenv("RETRIEVAL_TOP_K", "8"))


def validate_config() -> bool:
    if not OPENAI_API_KEY:
        raise EnvironmentError("OPENAI_API_KEY is not set.")
    logger.info(
        "Config OK — model=%s base_url=%s",
        LLM_MODEL,
        OPENAI_BASE_URL[:40] + "…" if OPENAI_BASE_URL else "default (OpenAI)"
    )
    return True
