"""
tools/evaluation.py  —  Thrillophilia Trip Planner Evaluation Framework
=========================================================================
Custom evaluation framework purpose-built for an API-driven trip planner.

WHY NOT STANDARD RAGAS:
  RAGAS is designed for document-RAG systems with fixed ground truth.
  This system is API-driven — answers come from live OpenWeatherMap,
  Geoapify, OpenRouteService, Xotelo + GPT synthesis. No fixed ground truth exists.

WHAT WE EVALUATE (4 tracks):
  Track 1 — API Quality     : Did live APIs return real, usable data?
  Track 2 — Constraint Check: Did LLM respect user constraints?
  Track 3 — Faithfulness    : Did LLM use API data or hallucinate?
  Track 4 — Completeness    : Is the output complete and usable?

USAGE:
  from tools.evaluation import evaluate_trip_result, render_evaluation_dashboard
  report = evaluate_trip_result(result, prefs)
  render_evaluation_dashboard(report)   # inside Streamlit
  print(report.summary())               # CLI
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("trip_planner.evaluation")


# ─────────────────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TrackResult:
    name:        str
    score:       float
    passed:      bool
    checks:      List[str]
    passed_list: List[str]
    failed_list: List[str]
    details:     Dict[str, Any] = field(default_factory=dict)

    @property
    def pct(self) -> int:
        return int(self.score * 100)


@dataclass
class EvaluationReport:
    timestamp:    float
    destination:  str
    num_days:     int
    budget:       float
    currency:     str
    api_quality:  TrackResult
    constraints:  TrackResult
    faithfulness: TrackResult
    completeness: TrackResult

    @property
    def overall_score(self) -> float:
        return round(
            0.20 * self.api_quality.score +
            0.35 * self.constraints.score +
            0.25 * self.faithfulness.score +
            0.20 * self.completeness.score,
            3
        )

    @property
    def overall_pct(self) -> int:
        return int(self.overall_score * 100)

    @property
    def grade(self) -> str:
        s = self.overall_pct
        if s >= 90: return "A"
        if s >= 75: return "B"
        if s >= 60: return "C"
        if s >= 45: return "D"
        return "F"

    def summary(self) -> str:
        lines = [
            "═══ Thrillophilia Trip Evaluation ═══",
            f"Destination : {self.destination} ({self.num_days} days)",
            f"Budget      : {self.currency} {self.budget:,.0f}",
            f"Overall     : {self.overall_pct}/100  Grade: {self.grade}",
            "",
            f"  API Quality    : {self.api_quality.pct}/100",
            f"  Constraints    : {self.constraints.pct}/100",
            f"  Faithfulness   : {self.faithfulness.pct}/100",
            f"  Completeness   : {self.completeness.pct}/100",
        ]
        all_failures = (
            self.api_quality.failed_list +
            self.constraints.failed_list +
            self.faithfulness.failed_list +
            self.completeness.failed_list
        )
        if all_failures:
            lines.append("\nIssues found:")
            for f in all_failures:
                lines.append(f"  * {f}")
        else:
            lines.append("\nAll checks passed")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "destination": self.destination,
            "num_days": self.num_days,
            "budget": self.budget,
            "currency": self.currency,
            "overall_score": self.overall_score,
            "overall_pct": self.overall_pct,
            "grade": self.grade,
            "tracks": {
                "api_quality":  {"score": self.api_quality.score,  "pct": self.api_quality.pct,  "failed": self.api_quality.failed_list},
                "constraints":  {"score": self.constraints.score,  "pct": self.constraints.pct,  "failed": self.constraints.failed_list},
                "faithfulness": {"score": self.faithfulness.score, "pct": self.faithfulness.pct, "failed": self.faithfulness.failed_list},
                "completeness": {"score": self.completeness.score, "pct": self.completeness.pct, "failed": self.completeness.failed_list},
            }
        }


# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _f(val, default: float = 0.0) -> float:
    try:    return float(val)
    except: return default

def _track(name: str, results: List[Tuple[str, bool, str]]) -> TrackResult:
    checks      = [r[0] for r in results]
    passed_list = [r[0] for r in results if r[1]]
    failed_list = [f"{r[0]}: {r[2]}" for r in results if not r[1]]
    score       = len(passed_list) / max(len(checks), 1)
    return TrackResult(
        name=name, score=round(score, 3),
        passed=(len(failed_list) == 0),
        checks=checks, passed_list=passed_list, failed_list=failed_list,
    )


# ─────────────────────────────────────────────────────────────────────────────
# TRACK 1 — API QUALITY
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_api_quality(result: Dict[str, Any]) -> TrackResult:
    checks = []
    weather   = result.get("weather_data", {})
    transport = result.get("transport_data", {})
    places    = result.get("places_data", {})
    hotel     = result.get("hotel_data", {})

    # Weather
    w_source = weather.get("source", "").lower()
    checks.append(("weather_live",
        any(s in w_source for s in ["openweathermap","open-meteo","live"]),
        f"Weather source='{weather.get('source','none')}' — not a live API"))
    checks.append(("weather_data_complete",
        bool(weather.get("avg_temp_day") and weather.get("conditions")),
        "Weather missing avg_temp_day or conditions"))
    checks.append(("geocoding_success",
        bool(weather.get("lat") and weather.get("lon")),
        "No lat/lon in weather data"))

    # Transport / Route
    live_route = transport.get("live_route", {})
    dist_km    = _f(live_route.get("distance_km", 0))
    checks.append(("route_distance_live",
        dist_km > 0,
        "OpenRouteService not used — using LLM estimate"))
    if dist_km > 0:
        checks.append(("route_distance_realistic",
            0 < dist_km < 20000,
            f"Route distance {dist_km:.0f}km seems unrealistic"))

    # Places
    p_source = places.get("source", "").lower()
    p_count  = len(places.get("top_attractions", []))
    checks.append(("places_live",
        "geoapify" in p_source,
        f"Places source='{places.get('source','none')}' — not Geoapify"))
    checks.append(("places_count",
        p_count >= 3,
        f"Only {p_count} attractions returned"))

    # Hotels
    h_source = hotel.get("source", "").lower()
    checks.append(("hotels_live",
        "xotelo" in h_source,
        "Hotel prices from Xotelo not available"))

    return _track("API Quality", checks)


# ─────────────────────────────────────────────────────────────────────────────
# TRACK 2 — CONSTRAINT CHECKING
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_constraints(result: Dict[str, Any], prefs: Dict[str, Any]) -> TrackResult:
    checks   = []
    budget   = _f(prefs.get("budget", 0))
    num_days = int(prefs.get("num_days", 0) or 0)
    dest     = (prefs.get("destination") or "").lower().strip()
    currency = prefs.get("currency", "INR")
    t_pref   = (prefs.get("transport_preference") or "").lower()
    travelers= int(prefs.get("travelers", 0) or 0)

    budget_data = result.get("budget_summary", {})
    itin        = result.get("itinerary", {})
    hotel       = result.get("hotel_data", {})
    transport   = result.get("transport_data", {})
    days        = itin.get("days", [])

    # 1. Budget constraint
    if budget > 0:
        estimated = _f(budget_data.get("breakdown", {}).get("estimated_total", 0))
        checks.append(("budget_respected",
            estimated <= budget * 1.10,
            f"Estimated {currency}{estimated:,.0f} exceeds budget {currency}{budget:,.0f} (+10% tolerance)"))

    # 2. Day count
    if num_days > 0:
        days_got = len(days)
        checks.append(("itinerary_not_empty",
            days_got > 0,
            "Itinerary has 0 days"))
        checks.append(("correct_day_count",
            days_got == num_days,
            f"Itinerary has {days_got} days, expected {num_days}"))

    # 3. Destination present
    if dest and days:
        itin_text = str(itin).lower()
        mentioned = dest in itin_text or any(
            w in itin_text for w in dest.split() if len(w) > 3
        )
        checks.append(("destination_in_itinerary",
            mentioned,
            f"'{dest}' not found in itinerary content"))

    # 4. Hotel within 40% budget slice
    if budget > 0 and num_days > 0:
        max_ppn   = (budget * 0.40) / num_days
        hotel_rec = hotel.get("recommended_hotel", {})
        ppn       = _f(hotel_rec.get("price_per_night", 0))
        if ppn > 0:
            checks.append(("hotel_within_budget",
                ppn <= max_ppn * 1.15,
                f"Hotel {currency}{ppn:,.0f}/night > max {currency}{max_ppn:,.0f}/night"))

    # 5. Transport preference honoured
    if t_pref and t_pref not in ("any",):
        act_mode = (transport.get("primary_option", {}).get("mode") or "").lower()
        checks.append(("transport_preference_honoured",
            t_pref in act_mode or act_mode in t_pref,
            f"Preferred '{t_pref}' but got '{act_mode}'"))

    # 6. Traveler cost sanity
    if travelers > 0:
        food_cost = _f(budget_data.get("breakdown", {}).get("food", 0))
        per_head  = food_cost / travelers if travelers else food_cost
        checks.append(("traveler_cost_realistic",
            100 <= per_head <= 100_000,
            f"Food cost per person {currency}{per_head:,.0f} seems unrealistic"))

    return _track("Constraints", checks)


# ─────────────────────────────────────────────────────────────────────────────
# TRACK 3 — FAITHFULNESS
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_faithfulness(result: Dict[str, Any], prefs: Dict[str, Any]) -> TrackResult:
    checks    = []
    currency  = prefs.get("currency", "INR")
    weather   = result.get("weather_data", {})
    transport = result.get("transport_data", {})
    hotel     = result.get("hotel_data", {})
    places    = result.get("places_data", {})
    itin      = result.get("itinerary", {})
    budget    = result.get("budget_summary", {})

    # 1. Transport mode faithful to live route
    live_route = transport.get("live_route", {})
    prim       = transport.get("primary_option", {})
    rec_mode   = (live_route.get("recommended_mode") or "").lower()
    act_mode   = (prim.get("mode") or "").lower()
    if rec_mode and act_mode:
        faithful = (rec_mode == act_mode or
                    (rec_mode in ("train","bus") and act_mode in ("train","bus")))
        checks.append(("transport_mode_faithful",
            faithful,
            f"Live route recommends '{rec_mode}' but plan uses '{act_mode}'"))

    # 2. Hotel prices non-zero
    opts = hotel.get("hotel_options", [])
    if opts:
        checks.append(("hotel_prices_nonzero",
            all(_f(o.get("price_per_night",0)) > 0 for o in opts),
            "Hotel option(s) have price_per_night=0"))
        min_ppn = min(_f(o.get("price_per_night",0)) for o in opts)
        too_cheap = (currency == "INR" and min_ppn < 200) or (currency != "INR" and min_ppn < 5)
        checks.append(("hotel_prices_realistic",
            not too_cheap,
            f"Cheapest hotel {currency}{min_ppn:,.0f}/night — likely hallucinated"))

    # 3. Budget fields non-zero
    bd = budget.get("breakdown", {})
    for f_name in ("transport", "accommodation", "food"):
        checks.append((f"budget_{f_name}_nonzero",
            _f(bd.get(f_name,0)) > 0,
            f"Budget '{f_name}'=0"))

    # 4. Live place names in itinerary
    live_att = [a.get("name","") for a in places.get("top_attractions",[])[:5]]
    if live_att:
        itin_text   = str(itin).lower()
        found       = [n for n in live_att if n.lower() in itin_text]
        checks.append(("live_places_in_itinerary",
            len(found) > 0,
            f"None of {live_att[:3]} appear in itinerary"))

    # 5. Weather consistency
    outdoor_ok   = weather.get("outdoor_suitable", True)
    itin_text    = str(itin).lower()
    beach_plan   = any(w in itin_text for w in ("beach","swim","snorkel","water sport"))
    conditions   = weather.get("conditions","")
    if not outdoor_ok and beach_plan:
        checks.append(("weather_consistent_with_plan",
            False,
            f"Weather={conditions} (not outdoor-suitable) but plan has beach activities"))
    elif conditions:
        checks.append(("weather_consistent_with_plan", True, ""))

    # 6. Transport price realistic
    dist_km  = _f(live_route.get("distance_km",0))
    price_pp = _f(prim.get("price_per_person",0))
    mode     = (prim.get("mode") or "").lower()
    if dist_km > 500 and price_pp > 0 and "flight" in mode:
        if currency == "INR":
            realistic = 1500 <= price_pp <= 50_000
        else:
            realistic = 50 <= price_pp <= 2000
        checks.append(("transport_price_realistic",
            realistic,
            f"Flight {currency}{price_pp:,.0f}/person for {dist_km:.0f}km route"))

    return _track("Faithfulness", checks)


# ─────────────────────────────────────────────────────────────────────────────
# TRACK 4 — COMPLETENESS
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_completeness(result: Dict[str, Any], prefs: Dict[str, Any]) -> TrackResult:
    checks    = []
    itin      = result.get("itinerary", {})
    transport = result.get("transport_data", {})
    hotel     = result.get("hotel_data", {})
    places    = result.get("places_data", {})
    weather   = result.get("weather_data", {})
    budget    = result.get("budget_summary", {})
    days      = itin.get("days", [])
    prim      = transport.get("primary_option", {})

    # Itinerary
    checks.append(("has_days",          len(days) > 0,                              "0 itinerary days"))
    checks.append(("has_trip_title",    bool(itin.get("trip_title")),               "No trip title"))
    checks.append(("has_packing_list",  len(itin.get("packing_checklist",[])) > 0,  "No packing checklist"))
    checks.append(("has_travel_tips",   len(itin.get("travel_tips",[])) > 0,        "No travel tips"))
    checks.append(("has_emergency",     bool(itin.get("emergency_contacts")),       "No emergency contacts"))

    if days:
        req   = {"morning","afternoon","meals","accommodation"}
        full  = sum(1 for d in days if req.issubset(d.keys()))
        checks.append(("days_fully_populated",
            full / len(days) >= 0.8,
            f"Only {full}/{len(days)} days fully populated"))

    # Transport
    checks.append(("has_transport_mode",  bool(prim.get("mode")),                  "No transport mode"))
    checks.append(("has_transport_price", _f(prim.get("price_per_person",0)) > 0,  "Transport price=0"))
    checks.append(("has_local_transport", bool(transport.get("local_transport")),  "No local transport"))

    # Hotels
    opts = hotel.get("hotel_options", [])
    checks.append(("has_hotel_options",   len(opts) >= 2,                          f"Only {len(opts)} hotel options"))
    checks.append(("has_hotel_amenities", any(o.get("amenities") for o in opts),   "No hotel amenities"))

    # Places
    att_count  = len(places.get("top_attractions",[]))
    rest_count = len(places.get("restaurants",[]))
    checks.append(("has_attractions",  att_count >= 3,   f"Only {att_count} attractions"))
    checks.append(("has_restaurants",  rest_count >= 1,  "No restaurants listed"))

    # Weather
    checks.append(("has_weather_summary", bool(weather.get("weather_summary")), "No weather summary"))
    checks.append(("has_clothing_advice", bool(weather.get("clothing_advice")), "No clothing advice"))

    # Budget
    bd = budget.get("breakdown", {})
    checks.append(("has_budget_breakdown",  bool(bd),                                    "No budget breakdown"))
    checks.append(("has_cost_tips",         len(budget.get("optimization_tips",[])) > 0, "No cost tips"))

    # PDF
    checks.append(("pdf_generated", bool(result.get("pdf_path")), "PDF not generated"))

    return _track("Completeness", checks)


# ══════════════════════════════════════════════════════════════════════════════
# MASTER EVALUATOR
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_trip_result(result: Dict[str, Any],
                         prefs:  Dict[str, Any] = None) -> EvaluationReport:
    """
    Run all 4 evaluation tracks. Returns EvaluationReport with overall grade.
    """
    if prefs is None:
        prefs = result.get("trip_preferences", {})

    logger.info("[Evaluation] Evaluating trip for %s (%s days)",
                prefs.get("destination","?"), prefs.get("num_days","?"))
    t0 = time.time()

    api_q  = evaluate_api_quality(result)
    constr = evaluate_constraints(result, prefs)
    faith  = evaluate_faithfulness(result, prefs)
    compl  = evaluate_completeness(result, prefs)

    overall = int((api_q.score*0.2 + constr.score*0.35 + faith.score*0.25 + compl.score*0.2)*100)
    logger.info(
        "[Evaluation] Done in %.2fs — Overall:%d%% API:%d%% Constraints:%d%% Faith:%d%% Complete:%d%%",
        time.time()-t0, overall, api_q.pct, constr.pct, faith.pct, compl.pct
    )

    return EvaluationReport(
        timestamp    = t0,
        destination  = prefs.get("destination","Unknown"),
        num_days     = int(prefs.get("num_days",0) or 0),
        budget       = float(prefs.get("budget",0) or 0),
        currency     = prefs.get("currency","INR"),
        api_quality  = api_q,
        constraints  = constr,
        faithfulness = faith,
        completeness = compl,
    )


# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT DASHBOARD RENDERER
# ══════════════════════════════════════════════════════════════════════════════

def render_evaluation_dashboard(report: EvaluationReport):
    """
    Render evaluation results as a Streamlit dashboard inside an expander.
    Call from app.py after a trip plan is complete.
    """
    try:
        import streamlit as st
    except ImportError:
        print(report.summary())
        return

    grade_color = {
        "A":"#2E7D52","B":"#1A4A8A","C":"#C9A84C","D":"#B07020","F":"#B02A2A"
    }.get(report.grade, "#888")

    with st.expander(
        f"📊 Quality Evaluation — {report.overall_pct}/100  Grade: {report.grade}",
        expanded=False
    ):
        # Overall banner
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#1A1400,#252510);'
            f'border:2px solid {grade_color};border-radius:12px;'
            f'padding:1rem 1.3rem;margin-bottom:1rem;display:flex;justify-content:space-between;">'
            f'<div>'
            f'<div style="color:#F0EAD6;font-size:1rem;font-weight:700;">Trip Quality Score</div>'
            f'<div style="color:#888;font-size:0.8rem;">'
            f'{report.destination} · {report.num_days} days · {report.currency} {report.budget:,.0f}</div>'
            f'</div>'
            f'<div style="text-align:right;">'
            f'<div style="font-size:2rem;font-weight:900;color:{grade_color};">{report.overall_pct}</div>'
            f'<div style="color:{grade_color};font-weight:700;">Grade {report.grade}</div>'
            f'</div></div>',
            unsafe_allow_html=True
        )

        # 4 track score cards
        tracks = [
            ("🔌 API Quality",  report.api_quality,  "#1A4A8A"),
            ("✅ Constraints",  report.constraints,  "#2E7D52"),
            ("🎯 Faithfulness", report.faithfulness, "#C9A84C"),
            ("📋 Completeness", report.completeness, "#8B5CF6"),
        ]
        cols = st.columns(4)
        for col, (label, track, color) in zip(cols, tracks):
            col.markdown(
                f'<div style="background:#1E1E1E;border:1px solid {color}40;'
                f'border-radius:10px;padding:0.8rem;text-align:center;">'
                f'<div style="color:{color};font-size:1.4rem;font-weight:800;">{track.pct}%</div>'
                f'<div style="color:#888;font-size:0.7rem;">{label}</div>'
                f'<div style="color:{"#2E7D52" if track.passed else "#B02A2A"};font-size:0.66rem;">'
                f'{"✓ PASSED" if track.passed else "✗ ISSUES"}</div></div>',
                unsafe_allow_html=True
            )

        # Progress bars
        st.markdown("<br>", unsafe_allow_html=True)
        for label, track, color in tracks:
            n_pass = len(track.passed_list)
            n_total= len(track.checks)
            st.markdown(
                f'<div style="margin-bottom:0.5rem;">'
                f'<div style="display:flex;justify-content:space-between;font-size:0.8rem;margin-bottom:2px;">'
                f'<span style="color:#F0EAD6;">{label}</span>'
                f'<span style="color:{color};font-weight:700;">{track.pct}% ({n_pass}/{n_total})</span>'
                f'</div>'
                f'<div style="background:#2E2E2E;border-radius:4px;height:6px;">'
                f'<div style="background:{color};width:{track.pct}%;height:6px;border-radius:4px;"></div>'
                f'</div></div>',
                unsafe_allow_html=True
            )

        # Issues
        all_failures = (
            report.api_quality.failed_list + report.constraints.failed_list +
            report.faithfulness.failed_list + report.completeness.failed_list
        )
        if all_failures:
            st.markdown(
                '<div style="color:#B02A2A;font-weight:700;font-size:0.83rem;margin:0.7rem 0 0.3rem;">⚠️ Issues</div>',
                unsafe_allow_html=True
            )
            for issue in all_failures:
                st.markdown(
                    f'<div style="background:#1F0D0D;border:1px solid #B02A2A30;border-radius:6px;'
                    f'padding:0.3rem 0.7rem;margin-bottom:0.2rem;font-size:0.78rem;color:#FFB3B3;">⚠ {issue}</div>',
                    unsafe_allow_html=True
                )
        else:
            st.success("✅ All evaluation checks passed!")

        with st.expander("✅ Passed checks"):
            all_passed = (
                report.api_quality.passed_list + report.constraints.passed_list +
                report.faithfulness.passed_list + report.completeness.passed_list
            )
            c1, c2 = st.columns(2)
            for i, check in enumerate(all_passed):
                (c1 if i%2==0 else c2).markdown(
                    f'<div style="color:#2E7D52;font-size:0.76rem;padding:1px 0;">✓ {check}</div>',
                    unsafe_allow_html=True
                )
