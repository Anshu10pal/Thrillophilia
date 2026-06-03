"""
tools/live_apis.py  —  Live API integrations
=============================================
Every function tries the real API first, falls back to None on failure.
Agents check for None and fall back to LLM reasoning gracefully.

APIs wired:
  ✅ Open-Meteo        — weather forecast (no key)
  ✅ OpenWeatherMap    — current weather + forecast (OPENWEATHER_API_KEY)
  ✅ Geoapify Places   — attractions, restaurants, POIs (GEOAPIFY_API_KEY)
  ✅ OpenRouteService  — road distance + duration (OPENROUTE_API_KEY)
  ✅ Xotelo            — live hotel prices (no key)

Fixes in this version:
  - Extended KNOWN_CITIES with all major Indian hill stations + Ladakh/Leh
  - fetch_places: separate restaurant fallback query for cities returning 0 restaurants
  - fetch_places: broader catering category for better Dubai/metro results
  - fetch_route_distance: respects user transport_preference override
"""

import os, json, logging, time
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta

import requests

logger = logging.getLogger("trip_planner.live_apis")

try:
    from langsmith import traceable
except ImportError:
    def traceable(**kwargs):
        def decorator(fn): return fn
        return decorator

# ── Keys ──────────────────────────────────────────────────────────────────────
OPENWEATHER_KEY  = os.getenv("OPENWEATHER_API_KEY", "")
GEOAPIFY_KEY     = os.getenv("GEOAPIFY_API_KEY", "")
OPENROUTE_KEY    = os.getenv("OPENROUTE_API_KEY", "")

TIMEOUT = 10   # seconds per request


# ══════════════════════════════════════════════════════════════════════════════
# KNOWN CITIES fallback table (used when both geocoding APIs fail)
# Comprehensive India coverage + popular international destinations
# ══════════════════════════════════════════════════════════════════════════════

