"""
tools/pdf_generator.py — Professional PDF Report Generator
===========================================================
Uses ReportLab to produce a polished, multi-section PDF travel report.

Sections:
  1. Cover Page
  2. Trip Summary
  3. Flights & Transport
  4. Hotel Details
  5. Day-wise Itinerary
  6. Budget Report
  7. Packing Checklist
  8. Emergency Contacts & Travel Tips
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import PDF_OUTPUT_DIR
from state import TripState

logger = logging.getLogger("trip_planner.pdf")


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def generate_pdf(state: TripState) -> Dict[str, Any]:
    """
    Generate a professional PDF report from the trip plan state.
    Returns updated pdf_status and pdf_path.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.colors import HexColor, white, black
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, PageBreak,
        )
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    except ImportError as e:
        logger.error("ReportLab not installed: %s", e)
        return {"pdf_status": {"generated": False, "error": str(e)}, "pdf_path": None}

    # ── Extract state data ────────────────────────────────────────────────────
    prefs = state.get("trip_preferences", {})
    weather = state.get("weather_data", {})
    transport = state.get("transport_data", {})
    hotel = state.get("hotel_data", {})
    places = state.get("places_data", {})
    budget = state.get("budget_summary", {})
    itinerary = state.get("itinerary", {})
    review = state.get("review_status", {})

    destination = prefs.get("destination", "Your Destination")
    source = prefs.get("source", "Origin")
    num_days = prefs.get("num_days", 5)
    currency = prefs.get("currency", "INR")
    total_budget = _safe_float(prefs.get("budget", 0))
    travel_type = prefs.get("travel_type", "trip")
    travelers = prefs.get("travelers", 2)
    trip_title = itinerary.get("trip_title", f"{num_days}-Day {destination} Trip")

    # ── Filename — sanitise all characters Windows/Linux rejects ────────────
    import re
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Use only the extracted destination field, not the raw query (max 30 chars)
    raw_dest = str(destination)[:30]
    safe_dest = re.sub(r'[^\w\-]', '_', raw_dest)   # keep letters, digits, _ and -
    safe_dest = re.sub(r'_+', '_', safe_dest).strip('_')  # collapse repeated underscores
    safe_dest = safe_dest or "Trip"                    # fallback if still empty
    filename = f"TripPlan_{safe_dest}_{ts}.pdf"
    filepath = Path(PDF_OUTPUT_DIR) / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # ── Colour palette ────────────────────────────────────────────────────────
    BRAND_BLUE = HexColor("#1A73E8")
    BRAND_TEAL = HexColor("#0D9488")
    LIGHT_GREY = HexColor("#F8FAFC")
    MID_GREY = HexColor("#64748B")
    DARK = HexColor("#1E293B")
    ACCENT = HexColor("#F59E0B")

    # ── Document ──────────────────────────────────────────────────────────────
    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    story = []

    # Custom styles
    def style(name, **kwargs):
        s = ParagraphStyle(name, **kwargs)
        return s

    h1 = style("H1", fontSize=28, textColor=white, fontName="Helvetica-Bold",
               alignment=TA_CENTER, spaceAfter=6)
    h2 = style("H2", fontSize=16, textColor=BRAND_BLUE, fontName="Helvetica-Bold",
               spaceBefore=14, spaceAfter=6)
    h3 = style("H3", fontSize=12, textColor=BRAND_TEAL, fontName="Helvetica-Bold",
               spaceBefore=8, spaceAfter=4)
    body = style("Body", fontSize=10, textColor=DARK, fontName="Helvetica",
                 spaceBefore=2, spaceAfter=2, leading=14)
    small = style("Small", fontSize=9, textColor=MID_GREY, fontName="Helvetica",
                  spaceBefore=2, spaceAfter=2)
    centre = style("Centre", fontSize=11, textColor=MID_GREY, fontName="Helvetica",
                   alignment=TA_CENTER, spaceBefore=4)

    # ─── COVER PAGE ──────────────────────────────────────────────────────────
    cover_table = Table(
        [[Paragraph(f"✈ AI TRAVEL PLANNER", style("CoverTop", fontSize=13, textColor=white,
                    fontName="Helvetica", alignment=TA_CENTER))]],
        colWidths=[17*cm], rowHeights=[0.8*cm],
    )
    cover_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), BRAND_TEAL),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ROUNDEDCORNERS", [8]),
    ]))
    story.append(cover_table)
    story.append(Spacer(1, 1*cm))

    title_box = Table(
        [
            [Paragraph(trip_title, h1)],
            [Paragraph(f"{source}  →  {destination}", style("Sub", fontSize=15,
              textColor=white, fontName="Helvetica", alignment=TA_CENTER))],
            [Paragraph(f"{travel_type.title()} | {travelers} Traveller(s) | {num_days} Days",
              style("Sub2", fontSize=12, textColor=HexColor("#CBD5E1"), fontName="Helvetica",
                    alignment=TA_CENTER))],
        ],
        colWidths=[17*cm],
    )
    title_box.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), BRAND_BLUE),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING", (0,0), (-1,-1), 20),
        ("BOTTOMPADDING", (0,0), (-1,-1), 20),
        ("ROUNDEDCORNERS", [12]),
    ]))
    story.append(title_box)
    story.append(Spacer(1, 0.5*cm))

    # Key info boxes
    info_data = [
        ["📅 Dates", f"{prefs.get('start_date','TBD')} – {prefs.get('end_date','TBD')}"],
        ["💰 Budget", f"{currency} {total_budget:,.0f}"],
        ["🏨 Stay", hotel.get("recommended_hotel", {}).get("name", "TBD")],
        ["🌤️ Weather", weather.get("conditions", "N/A").title()],
    ]
    info_table = Table(info_data, colWidths=[5*cm, 12*cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), LIGHT_GREY),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME", (1,0), (1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("TEXTCOLOR", (0,0), (0,-1), BRAND_BLUE),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [white, LIGHT_GREY]),
        ("GRID", (0,0), (-1,-1), 0.5, HexColor("#E2E8F0")),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph(
        f"Generated by AI Trip Planner • {datetime.now().strftime('%d %B %Y %H:%M')}",
        style("Gen", fontSize=9, textColor=MID_GREY, alignment=TA_CENTER)
    ))
    story.append(PageBreak())

    # ─── SECTION 1: WEATHER ───────────────────────────────────────────────────
    story.append(Paragraph("1. Weather Report", h2))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_BLUE))
    story.append(Spacer(1, 0.2*cm))
    if weather:
        weather_rows = [
            ["Condition", weather.get("conditions", "N/A").title()],
            ["Daytime Temp", weather.get("avg_temp_day", "N/A")],
            ["Night Temp", weather.get("avg_temp_night", "N/A")],
            ["Rainfall", weather.get("rainfall", "N/A").title()],
            ["Beach Suitable", "✅ Yes" if weather.get("beach_suitable") else "❌ No"],
            ["Outdoor Activities", "✅ Yes" if weather.get("outdoor_suitable") else "❌ No"],
            ["Clothing Advice", weather.get("clothing_advice", "N/A")],
        ]
        w_table = Table(weather_rows, colWidths=[5*cm, 12*cm])
        w_table.setStyle(TableStyle([
            ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
            ("FONTNAME", (1,0), (1,-1), "Helvetica"),
            ("FONTSIZE", (0,0), (-1,-1), 10),
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [white, LIGHT_GREY]),
            ("GRID", (0,0), (-1,-1), 0.5, HexColor("#E2E8F0")),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
        ]))
        story.append(w_table)
        if weather.get("weather_summary"):
            story.append(Spacer(1, 0.2*cm))
            story.append(Paragraph(weather["weather_summary"], body))
    story.append(PageBreak())

    # ─── SECTION 2: TRANSPORT ─────────────────────────────────────────────────
    story.append(Paragraph("2. Flights & Transport", h2))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_BLUE))
    story.append(Spacer(1, 0.2*cm))

    primary = transport.get("primary_option", {})
    if primary:
        story.append(Paragraph("Primary Option", h3))
        t_rows = [
            ["Mode", primary.get("mode","N/A").title()],
            ["Operator", primary.get("operator","N/A")],
            ["Duration", primary.get("duration","N/A")],
            ["Price / Person", f"{currency} {_safe_float(primary.get('price_per_person',0)):,.0f}"],
            ["Total Cost", f"{currency} {_safe_float(primary.get('total_price',0)):,.0f}"],
            ["Schedule", primary.get("schedule","N/A")],
            ["Book via", primary.get("booking_platform","N/A")],
        ]
        t_table = Table(t_rows, colWidths=[5*cm, 12*cm])
        t_table.setStyle(TableStyle([
            ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
            ("FONTNAME", (1,0), (1,-1), "Helvetica"),
            ("FONTSIZE", (0,0), (-1,-1), 10),
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [white, LIGHT_GREY]),
            ("GRID", (0,0), (-1,-1), 0.5, HexColor("#E2E8F0")),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
        ]))
        story.append(t_table)

    # Alternatives
    alts = transport.get("alternative_options", [])
    if alts:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph("Alternative Options", h3))
        alt_rows = [["Mode", "Cost/Person", "Duration", "Notes"]]
        for a in alts[:3]:
            alt_rows.append([
                a.get("mode","N/A").title(),
                f"{currency} {_safe_float(a.get('price_per_person',0)):,.0f}",
                a.get("duration","N/A"),
                a.get("notes","N/A")[:50],
            ])
        alt_table = Table(alt_rows, colWidths=[3*cm, 3.5*cm, 3.5*cm, 7*cm])
        alt_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), BRAND_BLUE),
            ("TEXTCOLOR", (0,0), (-1,0), white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, LIGHT_GREY]),
            ("GRID", (0,0), (-1,-1), 0.5, HexColor("#E2E8F0")),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(alt_table)

    # Local transport
    local_t = transport.get("local_transport", {})
    if local_t:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph("Local Transport", h3))
        story.append(Paragraph(
            f"Recommended: <b>{local_t.get('recommended','taxi').title()}</b> | "
            f"Daily cost: <b>{currency} {_safe_float(local_t.get('daily_cost',0)):,.0f}</b> | "
            f"Total: <b>{currency} {_safe_float(local_t.get('total_local_cost',0)):,.0f}</b>",
            body
        ))
        if local_t.get("tips"):
            story.append(Paragraph(f"Tip: {local_t['tips']}", small))
    story.append(PageBreak())

    # ─── SECTION 3: HOTEL ─────────────────────────────────────────────────────
    story.append(Paragraph("3. Accommodation", h2))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_BLUE))
    story.append(Spacer(1, 0.2*cm))

    rec = hotel.get("recommended_hotel", {})
    if rec:
        story.append(Paragraph(f"⭐ Recommended: {rec.get('name','N/A')}", h3))
        h_rows = [
            ["Category", rec.get("category","N/A")],
            ["Location", rec.get("location","N/A")],
            ["Rating", f"⭐ {rec.get('rating','N/A')} / 5"],
            ["Price/Night", f"{currency} {_safe_float(rec.get('price_per_night',0)):,.0f}"],
            ["Total Cost", f"{currency} {_safe_float(rec.get('total_cost',0)):,.0f} ({num_days} nights)"],
            ["Book via", rec.get("booking_url","MakeMyTrip / Booking.com")],
        ]
        h_table = Table(h_rows, colWidths=[5*cm, 12*cm])
        h_table.setStyle(TableStyle([
            ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
            ("FONTNAME", (1,0), (1,-1), "Helvetica"),
            ("FONTSIZE", (0,0), (-1,-1), 10),
            ("ROWBACKGROUNDS", (0,0), (-1,-1), [white, LIGHT_GREY]),
            ("GRID", (0,0), (-1,-1), 0.5, HexColor("#E2E8F0")),
            ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
        ]))
        story.append(h_table)
        amenities = rec.get("amenities", [])
        if amenities:
            story.append(Spacer(1, 0.2*cm))
            story.append(Paragraph(f"<b>Amenities:</b> {', '.join(amenities)}", body))
        if rec.get("why_recommended"):
            story.append(Paragraph(f"<b>Why:</b> {rec['why_recommended']}", small))

    # Alternatives
    h_alts = hotel.get("alternatives", [])
    if h_alts:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph("Budget Alternatives", h3))
        for alt in h_alts[:3]:
            story.append(Paragraph(
                f"• <b>{alt.get('name','N/A')}</b> ({alt.get('category','N/A')}) — "
                f"{currency} {_safe_float(alt.get('price_per_night',0)):,.0f}/night — {alt.get('notes','')}",
                body
            ))
    story.append(PageBreak())

    # ─── SECTION 4: ITINERARY ─────────────────────────────────────────────────
    story.append(Paragraph("4. Day-Wise Itinerary", h2))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_BLUE))

    for day_plan in itinerary.get("days", []):
        story.append(Spacer(1, 0.3*cm))
        day_num = day_plan.get("day", "?")
        theme = day_plan.get("theme", "")
        day_header = Table(
            [[Paragraph(f"Day {day_num}: {theme}", style("DH", fontSize=12,
               textColor=white, fontName="Helvetica-Bold", alignment=TA_LEFT))]],
            colWidths=[17*cm],
        )
        day_header.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), BRAND_TEAL),
            ("TOPPADDING", (0,0), (-1,-1), 7),
            ("BOTTOMPADDING", (0,0), (-1,-1), 7),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
            ("ROUNDEDCORNERS", [4]),
        ]))
        story.append(day_header)

        schedule_rows = [["Time", "Activity", "Location"]]
        for period, emoji in [("morning","🌅"), ("afternoon","☀️"), ("evening","🌇"), ("night","🌙")]:
            block = day_plan.get(period, {})
            if block:
                schedule_rows.append([
                    f"{emoji} {period.title()}",
                    block.get("activity","")[:60],
                    block.get("location","")[:40],
                ])

        sched_table = Table(schedule_rows, colWidths=[3.5*cm, 9*cm, 4.5*cm])
        sched_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), LIGHT_GREY),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("GRID", (0,0), (-1,-1), 0.5, HexColor("#E2E8F0")),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
        ]))
        story.append(sched_table)

        meals = day_plan.get("meals", {})
        if meals:
            meal_str = " | ".join(f"<b>{k.title()}:</b> {v}" for k,v in meals.items() if v)
            story.append(Paragraph(f"🍽️ {meal_str}", small))

        est_cost = _safe_float(day_plan.get("estimated_day_cost", 0))
        if est_cost:
            story.append(Paragraph(f"💰 Estimated day cost: {currency} {est_cost:,.0f}", small))

    story.append(PageBreak())

    # ─── SECTION 5: BUDGET ────────────────────────────────────────────────────
    story.append(Paragraph("5. Budget Report", h2))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_BLUE))
    story.append(Spacer(1, 0.2*cm))

    breakdown = budget.get("breakdown", {})
    if breakdown:
        b_rows = [
            ["Category", "Estimated Cost"],
            ["✈️ Transport", f"{currency} {_safe_float(breakdown.get('transport',0)):,.0f}"],
            ["🏨 Accommodation", f"{currency} {_safe_float(breakdown.get('accommodation',0)):,.0f}"],
            ["🍽️ Food & Dining", f"{currency} {_safe_float(breakdown.get('food',0)):,.0f}"],
            ["🎯 Activities", f"{currency} {_safe_float(breakdown.get('activities',0)):,.0f}"],
            ["🛍️ Miscellaneous", f"{currency} {_safe_float(breakdown.get('miscellaneous',0)):,.0f}"],
            ["TOTAL ESTIMATE", f"{currency} {_safe_float(breakdown.get('estimated_total',0)):,.0f}"],
            ["YOUR BUDGET", f"{currency} {total_budget:,.0f}"],
        ]
        b_table = Table(b_rows, colWidths=[10*cm, 7*cm])
        b_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), BRAND_BLUE),
            ("TEXTCOLOR", (0,0), (-1,0), white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTNAME", (0,1), (-1,-5), "Helvetica"),
            ("FONTNAME", (0,-2), (-1,-1), "Helvetica-Bold"),
            ("BACKGROUND", (0,-2), (-1,-2), LIGHT_GREY),
            ("BACKGROUND", (0,-1), (-1,-1), ACCENT),
            ("FONTSIZE", (0,0), (-1,-1), 10),
            ("ROWBACKGROUNDS", (0,1), (-1,-3), [white, LIGHT_GREY]),
            ("GRID", (0,0), (-1,-1), 0.5, HexColor("#E2E8F0")),
            ("TOPPADDING", (0,0), (-1,-1), 7),
            ("BOTTOMPADDING", (0,0), (-1,-1), 7),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
            ("ALIGN", (1,0), (1,-1), "RIGHT"),
        ]))
        story.append(b_table)

    surplus = budget.get("surplus_or_deficit", 0)
    status = budget.get("budget_status", "on_track")
    colour = BRAND_TEAL if surplus >= 0 else HexColor("#EF4444")
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f"<b>Status:</b> {status.replace('_',' ').title()} | "
        f"<b>Surplus / Deficit:</b> {currency} {_safe_float(surplus):,.0f}",
        style("BStatus", fontSize=11, textColor=colour, fontName="Helvetica-Bold")
    ))

    tips = budget.get("optimization_tips", [])
    if tips:
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph("<b>💡 Budget Optimization Tips:</b>", h3))
        for tip in tips[:5]:
            story.append(Paragraph(f"• {tip}", body))

    story.append(PageBreak())

    # ─── SECTION 6: PACKING & EMERGENCY ──────────────────────────────────────
    story.append(Paragraph("6. Packing Checklist", h2))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_BLUE))
    story.append(Spacer(1, 0.2*cm))

    checklist = itinerary.get("packing_checklist", [])
    if not checklist:
        checklist = [
            "Valid ID / Passport & copies",
            "Flight/train tickets (print + digital)",
            "Hotel booking confirmation",
            "Travel insurance documents",
            "Sunscreen & sunglasses",
            "Weather-appropriate clothing",
            "Power bank & universal adapter",
            "Basic first-aid kit & medicines",
            "Cash & forex card",
            "Offline maps (Maps.me)",
            "Reusable water bottle",
            "Camera / phone charger",
        ]

    mid = len(checklist) // 2
    col1 = checklist[:mid]
    col2 = checklist[mid:]
    max_len = max(len(col1), len(col2))
    col1 += [""] * (max_len - len(col1))
    col2 += [""] * (max_len - len(col2))

    pack_rows = [[Paragraph(f"☐ {a}", body), Paragraph(f"☐ {b}", body) if b else Paragraph("", body)]
                 for a, b in zip(col1, col2)]
    pack_table = Table(pack_rows, colWidths=[8.5*cm, 8.5*cm])
    pack_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [white, LIGHT_GREY]),
        ("GRID", (0,0), (-1,-1), 0.3, HexColor("#E2E8F0")),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(pack_table)

    # Emergency contacts
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph("7. Emergency Contacts & Travel Tips", h2))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_BLUE))
    story.append(Spacer(1, 0.2*cm))

    contacts = itinerary.get("emergency_contacts", {
        "Tourist Helpline": "1363",
        "Police": "100",
        "Ambulance": "108",
        "Fire": "101",
    })
    ec_rows = [["Service", "Number / Contact"]]
    for k, v in contacts.items():
        ec_rows.append([k, str(v)])

    ec_table = Table(ec_rows, colWidths=[8*cm, 9*cm])
    ec_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), HexColor("#EF4444")),
        ("TEXTCOLOR", (0,0), (-1,0), white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [white, LIGHT_GREY]),
        ("GRID", (0,0), (-1,-1), 0.5, HexColor("#E2E8F0")),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("LEFTPADDING", (0,0), (-1,-1), 10),
    ]))
    story.append(ec_table)

    travel_tips = itinerary.get("travel_tips", [])
    if travel_tips:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph("<b>Travel Tips:</b>", h3))
        for tip in travel_tips[:6]:
            story.append(Paragraph(f"• {tip}", body))

    # Footer
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=MID_GREY))
    story.append(Paragraph(
        f"Generated by AI Trip Planner using LangGraph + GPT-4o-Mini | {datetime.now().strftime('%d %B %Y')}",
        style("Footer", fontSize=8, textColor=MID_GREY, alignment=TA_CENTER)
    ))

    # ── Build ─────────────────────────────────────────────────────────────────
    doc.build(story)
    logger.info("[PDFGenerator] PDF saved to %s", filepath)

    return {
        "pdf_status": {"generated": True, "path": str(filepath), "filename": filename},
        "pdf_path": str(filepath),
        "current_agent": "pdf_generator",
    }
