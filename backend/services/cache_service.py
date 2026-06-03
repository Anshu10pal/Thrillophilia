"""
backend/services/cache_service.py — Redis Cache Abstraction
============================================================
Upstash Redis via redis-py async client.
All TTLs, key schemas, and cache logic in one place.

Key schema:
  weather:{city}:{YYYY-MM}:{days}       TTL: 3h
  route:{origin}:{dest}:{mode}           TTL: 30d
  places:{city}:{style}:{radius}         TTL: 24h
  plan:{md5_hash}                        TTL: 2h
  geo:{city}                             TTL: permanent
  recent:{session_id}                    TTL: 7d (Redis list)
  meta:{plan_id}                         TTL: 7d
"""

import os
import json
import hashlib
import logging
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis

logger = logging.getLogger("thrillophilia.cache")

# ── TTLs in seconds ───────────────────────────────────────────────────────────
TTL_WEATHER  = 60 * 60 * 3       # 3 hours
TTL_ROUTE    = 60 * 60 * 24 * 30 # 30 days
TTL_PLACES   = 60 * 60 * 24      # 24 hours
TTL_PLAN     = 60 * 60 * 2       # 2 hours
TTL_GEO      = 0                  # permanent (no expiry)
TTL_RECENT   = 60 * 60 * 24 * 7  # 7 days
TTL_META     = 60 * 60 * 24 * 7  # 7 days
MAX_RECENT   = 6


def _norm(s: str) -> str:
    """Normalise string for use in cache key."""
    return s.lower().strip().replace(" ", "_") if s else "unknown"


def _hash(params: Dict) -> str:
    """MD5 hash of sorted dict for compound keys."""
    payload = json.dumps(params, sort_keys=True, default=str)
    return hashlib.md5(payload.encode()).hexdigest()[:12]


def budget_tier(amount: float, currency: str = "INR") -> str:
    """Bucket budget into tier to avoid too-specific cache keys."""
    if currency == "INR":
        if amount < 30000:   return "budget"
        if amount < 80000:   return "mid"
        if amount < 200000:  return "premium"
        return "luxury"
    else:
        if amount < 500:  return "budget"
        if amount < 1500: return "mid"
        return "luxury"