KNOWN_CITIES: Dict[str, Tuple[float, float]] = {
    # ── Major Indian metros ────────────────────────────────────────────────────
    "goa":          (15.4909,  73.8278),
    "mumbai":       (19.0760,  72.8777),
    "bangalore":    (12.9716,  77.5946),
    "bengaluru":    (12.9716,  77.5946),
    "delhi":        (28.6139,  77.2090),
    "new delhi":    (28.6139,  77.2090),
    "chennai":      (13.0827,  80.2707),
    "kolkata":      (22.5726,  88.3639),
    "hyderabad":    (17.3850,  78.4867),
    "pune":         (18.5204,  73.8567),
    "ahmedabad":    (23.0225,  72.5714),
    "surat":        (21.1702,  72.8311),
    "jaipur":       (26.9124,  75.7873),
    "lucknow":      (26.8467,  80.9462),
    "kanpur":       (26.4499,  80.3319),
    "nagpur":       (21.1458,  79.0882),
    "indore":       (22.7196,  75.8577),
    "bhopal":       (23.2599,  77.4126),
    "visakhapatnam":(17.6868,  83.2185),
    "patna":        (25.5941,  85.1376),
    "vadodara":     (22.3072,  73.1812),
    # ── Rajasthan ─────────────────────────────────────────────────────────────
    "udaipur":      (24.5854,  73.7125),
    "jodhpur":      (26.2389,  73.0243),
    "jaisalmer":    (26.9157,  70.9083),
    "pushkar":      (26.4898,  74.5511),
    "ajmer":        (26.4499,  74.6399),
    "bikaner":      (28.0229,  73.3119),
    "mount abu":    (24.5926,  72.7156),
    # ── Hill stations & North India ────────────────────────────────────────────
    "shimla":       (31.1048,  77.1734),
    "manali":       (32.2432,  77.1892),
    "dharamshala":  (32.2190,  76.3234),
    "mcleod ganj":  (32.2423,  76.3217),
    "dalhousie":    (32.5387,  75.9734),
    "kasauli":      (30.8989,  76.9686),
    "mussoorie":    (30.4598,  78.0644),
    "nainital":     (29.3803,  79.4636),
    "dehradun":     (30.3165,  78.0322),
    "haridwar":     (29.9457,  78.1642),
    "rishikesh":    (30.0869,  78.2676),
    "auli":         (30.5228,  79.5618),
    "chopta":       (30.3869,  79.2067),
    # ── Ladakh / Kashmir ──────────────────────────────────────────────────────
    "leh":          (34.1526,  77.5770),
    "ladakh":       (34.1526,  77.5770),
    "leh ladakh":   (34.1526,  77.5770),
    "kargil":       (34.5539,  76.1349),
    "nubra valley": (34.7258,  77.5706),
    "pangong":      (33.7643,  78.5920),
    "pangong lake": (33.7643,  78.5920),
    "zanskar":      (33.4484,  76.4741),
    "srinagar":     (34.0837,  74.7973),
    "gulmarg":      (34.0497,  74.3839),
    "pahalgam":     (34.0161,  75.3153),
    "sonamarg":     (34.3059,  75.2935),
    # ── Punjab & Haryana ──────────────────────────────────────────────────────
    "amritsar":     (31.6340,  74.8723),
    "pathankot":    (32.2643,  75.6421),
    "chandigarh":   (30.7333,  76.7794),
    "ludhiana":     (30.9010,  75.8573),
    "jalandhar":    (31.3260,  75.5762),
    # ── Himachal Pradesh ──────────────────────────────────────────────────────
    "spiti":        (32.2460,  78.0338),
    "spiti valley": (32.2460,  78.0338),
    "kasol":        (32.0998,  77.3147),
    "kheerganga":   (32.1617,  77.3563),
    "kullu":        (31.9579,  77.1092),
    "mandi":        (31.7080,  76.9318),
    "keylong":      (32.5695,  77.0233),
    "kaza":         (32.2262,  78.0714),
    "rohtang pass": (32.3715,  77.2439),
    "solang valley":(32.3197,  77.1517),
    # ── Uttarakhand ────────────────────────────────────────────────────────────
    "kedarnath":    (30.7352,  79.0669),
    "badrinath":    (30.7433,  79.4938),
    "corbett":      (29.5300,  78.7747),
    "jim corbett":  (29.5300,  78.7747),
    "chakrata":     (30.7009,  77.8620),
    # ── Northeast India ────────────────────────────────────────────────────────
    "darjeeling":   (27.0360,  88.2627),
    "gangtok":      (27.3389,  88.6065),
    "sikkim":       (27.5330,  88.5122),
    "shillong":     (25.5788,  91.8933),
    "cherrapunji":  (25.2845,  91.7204),
    "kaziranga":    (26.5775,  93.1711),
    "guwahati":     (26.1445,  91.7362),
    "dibrugarh":    (27.4728,  94.9120),
    "tawang":       (27.5859,  91.8663),
    "ziro":         (27.5476,  93.8279),
    # ── South India ────────────────────────────────────────────────────────────
    "kerala":       (10.8505,  76.2711),
    "kochi":        ( 9.9312,  76.2673),
    "alleppey":     ( 9.4981,  76.3388),
    "alappuzha":    ( 9.4981,  76.3388),
    "munnar":       (10.0889,  77.0595),
    "thekkady":     ( 9.6001,  77.1655),
    "kovalam":      ( 8.4020,  76.9787),
    "varkala":      ( 8.7379,  76.7163),
    "thrissur":     (10.5276,  76.2144),
    "trivandrum":   ( 8.5241,  76.9366),
    "kozhikode":    (11.2588,  75.7804),
    "mysore":       (12.2958,  76.6394),
    "ooty":         (11.4102,  76.6950),
    "coorg":        (12.3375,  75.8069),
    "hampi":        (15.3350,  76.4600),
    "pondicherry":  (11.9416,  79.8083),
    "madurai":      ( 9.9252,  78.1198),
    "rameswaram":   ( 9.2877,  79.3129),
    "tirupati":     (13.6288,  79.4192),
    "varanasi":     (25.3176,  82.9739),
    "agra":         (27.1767,  78.0081),
    "mathura":      (27.4924,  77.6737),
    "vrindavan":    (27.5716,  77.6967),
    "allahabad":    (25.4358,  81.8463),
    "prayagraj":    (25.4358,  81.8463),
    "ayodhya":      (26.7922,  82.1998),
    # ── Islands ────────────────────────────────────────────────────────────────
    "andaman":      (11.7401,  92.6586),
    "port blair":   (11.6234,  92.7265),
    "havelock":     (12.0010,  92.9897),
    "neil island":  (11.8318,  93.0473),
    "lakshadweep":  (10.5593,  72.6358),
    # ── Popular International ──────────────────────────────────────────────────
    "dubai":        (25.2048,  55.2708),
    "abu dhabi":    (24.4539,  54.3773),
    "bali":         (-8.3405, 115.0920),
    "bangkok":      (13.7563, 100.5018),
    "phuket":       ( 7.8804,  98.3923),
    "singapore":    ( 1.3521, 103.8198),
    "kuala lumpur": ( 3.1390, 101.6869),
    "tokyo":        (35.6762, 139.6503),
    "osaka":        (34.6937, 135.5023),
    "kyoto":        (35.0116, 135.7681),
    "paris":        (48.8566,   2.3522),
    "london":       (51.5074,  -0.1278),
    "barcelona":    (41.3851,   2.1734),
    "rome":         (41.9028,  12.4964),
    "amsterdam":    (52.3676,   4.9041),
    "zurich":       (47.3769,   8.5417),
    "interlaken":   (46.6863,   7.8632),
    "maldives":     ( 3.2028,  73.2207),
    "male":         ( 4.1755,  73.5093),
    "nepal":        (28.3949,  84.1240),
    "kathmandu":    (27.7172,  85.3240),
    "pokhara":      (28.2096,  83.9856),
    "bhutan":       (27.5142,  90.4336),
    "thimphu":      (27.4728,  89.6393),
    "colombo":      ( 6.9271,  79.8612),
    "new york":     (40.7128, -74.0060),
    "los angeles":  (34.0522,-118.2437),
    "sydney":       (-33.8688, 151.2093),
    "melbourne":    (-37.8136, 144.9631),
}

@traceable(name="geocode_city", run_type="tool",
           metadata={"apis": "Geoapify → OWM → KNOWN_CITIES"})
def geocode_city(city: str) -> Optional[Tuple[float, float]]:
    """
    Convert city name to (lat, lon).
    Priority: Geoapify → OpenWeatherMap → KNOWN_CITIES table → None
    """
    if not city or city.strip().lower() in ("null", "none", "", "unknown"):
        return None

    city_clean = city.split(",")[0].strip()

    # 1. Try Geoapify
    if GEOAPIFY_KEY:
        try:
            r = requests.get(
                "https://api.geoapify.com/v1/geocode/search",
                params={
                    "text":    city_clean,
                    "limit":   1,
                    "apiKey":  GEOAPIFY_KEY,
                    "lang":    "en",
                    "filter":  "countrycode:in,ae,sg,th,gb,fr,de,us,au,jp,id,np,bt,lk,mv,om,qa",
                },
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            features = r.json().get("features", [])
            if features:
                coords = features[0]["geometry"]["coordinates"]
                lat, lon = coords[1], coords[0]
                # Sanity check: reject obviously wrong coordinates
                # India bounding box: lat 8-37, lon 68-97
                # If it's an Indian city name but coords are outside India/Asia, reject
                indian_cities = {"shimla","manali","ladakh","leh","pathankot","goa","kerala",
                                 "delhi","mumbai","bangalore","chennai","kolkata","jaipur",
                                 "darjeeling","andaman","rishikesh","udaipur","varanasi",
                                 "amritsar","chandigarh","dehradun","mussoorie","nainital",
                                 "spiti","kasol","kargil","srinagar"}
                city_lower = city_clean.lower()
                is_indian  = any(c in city_lower or city_lower in c for c in indian_cities)
                if is_indian and not (8 <= lat <= 37 and 68 <= lon <= 97):
                    logger.warning(
                        "Geoapify returned wrong coords for Indian city '%s': %.4f,%.4f — using KNOWN_CITIES",
                        city_clean, lat, lon
                    )
                else:
                    logger.info("Geocoded '%s' → %.4f, %.4f (Geoapify)", city_clean, lat, lon)
                    return lat, lon
        except Exception as e:
            logger.warning("Geoapify geocode failed for '%s': %s", city_clean, e)

    # 2. Try OpenWeatherMap geocoding
    if OPENWEATHER_KEY:
        try:
            r = requests.get(
                "http://api.openweathermap.org/geo/1.0/direct",
                params={"q": city_clean, "limit": 1, "appid": OPENWEATHER_KEY},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            if data:
                lat, lon = data[0]["lat"], data[0]["lon"]
                logger.info("Geocoded '%s' → %.4f, %.4f (OWM)", city_clean, lat, lon)
                return lat, lon
        except Exception as e:
            logger.warning("OWM geocode failed for '%s': %s", city_clean, e)

    # 3. KNOWN_CITIES table
    key = city_clean.lower()
    for k, coords in KNOWN_CITIES.items():
        if k == key or k in key or key in k:
            logger.info("Geocoded '%s' → %.4f, %.4f (KNOWN_CITIES)", city_clean, *coords)
            return coords

    logger.error("Could not geocode city: '%s'", city_clean)
    return None


# ══════════════════════════════════════════════════════════════════════════════
# 1. WEATHER  —  Open-Meteo (primary) + OpenWeatherMap (fallback)
# ══════════════════════════════════════════════════════════════════════════════

@traceable(name="fetch_weather", run_type="tool",
           metadata={"apis": "Open-Meteo → OWM fallback"})
def fetch_weather(destination: str,
                  start_date: Optional[str] = None,
                  num_days: int = 7) -> Optional[Dict[str, Any]]:
    """Fetch real weather forecast. Returns structured dict or None."""
    coords = geocode_city(destination)
    if not coords:
        return None

    lat, lon = coords

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else datetime.now()
    except Exception:
        start_dt = datetime.now()

    end_dt    = start_dt + timedelta(days=min(num_days, 14))
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str   = end_dt.strftime("%Y-%m-%d")

    # ── Open-Meteo (primary, no key) ──────────────────────────────────────────
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude":      lat,
                "longitude":     lon,
                "daily":         "temperature_2m_max,temperature_2m_min,"
                                 "precipitation_sum,weathercode,windspeed_10m_max",
                "timezone":      "auto",
                "start_date":    start_str,
                "end_date":      end_str,
                "forecast_days": min(num_days, 16),
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data  = r.json()
        daily = data.get("daily", {})
        dates     = daily.get("time", [])
        temp_max  = daily.get("temperature_2m_max", [])
        temp_min  = daily.get("temperature_2m_min", [])
        precip    = daily.get("precipitation_sum", [])
        wind      = daily.get("windspeed_10m_max", [])
        wcodes    = daily.get("weathercode", [])

        if not dates:
            raise ValueError("Empty Open-Meteo response")

        avg_max  = sum(t for t in temp_max if t is not None) / max(len([t for t in temp_max if t]), 1)
        avg_min  = sum(t for t in temp_min if t is not None) / max(len([t for t in temp_min if t]), 1)
        avg_prec = sum(p for p in precip  if p is not None) / max(len([p for p in precip  if p]), 1)
        avg_wind = sum(w for w in wind    if w is not None) / max(len([w for w in wind    if w]), 1)

        def wmo_desc(code):
            if code in (0, 1):         return "sunny"
            if code in (2, 3):         return "partly cloudy"
            if code in range(51, 68):  return "rainy"
            if code in range(71, 78):  return "snow"
            if code in range(80, 82):  return "showers"
            if code in range(95, 100): return "thunderstorm"
            return "cloudy"

        dominant   = max(set(wcodes), key=wcodes.count) if wcodes else 0
        conditions = wmo_desc(dominant)
        rainfall   = "high" if avg_prec > 5 else ("moderate" if avg_prec > 2 else "low")

        if avg_max > 30:   clothing = "Light summer clothes, sunscreen and hat."
        elif avg_max > 22: clothing = "Light casuals. Carry a light jacket for evenings."
        elif avg_max > 15: clothing = "Layered clothing. Jacket required."
        else:              clothing = "Warm jacket, thermals and waterproof gear."

        warnings = []
        if avg_prec > 5:  warnings.append(f"Expect rain ({avg_prec:.1f}mm/day avg) — carry umbrella")
        if avg_wind > 40: warnings.append(f"Strong winds expected ({avg_wind:.0f}km/h avg)")
        if dominant >= 95: warnings.append("Thunderstorms possible — check forecast daily")

        forecast_days = []
        for i, date in enumerate(dates[:num_days]):
            forecast_days.append({
                "date":          date,
                "max_temp":      f"{temp_max[i]:.0f}°C"  if i < len(temp_max) and temp_max[i]  is not None else "N/A",
                "min_temp":      f"{temp_min[i]:.0f}°C"  if i < len(temp_min) and temp_min[i]  is not None else "N/A",
                "precipitation": f"{precip[i]:.1f}mm"    if i < len(precip)   and precip[i]    is not None else "0mm",
                "conditions":    wmo_desc(wcodes[i]       if i < len(wcodes)  else 0),
            })

        # Build date → weather lookup for itinerary day matching
        _W_EMOJI = {
            "sunny": "☀️", "partly cloudy": "⛅", "cloudy": "☁️",
            "rainy": "🌧️", "showers": "🌦️", "thunderstorm": "⛈️",
            "snow": "❄️",
        }
        daily_lookup = {}
        for fd in forecast_days:
            daily_lookup[fd["date"]] = {
                "max_temp":      fd["max_temp"],
                "min_temp":      fd["min_temp"],
                "conditions":    fd["conditions"],
                "precipitation": fd["precipitation"],
                "emoji":         _W_EMOJI.get(fd["conditions"], "🌤️"),
            }

        result = {
            "source":          "Open-Meteo (live)",
            "destination":     destination,
            "lat":             lat, "lon": lon,
            "travel_period":   f"{start_str} to {end_str}",
            "avg_temp_day":    f"{avg_max:.0f}°C",
            "avg_temp_night":  f"{avg_min:.0f}°C",
            "conditions":      conditions,
            "rainfall":        rainfall,
            "avg_precip_mm":   round(avg_prec, 1),
            "avg_wind_kmh":    round(avg_wind, 1),
            "clothing_advice": clothing,
            "weather_warnings": warnings,
            "beach_suitable":  avg_max > 20 and avg_prec < 3 and conditions in ("sunny","partly cloudy"),
            "outdoor_suitable": conditions not in ("thunderstorm",) and avg_prec < 8,
            "forecast_days":   forecast_days,
            "daily_lookup":    daily_lookup,
            "weather_summary": (
                f"{destination} will have {conditions} weather, "
                f"{avg_max:.0f}°C highs and {avg_min:.0f}°C lows. "
                f"Avg precipitation: {avg_prec:.1f}mm/day."
            ),
        }
        logger.info("[LiveAPI] Weather via Open-Meteo for %s ✓", destination)
        return result

    except Exception as e:
        logger.warning("Open-Meteo failed: %s — trying OpenWeatherMap", e)

    # ── OpenWeatherMap fallback ────────────────────────────────────────────────
    if not OPENWEATHER_KEY:
        return None

    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={"lat": lat, "lon": lon, "appid": OPENWEATHER_KEY,
                    "units": "metric", "cnt": min(num_days * 8, 40)},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data      = r.json()
        forecasts = data.get("list", [])
        if not forecasts:
            return None

        temps   = [f["main"]["temp"]                        for f in forecasts]
        precips = [f.get("rain", {}).get("3h", 0)           for f in forecasts]
        descs   = [f["weather"][0]["main"]                  for f in forecasts]

        avg_max   = max(temps)
        avg_min   = min(temps)
        avg_prec  = sum(precips) / max(len(precips), 1) * 8
        dominant  = max(set(descs), key=descs.count).lower()
        conditions = "sunny" if "clear" in dominant else (
                     "rainy" if "rain"  in dominant else (
                     "cloudy" if "cloud" in dominant else dominant))
        rainfall = "high" if avg_prec > 5 else ("moderate" if avg_prec > 2 else "low")

        # Build daily_lookup from OWM 3-hourly data (group by date, take max/min)
        from collections import defaultdict
        day_groups = defaultdict(list)
        for f in forecasts:
            date_key = f["dt_txt"][:10] if "dt_txt" in f else ""
            if date_key:
                day_groups[date_key].append(f)

        _W_EMOJI = {
            "sunny": "☀️", "partly cloudy": "⛅", "cloudy": "☁️",
            "rainy": "🌧️", "showers": "🌦️", "thunderstorm": "⛈️",
        }
        owm_daily_lookup = {}
        for date_key, day_forecasts in sorted(day_groups.items()):
            d_temps  = [f["main"]["temp"]   for f in day_forecasts]
            d_precip = [f.get("rain",{}).get("3h",0) for f in day_forecasts]
            d_descs  = [f["weather"][0]["main"].lower() for f in day_forecasts]
            d_max    = max(d_temps)
            d_min    = min(d_temps)
            d_prec   = sum(d_precip)
            d_dom    = max(set(d_descs), key=d_descs.count)
            d_cond   = "sunny" if "clear" in d_dom else ("rainy" if "rain" in d_dom else "cloudy")
            owm_daily_lookup[date_key] = {
                "max_temp":      f"{d_max:.0f}°C",
                "min_temp":      f"{d_min:.0f}°C",
                "conditions":    d_cond,
                "precipitation": f"{d_prec:.1f}mm",
                "emoji":         _W_EMOJI.get(d_cond, "🌤️"),
            }

        result = {
            "source":          "OpenWeatherMap (live)",
            "destination":     destination,
            "lat":             lat, "lon": lon,
            "travel_period":   f"{start_str} to {end_str}",
            "avg_temp_day":    f"{avg_max:.0f}°C",
            "avg_temp_night":  f"{avg_min:.0f}°C",
            "conditions":      conditions,
            "rainfall":        rainfall,
            "avg_precip_mm":   round(avg_prec, 1),
            "clothing_advice": "Check daily forecast and dress accordingly.",
            "weather_warnings": ["Heavy rain — carry umbrella"] if avg_prec > 5 else [],
            "beach_suitable":  avg_max > 22 and avg_prec < 3,
            "outdoor_suitable": avg_prec < 8,
            "forecast_days":   list(owm_daily_lookup.values()),
            "daily_lookup":    owm_daily_lookup,
            "weather_summary": (
                f"{destination}: {conditions}, {avg_max:.0f}°C highs, "
                f"{avg_min:.0f}°C lows."
            ),
        }
        logger.info("[LiveAPI] Weather via OpenWeatherMap for %s ✓", destination)
        return result

    except Exception as e:
        logger.error("OpenWeatherMap failed: %s", e)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 2. PLACES  —  Geoapify
# ══════════════════════════════════════════════════════════════════════════════

INTEREST_TO_CATEGORIES = {
    "beach":       "natural.beach,leisure.park,sport.swimming",
    "adventure":   "sport,leisure,tourism.attraction",
    "culture":     "tourism.attraction,heritage,education.museum,entertainment.culture",
    "nightlife":   "entertainment.nightclub,catering.bar,entertainment",
    "nature":      "natural,tourism.attraction,leisure.park",
    "food":        "catering.restaurant,catering.cafe,catering.fast_food",
    "sightseeing": "tourism.attraction,tourism.sights,heritage",
    "shopping":    "commercial.shopping_mall,commercial.marketplace",
    "history":     "heritage,tourism.attraction,education.museum",
    "religious":   "religion,tourism.attraction",
    "honeymoon":   "tourism.attraction,natural.beach,leisure.park,catering.restaurant",
    "default":     "tourism.attraction,catering.restaurant,entertainment",
}


def _geoapify_request(lat: float, lon: float, categories: str,
                      radius_m: int, limit: int) -> List[Dict]:
    """Single Geoapify places request, returns raw feature list."""
    r = requests.get(
        "https://api.geoapify.com/v2/places",
        params={
            "categories": categories,
            "filter":     f"circle:{lon},{lat},{radius_m}",
            "bias":       f"proximity:{lon},{lat}",
            "limit":      limit,
            "apiKey":     GEOAPIFY_KEY,
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json().get("features", [])


@traceable(name="fetch_places", run_type="tool",
           metadata={"api": "Geoapify"})
def fetch_places(destination: str,
                 interests: List[str] = None,
                 radius_m: int = 15000,
                 limit: int = 20) -> Optional[Dict[str, Any]]:
    """
    Fetch real attractions, restaurants, and activities from Geoapify.
    Includes a restaurant-specific fallback query if main query returns 0 restaurants.
    """
    if not GEOAPIFY_KEY:
        logger.warning("No GEOAPIFY_API_KEY — skipping live places")
        return None

    coords = geocode_city(destination)
    if not coords:
        return None

    lat, lon = coords

    # Build categories from interests
    cats_set = set()
    for interest in (interests or ["sightseeing"]):
        key     = interest.lower().strip()
        matched = next((v for k, v in INTEREST_TO_CATEGORIES.items() if k in key), None)
        if matched:
            cats_set.update(matched.split(","))
    if not cats_set:
        cats_set = set(INTEREST_TO_CATEGORIES["default"].split(","))

    # Always include catering for restaurants
    cats_set.add("catering.restaurant")
    cats_set.add("catering.cafe")
    categories = ",".join(sorted(cats_set))

    try:
        features = _geoapify_request(lat, lon, categories, radius_m, limit)
        attractions, restaurants, activities = [], [], []

        for feat in features:
            props    = feat.get("properties", {})
            name     = props.get("name", "").strip()
            if not name or len(name) < 3:
                continue

            cats_raw = props.get("categories", [])
            cat_str  = ",".join(cats_raw) if isinstance(cats_raw, list) else str(cats_raw)
            address  = props.get("formatted", props.get("city", destination))
            rating   = round(props.get("datasource", {}).get("rating", 0) or 0, 1) or None

            entry = {
                "name":     name,
                "location": address[:60] if address else destination,
                "rating":   rating or "N/A",
                "lat":      feat["geometry"]["coordinates"][1],
                "lon":      feat["geometry"]["coordinates"][0],
            }

            if any(k in cat_str for k in ("restaurant","cafe","food","catering")):
                entry.update({
                    "cuisine":             "Local",
                    "avg_cost_per_person": 0,
                    "must_try_dish":       "Local speciality",
                    "type":                "restaurant",
                })
                restaurants.append(entry)
            elif any(k in cat_str for k in ("sport","leisure","entertainment","nightclub")):
                entry.update({
                    "type":            _cat_to_type(cat_str),
                    "cost_per_person": 0,
                    "duration":        "2h",
                    "suitable_for":    "all",
                })
                activities.append(entry)
            else:
                entry.update({
                    "type":      _cat_to_type(cat_str),
                    "duration":  "1-2h",
                    "entry_fee": None,
                    "best_time": "morning",
                })
                attractions.append(entry)

        # ── Restaurant fallback: if 0 restaurants, try broader catering query ──
        if len(restaurants) == 0:
            logger.info("[LiveAPI] 0 restaurants from main query — trying broad catering search")
            try:
                rest_features = _geoapify_request(lat, lon, "catering", radius_m, 10)
                for feat in rest_features:
                    props = feat.get("properties", {})
                    name  = props.get("name", "").strip()
                    if name and len(name) >= 3:
                        address = props.get("formatted", destination)
                        restaurants.append({
                            "name":                name,
                            "location":            address[:60],
                            "rating":              "N/A",
                            "cuisine":             "Local",
                            "avg_cost_per_person": 0,
                            "must_try_dish":       "Local speciality",
                            "type":                "restaurant",
                        })
            except Exception as re:
                logger.warning("Restaurant fallback query failed: %s", re)

        logger.info(
            "[LiveAPI] Places for %s: %d attractions, %d restaurants, %d activities",
            destination, len(attractions), len(restaurants), len(activities)
        )

        if not attractions and not restaurants and not activities:
            return None

        return {
            "source":          "Geoapify (live)",
            "destination":     destination,
            "top_attractions": attractions[:8],
            "restaurants":     restaurants[:6],
            "activities":      activities[:6],
            "hidden_gems":     [],
            "places_summary":  (
                f"Found {len(attractions)} attractions, "
                f"{len(restaurants)} restaurants, "
                f"{len(activities)} activities in {destination}."
            ),
        }

    except Exception as e:
        logger.error("[LiveAPI] Geoapify places failed for %s: %s", destination, e)
        return None


def _cat_to_type(cat_str: str) -> str:
    if "beach"     in cat_str: return "beach"
    if "museum"    in cat_str: return "cultural"
    if "heritage"  in cat_str: return "heritage"
    if "sport"     in cat_str: return "adventure"
    if "nightclub" in cat_str: return "nightlife"
    if "entertain" in cat_str: return "entertainment"
    if "nature"    in cat_str: return "nature"
    if "religion"  in cat_str: return "religious"
    return "sightseeing"


# ══════════════════════════════════════════════════════════════════════════════
# 3. ROUTE DISTANCE  —  OpenRouteService
# ══════════════════════════════════════════════════════════════════════════════

@traceable(name="fetch_route_distance", run_type="tool",
           metadata={"api": "OpenRouteService"})   
def fetch_route_distance(origin: str,
                         destination: str,
                         transport_preference: str = "") -> Optional[Dict[str, Any]]:
    """
    Get real driving distance and duration between two cities.
    transport_preference: if set to 'car', always recommend 'car' regardless of distance.
    """
    if not OPENROUTE_KEY:
        logger.warning("No OPENROUTE_API_KEY — skipping live route")
        return None

    origin_coords = geocode_city(origin)
    dest_coords   = geocode_city(destination)

    if not origin_coords or not dest_coords:
        return None

    try:
        r = requests.get(
            "https://api.openrouteservice.org/v2/directions/driving-car",
            params={
                "api_key": OPENROUTE_KEY,
                "start":   f"{origin_coords[1]},{origin_coords[0]}",
                "end":     f"{dest_coords[1]},{dest_coords[0]}",
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()

        features = data.get("features", [])
        if not features:
            return None

        summary  = features[0]["properties"]["segments"][0]
        dist_km  = round(summary["distance"] / 1000, 1)
        dur_hrs  = round(summary["duration"] / 3600, 1)

        # Respect user transport preference if specified
        pref = transport_preference.lower().strip()
        if pref in ("car", "drive", "road"):
            recommended = "car"
            est_cost    = dist_km * 4   # INR/km fuel estimate
        elif pref in ("bus",):
            recommended = "bus"
            est_cost    = dist_km * 1.2
        elif pref in ("train",):
            recommended = "train"
            est_cost    = dist_km * 0.8
        elif pref in ("flight", "fly"):
            recommended = "flight"
            est_cost    = max(2500, dist_km * 3.5)
        else:
            # Auto-decide based on distance
            if dist_km < 150:
                recommended = "bus";    est_cost = dist_km * 1.2
            elif dist_km < 800:
                recommended = "train";  est_cost = dist_km * 0.8
            else:
                recommended = "flight"; est_cost = max(2500, dist_km * 3.5)

        result = {
            "source":             "OpenRouteService (live)",
            "origin":             origin,
            "destination":        destination,
            "distance_km":        dist_km,
            "road_duration_h":    dur_hrs,
            "recommended_mode":   recommended,
            "estimated_cost_inr": round(est_cost),
            "notes": (
                f"Road distance: {dist_km}km. "
                f"Drive time: {dur_hrs:.0f}h. "
                f"Recommended: {recommended}."
            ),
        }
        logger.info(
            "[LiveAPI] Route %s→%s: %.0fkm, %.1fh, mode=%s ✓",
            origin, destination, dist_km, dur_hrs, recommended
        )
        return result

    except Exception as e:
        logger.error("[LiveAPI] OpenRouteService failed %s→%s: %s", origin, destination, e)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 4. HOTEL PRICES  —  Xotelo (no key)
# ══════════════════════════════════════════════════════════════════════════════

def _xotelo_search_location(destination: str) -> Optional[str]:
    try:
        r = requests.get(
            "https://data.xotelo.com/api/search",
            params={"query": destination},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        results = r.json().get("result", {}).get("list", [])
        if results:
            key = results[0].get("key", "")
            logger.info("Xotelo location key for %s: %s", destination, key)
            return key
    except Exception as e:
        logger.warning("Xotelo location search failed: %s", e)
    return None

@traceable(name="fetch_hotel_prices", run_type="tool",
           metadata={"api": "Xotelo"})
def fetch_hotel_prices(destination: str,
                       check_in: str,
                       check_out: str,
                       limit: int = 10) -> Optional[List[Dict[str, Any]]]:
    """Fetch live hotel prices from Xotelo (no API key needed)."""
    location_key = _xotelo_search_location(destination)
    if not location_key:
        return None

    try:
        r = requests.get(
            "https://data.xotelo.com/api/list",
            params={"location_key": location_key, "offset": 0, "limit": limit},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        hotels_raw = r.json().get("result", {}).get("list", [])
        if not hotels_raw:
            return None

        hotels = []
        for h in hotels_raw[:limit]:
            hotel_key  = h.get("key", "")
            hotel_name = h.get("name", "")
            if not hotel_key or not hotel_name:
                continue
            try:
                rr = requests.get(
                    "https://data.xotelo.com/api/rates",
                    params={"hotel_key": hotel_key, "chk_in": check_in, "chk_out": check_out},
                    timeout=TIMEOUT,
                )
                rr.raise_for_status()
                rates_raw  = rr.json().get("result", {}).get("rates", [])
                rates      = {}
                best_price = None
                for rate in rates_raw:
                    platform = rate.get("name", "")
                    price    = rate.get("rate")
                    if price and platform:
                        rates[platform] = price
                        if best_price is None or price < best_price:
                            best_price = price
                if best_price:
                    hotels.append({
                        "name":       hotel_name,
                        "hotel_key":  hotel_key,
                        "best_price": best_price,
                        "currency":   "USD",
                        "rates":      rates,
                        "source":     "Xotelo (live)",
                    })
                    time.sleep(0.1)
            except Exception:
                pass

        logger.info("[LiveAPI] Xotelo: %d hotels with prices for %s ✓", len(hotels), destination)
        return hotels if hotels else None

    except Exception as e:
        logger.error("[LiveAPI] Xotelo list failed for %s: %s", destination, e)
        return None