class CacheService:
    """Async Redis cache with typed get/set methods for each data layer."""

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._url = os.getenv("UPSTASH_REDIS_URL") or os.getenv("REDIS_URL", "")

    async def connect(self):
        if not self._url:
            logger.warning("No REDIS_URL set — cache disabled (NullCache mode)")
            return
        try:
            self._redis = aioredis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            await self._redis.ping()
            logger.info("Redis connected: %s", self._url[:40] + "…")
        except Exception as e:
            logger.warning("Redis connection failed: %s — running without cache", e)
            self._redis = None

    async def disconnect(self):
        if self._redis:
            await self._redis.aclose()

    async def ping(self) -> bool:
        if not self._redis:
            return False
        try:
            return await self._redis.ping()
        except Exception:
            return False

    # ── Generic get/set ───────────────────────────────────────────────────────

    async def get(self, key: str) -> Optional[Any]:
        if not self._redis:
            return None
        try:
            raw = await self._redis.get(key)
            if raw:
                logger.debug("CACHE HIT: %s", key)
                return json.loads(raw)
        except Exception as e:
            logger.warning("Cache get error [%s]: %s", key, e)
        return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        if not self._redis:
            return False
        try:
            payload = json.dumps(value, default=str)
            if ttl and ttl > 0:
                await self._redis.setex(key, ttl, payload)
            else:
                await self._redis.set(key, payload)  # no expiry
            logger.debug("CACHE SET: %s (TTL=%ds)", key, ttl)
            return True
        except Exception as e:
            logger.warning("Cache set error [%s]: %s", key, e)
            return False

    async def delete(self, key: str) -> bool:
        if not self._redis:
            return False
        try:
            await self._redis.delete(key)
            return True
        except Exception:
            return False

    # ── Typed methods ─────────────────────────────────────────────────────────

    async def get_weather(self, city: str, month: str, days: int) -> Optional[Dict]:
        key = f"weather:{_norm(city)}:{month}:{days}"
        return await self.get(key)

    async def set_weather(self, city: str, month: str, days: int, data: Dict):
        key = f"weather:{_norm(city)}:{month}:{days}"
        await self.set(key, data, TTL_WEATHER)

    async def get_route(self, origin: str, dest: str, mode: str) -> Optional[Dict]:
        key = f"route:{_norm(origin)}:{_norm(dest)}:{_norm(mode)}"
        return await self.get(key)

    async def set_route(self, origin: str, dest: str, mode: str, data: Dict):
        key = f"route:{_norm(origin)}:{_norm(dest)}:{_norm(mode)}"
        await self.set(key, data, TTL_ROUTE)

    async def get_places(self, city: str, style: str, radius: int) -> Optional[Dict]:
        key = f"places:{_norm(city)}:{_norm(style)}:{radius}"
        return await self.get(key)

    async def set_places(self, city: str, style: str, radius: int, data: Dict):
        key = f"places:{_norm(city)}:{_norm(style)}:{radius}"
        await self.set(key, data, TTL_PLACES)

    async def get_plan(self, dest: str, src: str, days: int,
                       budget: float, currency: str,
                       style: str, month: str) -> Optional[Dict]:
        params = {
            "dest":    _norm(dest),
            "src":     _norm(src),
            "days":    days,
            "tier":    budget_tier(budget, currency),
            "style":   _norm(style),
            "month":   month,
        }
        key = f"plan:{_hash(params)}"
        return await self.get(key)

    async def set_plan(self, dest: str, src: str, days: int,
                       budget: float, currency: str,
                       style: str, month: str, data: Dict):
        params = {
            "dest":  _norm(dest),
            "src":   _norm(src),
            "days":  days,
            "tier":  budget_tier(budget, currency),
            "style": _norm(style),
            "month": month,
        }
        key = f"plan:{_hash(params)}"
        await self.set(key, data, TTL_PLAN)

    async def get_geocode(self, city: str) -> Optional[Dict]:
        """Only called for cities NOT in KNOWN_CITIES."""
        key = f"geo:{_norm(city)}"
        return await self.get(key)

    async def set_geocode(self, city: str, lat: float, lon: float):
        key = f"geo:{_norm(city)}"
        await self.set(key, {"lat": lat, "lon": lon}, TTL_GEO)

    # ── Recent plans ──────────────────────────────────────────────────────────

    async def add_recent_plan(self, session_id: str, plan_id: str):
        """Add plan_id to front of recent list, keep max 6."""
        if not self._redis:
            return
        key = f"recent:{session_id}"
        try:
            await self._redis.lpush(key, plan_id)
            await self._redis.ltrim(key, 0, MAX_RECENT - 1)
            await self._redis.expire(key, TTL_RECENT)
        except Exception as e:
            logger.warning("add_recent_plan error: %s", e)

    async def get_recent_plan_ids(self, session_id: str) -> List[str]:
        if not self._redis:
            return []
        key = f"recent:{session_id}"
        try:
            return await self._redis.lrange(key, 0, MAX_RECENT - 1)
        except Exception:
            return []

    async def set_plan_meta(self, plan_id: str, meta: Dict):
        key = f"meta:{plan_id}"
        await self.set(key, meta, TTL_META)

    async def get_plan_meta(self, plan_id: str) -> Optional[Dict]:
        key = f"meta:{plan_id}"
        return await self.get(key)

    async def get_plan_result(self, plan_id: str) -> Optional[Dict]:
        key = f"result:{plan_id}"
        return await self.get(key)

    async def set_plan_result(self, plan_id: str, result: Dict):
        key = f"result:{plan_id}"
        await self.set(key, result, TTL_PLAN)

    # ── Job status (for SSE polling) ─────────────────────────────────────────

    async def set_job_status(self, job_id: str, status: Dict):
        key = f"job:{job_id}"
        await self.set(key, status, 3600)  # 1 hour TTL

    async def get_job_status(self, job_id: str) -> Optional[Dict]:
        key = f"job:{job_id}"
        return await self.get(key)

    async def append_job_event(self, job_id: str, event: Dict):
        """Append SSE event to job's event list."""
        if not self._redis:
            return
        key = f"events:{job_id}"
        try:
            await self._redis.rpush(key, json.dumps(event, default=str))
            await self._redis.expire(key, 3600)
        except Exception as e:
            logger.warning("append_job_event error: %s", e)

    async def get_job_events(self, job_id: str, from_index: int = 0) -> List[Dict]:
        if not self._redis:
            return []
        key = f"events:{job_id}"
        try:
            raw_list = await self._redis.lrange(key, from_index, -1)
            return [json.loads(r) for r in raw_list]
        except Exception:
            return []


# Singleton instance
cache = CacheService()
