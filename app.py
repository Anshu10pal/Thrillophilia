"""
app.py — Thrillophilia AI Trip Planner  (Complete Redesign)
============================================================
Changes:
  1. Hotel/activity preferences editable even when within budget
  2. Transport choice changeable + itinerary rebuilds
  3. Dynamic itinerary updates on all preference changes
  4. Premium UI: dark/gold/black, hero header, India/Abroad tabs, horizontal location scroll
  5. Subtle creative chatbot panel

Run: streamlit run app.py -- --env "D:\\FDE\\Day 1\\.env"
"""

import sys, os, time, threading, argparse, warnings, logging, re, json
from pathlib import Path
from copy import deepcopy

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.ERROR)
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import streamlit as st

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--env", default=None)
args, _ = parser.parse_known_args()
from dotenv import load_dotenv
load_dotenv(args.env if args.env else ".env", override=True)

sys.path.insert(0, str(Path(__file__).parent))

GUARDRAILS_ENABLED = False
try:
    from tools.guardrails import run_guardrails, GuardrailResult
    GUARDRAILS_ENABLED = True
except Exception:
    GUARDRAILS_ENABLED = False

# Evaluation framework
EVALUATION_ENABLED = False
try:
    from tools.evaluation import evaluate_trip_result, render_evaluation_dashboard
    EVALUATION_ENABLED = True
except Exception:
    EVALUATION_ENABLED = False

st.set_page_config(
    page_title="Thrillophilia — AI Trip Planner",
    page_icon="🧳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════════════════════
# PREMIUM CSS  —  Dark / Gold / Black with cream accents
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@300;400;500;600;700&display=swap');

:root {
  --gold:    #C9A84C;
  --gold2:   #E8C97A;
  --dark:    #0D0D0D;
  --dark2:   #1A1A1A;
  --dark3:   #252525;
  --card:    #1E1E1E;
  --border:  #2E2E2E;
  --cream:   #F5F0E8;
  --text:    #F0EAD6;
  --muted:   #888888;
  --red:     #B02A2A;
  --green:   #2E7D52;
  --blue:    #1A4A8A;
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
    background-color: var(--dark) !important;
    color: var(--text) !important;
}
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 !important; max-width: 100% !important; }
[data-testid="stSidebar"] { display: none !important; }

/* ── Inputs ── */
.stTextArea textarea {
    background: var(--dark3) !important;
    border: 1px solid var(--gold) !important;
    border-radius: 10px !important;
    color: var(--cream) !important;
    font-size: 0.95rem !important;
}
.stTextArea textarea:focus { box-shadow: 0 0 0 2px rgba(201,168,76,0.3) !important; }
.stTextArea textarea::placeholder { color: #666 !important; }
.stTextArea label { color: var(--gold) !important; font-weight: 600 !important; font-size: 0.85rem !important; }
.stTextInput input {
    background: var(--dark3) !important;
    border: 1px solid var(--gold) !important;
    border-radius: 8px !important;
    color: var(--cream) !important;
}
.stTextInput label { color: var(--gold) !important; font-weight: 600 !important; }

/* ── Buttons ── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, var(--gold), var(--gold2)) !important;
    color: var(--dark) !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 0.9rem !important;
    padding: 0.55rem 1.2rem !important;
}
.stButton > button[kind="primary"]:hover { opacity: 0.9 !important; transform: translateY(-1px) !important; }
.stButton > button[kind="secondary"] {
    background: transparent !important;
    color: var(--gold) !important;
    border: 1px solid var(--gold) !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
.stButton > button[kind="secondary"]:hover { background: rgba(201,168,76,0.1) !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: var(--dark2) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    padding: 3px !important;
    gap: 2px !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--muted) !important;
    border-radius: 7px !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    padding: 5px 12px !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, var(--gold), var(--gold2)) !important;
    color: var(--dark) !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    padding: 0.8rem !important;
}
[data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: 0.72rem !important; text-transform: uppercase; letter-spacing: 0.05em; }
[data-testid="stMetricValue"] { color: var(--gold) !important; font-size: 1.2rem !important; font-weight: 700 !important; }

/* ── Expander ── */
[data-testid="stExpander"] { background: var(--card) !important; border: 1px solid var(--border) !important; border-radius: 10px !important; }
.streamlit-expanderHeader { color: var(--gold) !important; font-weight: 600 !important; font-size: 0.88rem !important; }

/* ── Progress ── */
.stProgress > div > div { background: linear-gradient(90deg, var(--gold), var(--gold2)) !important; }
.stProgress > div { background: var(--dark3) !important; }

/* ── Alerts ── */
.stSuccess { background: #0D1F15 !important; border: 1px solid var(--green) !important; color: #90EE90 !important; border-radius: 8px !important; }
.stError   { background: #1F0D0D !important; border: 1px solid var(--red) !important; color: #FFB3B3 !important; border-radius: 8px !important; }
.stWarning { background: #1F1A0D !important; border: 1px solid var(--gold) !important; color: var(--gold2) !important; border-radius: 8px !important; }
.stInfo    { background: #0D1324 !important; border: 1px solid var(--blue) !important; color: #B3C8FF !important; border-radius: 8px !important; }

hr { border-color: var(--border) !important; }
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--dark2); }
::-webkit-scrollbar-thumb { background: var(--gold); border-radius: 3px; }

/* ── Select/Radio ── */
.stRadio > div { gap: 0.4rem !important; }
.stRadio label { color: var(--text) !important; }
.stSelectbox select { background: var(--dark3) !important; color: var(--cream) !important; border: 1px solid var(--gold) !important; }

/* Download button */
.stDownloadButton > button {
    background: linear-gradient(135deg, var(--gold), var(--gold2)) !important;
    color: var(--dark) !important;
    border: none !important;
    font-weight: 700 !important;
    border-radius: 8px !important;
    width: 100% !important;
}

/* ── Location card (horizontal scroll) ── */
.loc-scroll {
    display: flex;
    gap: 12px;
    overflow-x: auto;
    padding: 12px 0 16px 0;
    scrollbar-width: thin;
}
.loc-card {
    flex-shrink: 0;
    width: 130px;
    border-radius: 12px;
    border: 2px solid var(--border);
    background: var(--card);
    cursor: pointer;
    transition: all 0.2s;
    overflow: hidden;
    text-align: center;
}
.loc-card:hover { border-color: var(--gold); transform: translateY(-3px); }
.loc-card.selected { border-color: var(--gold); background: linear-gradient(180deg, #2A2410, var(--card)); }
.loc-card-img { width: 100%; height: 75px; object-fit: cover; }
.loc-card-name { color: var(--text); font-size: 0.78rem; font-weight: 600; padding: 6px 4px; }

/* ── Chat bubble ── */
/* ── Chat bubbles ── */
.chat-user {
    background: #FFFFFF;
    border: 2px solid #2E7D52;
    border-radius: 14px 14px 4px 14px;
    padding: 0.6rem 0.9rem;
    margin: 0.4rem 0 0.4rem 1.5rem;
    font-size: 0.85rem;
    color: #111111;
}
.chat-bot {
    background: #FFFFFF;
    border: 2px solid #1A4A8A;
    border-radius: 14px 14px 14px 4px;
    padding: 0.6rem 0.9rem;
    margin: 0.4rem 1.5rem 0.4rem 0;
    font-size: 0.85rem;
    color: #111111;
}
.chat-question {
    background: #FFFFFF;
    border: 2px solid #1A4A8A;
    border-radius: 14px 14px 14px 4px;
    padding: 0.65rem 0.9rem;
    margin: 0.4rem 1.5rem 0.4rem 0;
    font-size: 0.88rem;
    color: #111111;
}

/* ── Hide destination button text (show only the image card above) ── */
[data-testid="stButton"] > button[title^="Plan a trip"] {
    opacity: 0 !important;
    height: 4px !important;
    min-height: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    font-size: 0 !important;
    border: none !important;
    background: transparent !important;
    position: relative;
    top: -6px;
}

/* ── Section heading ── */
.sec-head {
    border-left: 3px solid var(--gold);
    padding: 4px 0 4px 12px;
    margin: 1.2rem 0 0.7rem;
}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# DESTINATION DATA
# ══════════════════════════════════════════════════════════════════════════════

INDIA_DESTINATIONS = [
    {"name": "Goa",        "emoji": "🏖️",  "img": "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?w=200&q=60"},
    {"name": "Kerala",     "emoji": "🌴",  "img": "https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?w=200&q=60"},
    {"name": "Rajasthan",  "emoji": "🏰",  "img": "https://images.unsplash.com/photo-1477587458883-47145ed6736c?w=200&q=60"},
    {"name": "Manali",     "emoji": "🏔️",  "img": "https://images.unsplash.com/photo-1626621341517-bbf3d9990a23?w=200&q=60"},
    {"name": "Andaman",    "emoji": "🐚",  "img": "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=200&q=60"},
    {"name": "Darjeeling", "emoji": "🍵",  "img": "https://images.unsplash.com/photo-1585136917228-ce68f7aeabce?w=200&q=60"},
    {"name": "Leh Ladakh", "emoji": "🗻",  "img": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=200&q=60"},
    {"name": "Rishikesh",  "emoji": "🕉️",  "img": "https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=200&q=60"},
    {"name": "Coorg",      "emoji": "☕",  "img": "https://images.unsplash.com/photo-1509316785289-025f5b846b35?w=200&q=60"},
    {"name": "Udaipur",    "emoji": "🛶",  "img": "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=200&q=60"},
    {"name": "Varanasi",   "emoji": "🪔",  "img": "https://images.unsplash.com/photo-1561361058-c24e5e3d885f?w=200&q=60"},
    {"name": "Mumbai",     "emoji": "🌆",  "img": "https://images.unsplash.com/photo-1570168007204-dfb528c6958f?w=200&q=60"},
]

ABROAD_DESTINATIONS = [
    {"name": "Bali",       "emoji": "🌺",  "img": "https://images.unsplash.com/photo-1537996194471-e657df975ab4?w=200&q=60"},
    {"name": "Dubai",      "emoji": "🏙️",  "img": "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=200&q=60"},
    {"name": "Thailand",   "emoji": "🐘",  "img": "https://images.unsplash.com/photo-1528360983277-13d401cdc186?w=200&q=60"},
    {"name": "Maldives",   "emoji": "🐠",  "img": "https://images.unsplash.com/photo-1514282401047-d79a71a590e8?w=200&q=60"},
    {"name": "Paris",      "emoji": "🗼",  "img": "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=200&q=60"},
    {"name": "Singapore",  "emoji": "🦁",  "img": "https://images.unsplash.com/photo-1525625293386-3f8f99389edd?w=200&q=60"},
    {"name": "Switzerland","emoji": "🏔️",  "img": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=200&q=60"},
    {"name": "Japan",      "emoji": "⛩️",  "img": "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?w=200&q=60"},
    {"name": "Barcelona",  "emoji": "⚽",  "img": "https://images.unsplash.com/photo-1539037116277-4db20889f2d4?w=200&q=60"},
    {"name": "New York",   "emoji": "🗽",  "img": "https://images.unsplash.com/photo-1485871981521-5b1fd3805eee?w=200&q=60"},
    {"name": "London",     "emoji": "🎡",  "img": "https://images.unsplash.com/photo-1513635269975-59663e0ac1ad?w=200&q=60"},
    {"name": "Santorini",  "emoji": "🫐",  "img": "https://images.unsplash.com/photo-1570077188670-e3a8d69ac5ff?w=200&q=60"},
]

# ══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════

# ── Rate limiting constants ───────────────────────────────────────────────────
RATE_LIMIT_MAX_QUERIES   = 5      # max planning runs per session
RATE_LIMIT_COOLDOWN_SECS = 30     # seconds to wait between runs

DEFAULTS = {
    "planner":               None,
    "result":                None,
    "flow_stage":            "hero",
    "region":                None,
    "selected_destination":  None,
    # Rate limiting
    "query_count":           0,
    "last_query_time":       0.0,
    "chat_messages":         [],
    "trip_preferences":      {},
    "clarification_answers": {},
    "missing_fields":        [],
    "current_question":      "",
    "current_question_field":"",
    "hotel_options_by_loc":  {},
    "itinerary_locations":   [],
    "hotel_selections":      {},
    "hotel_selection_step":  0,
    "overrun_hotel_swaps":   {},
    "skipped_activities":    [],
    "custom_transport":      None,
    "prefill":               "",
    "initial_query":         "",
    "rebuild_pending":       False,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

AGENT_STEPS = [
    "Parsing query","Retrieving knowledge","Weather",
    "Transport","Hotels","Places","Budget",
    "Building itinerary","Final review","PDF report",
]

# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _f(val, default=0.0):
    try: return float(val)
    except: return default

def check_api_key():
    k = os.getenv("OPENAI_API_KEY","")
    return bool(k and k.startswith("sk-"))

def gold_card(inner, border="#2E2E2E", accent=None):
    left = f"border-left:3px solid {accent};" if accent else ""
    r    = "0 10px 10px 0" if accent else "10px"
    return (
        f'<div style="background:#1E1E1E;border:1px solid {border};{left}'
        f'border-radius:{r};padding:0.85rem 1rem;margin-bottom:0.6rem;">{inner}</div>'
    )

def sec(icon, title, sub=""):
    s = f'<div style="color:#888;font-size:0.78rem;margin-top:1px;">{sub}</div>' if sub else ""
    return (
        f'<div class="sec-head">'
        f'<span style="font-size:1rem;font-weight:700;color:#F0EAD6;">{icon} {title}</span>{s}</div>'
    )

def _apply_guardrails(text):
    if not GUARDRAILS_ENABLED:
        return True, "", text
    result = run_guardrails(text)
    if result.blocked:
        return False, result.reason, text
    return True, "", result.clean

def _show_block(reason):
    st.markdown(
        f'<div style="background:#1F0D0D;border:1px solid #B02A2A;border-radius:10px;'
        f'padding:0.8rem 1rem;margin:0.5rem 0;font-size:0.88rem;color:#FFB3B3;">'
        f'🚫 {reason}</div>',
        unsafe_allow_html=True
    )

# ══════════════════════════════════════════════════════════════════════════════
# PLANNER RUNNER
# ══════════════════════════════════════════════════════════════════════════════

def get_planner():
    if st.session_state["planner"] is None:
        from workflow import TripPlanner
        st.session_state["planner"] = TripPlanner()
    return st.session_state["planner"]

def run_planning(query, is_refine=False):
    planner = get_planner()
    result_h, error_h = [None], [None]
    def worker():
        try: result_h[0] = planner.refine(query) if is_refine else planner.plan(query)
        except Exception as e: error_h[0] = e
    t = threading.Thread(target=worker); t.start()
    prog = st.progress(0); status = st.empty()
    step, total = 0, len(AGENT_STEPS)
    while t.is_alive():
        i = min(step, total-1)
        done = "  ·  ".join(f"✓ {AGENT_STEPS[j]}" for j in range(i))
        status.markdown(
            f'<div style="background:#1E1E1E;border:1px solid #2E2E2E;border-radius:8px;'
            f'padding:0.55rem 0.9rem;font-size:0.8rem;">'
            f'<span style="color:#C9A84C;font-weight:700;">⟳ {AGENT_STEPS[i]}…</span>'
            f'{"&nbsp;<span style=color:#333>|</span>&nbsp;" + done if done else ""}</div>',
            unsafe_allow_html=True
        )
        prog.progress(min((step+0.4)/total, 0.94))
        time.sleep(1.1)
        step = step+1 if step < total-1 else total-2
    t.join(); prog.progress(1.0); status.empty(); prog.empty()
    if error_h[0]: raise error_h[0]
    return result_h[0]

def run_hotel_options(result):
    from agents.agents import hotel_options_per_location_agent
    upd = hotel_options_per_location_agent(result)
    result.update(upd)
    return result

def rebuild_itinerary(selections, opts_map, skipped, custom_transport=None):
    """Full rebuild: update hotels + transport + regenerate itinerary + PDF."""
    import copy, logging as _log
    log = _log.getLogger("trip_planner")
    result = copy.deepcopy(st.session_state.get("result", {}))
    if not result: return False
    prefs    = result.get("trip_preferences", {})
    num_days = prefs.get("num_days", 5)

    # 1. Update hotel_data
    hotel_by_loc, total_hotel = {}, 0.0
    for loc, idx in selections.items():
        opts = opts_map.get(loc, [])
        if opts and idx < len(opts):
            chosen = opts[min(idx, len(opts)-1)]
            hotel_by_loc[loc] = chosen
            total_hotel += _f(chosen.get("price_per_night", 0)) * num_days
    if hotel_by_loc:
        first = next(iter(hotel_by_loc.values()))
        result["hotel_data"]["recommended_hotel"]      = first
        result["hotel_data"]["total_accommodation_cost"] = total_hotel
        result["trip_preferences"]["selected_hotels"] = {l: o.get("name","") for l,o in hotel_by_loc.items()}

    # 2. Update transport if user chose custom
    if custom_transport:
        result["trip_preferences"]["transport_preference"] = custom_transport
        # Clear existing transport so agent regenerates
        result["transport_data"] = {}

    # 3. Remove skipped activities
    if skipped:
        places = result.get("places_data", {})
        places["activities"]      = [a for a in places.get("activities", [])      if a.get("name","") not in skipped]
        places["top_attractions"] = [a for a in places.get("top_attractions", []) if a.get("name","") not in skipped]
        result["places_data"] = places

    # 4. Wipe stale itinerary
    result["itinerary"] = {}

    # 5. Re-run agents
    try:
        from agents.agents import itinerary_agent, budget_agent, transport_agent
        from tools.pdf_generator import generate_pdf

        # Regenerate transport if changed
        if custom_transport:
            new_t = transport_agent(result)
            result.update(new_t)

        # Regenerate itinerary
        new_itin = itinerary_agent(result)
        result.update(new_itin)

        # Patch hotel names in days
        days = result.get("itinerary", {}).get("days", [])
        for day in days:
            loc = (day.get("accommodation") or "").split(",")[0].strip()
            if loc in hotel_by_loc:
                day["accommodation"] = hotel_by_loc[loc].get("name", loc)
        if "itinerary" in result:
            result["itinerary"]["days"] = days

        # Recalculate budget
        new_bgt = budget_agent(result)
        result.update(new_bgt)

        # Regenerate PDF
        new_pdf = generate_pdf(result)
        result.update(new_pdf)

        st.session_state["result"] = result
        log.info("Itinerary rebuild successful")
        return True
    except Exception as e:
        log.error("Rebuild failed: %s", e)
        st.session_state["result"] = result
        return False

# ══════════════════════════════════════════════════════════════════════════════
# CLARIFICATION LOGIC
# ══════════════════════════════════════════════════════════════════════════════

def _handle_clarification(answer):
    from agents.agents import absorb_clarification_answer, clarification_agent
    allowed, block_msg, clean = _apply_guardrails(answer)
    if not allowed:
        st.session_state["chat_messages"].append({"role":"bot","content":block_msg,"type":"block"})
        return
    if clean != answer:
        st.session_state["chat_messages"].append({"role":"bot","content":"🔒 PII masked for your security.","type":"status"})
    field = st.session_state["current_question_field"]
    st.session_state["chat_messages"].append({"role":"user","content":clean,"type":"answer"})
    fake = {"trip_preferences": st.session_state["trip_preferences"],
            "clarification_answers": st.session_state["clarification_answers"]}
    upd = absorb_clarification_answer(fake, field, clean)
    st.session_state["trip_preferences"].update(upd.get("trip_preferences", {}))
    st.session_state["clarification_answers"].update(upd.get("clarification_answers", {}))
    check = {"trip_preferences": st.session_state["trip_preferences"],
             "clarification_answers": st.session_state["clarification_answers"]}
    res = clarification_agent(check)
    if res["flow_stage"] == "clarifying":
        st.session_state.update({
            "missing_fields": res["missing_fields"],
            "current_question": res["clarification_question"],
            "current_question_field": res["missing_fields"][0],
        })
        st.session_state["chat_messages"].append({"role":"bot","content":res["clarification_question"],"type":"question"})
    else:
        st.session_state["flow_stage"] = "planning"
        st.session_state["chat_messages"].append({"role":"bot","content":"✨ Perfect! Crafting your personalised journey now…","type":"status"})

def _skip_clarification():
    from agents.agents import FIELD_QUESTIONS
    missing = st.session_state["missing_fields"]
    if len(missing) > 1:
        nxt = missing[1]
        st.session_state.update({
            "missing_fields": missing[1:],
            "current_question": FIELD_QUESTIONS.get(nxt, f"Tell me your {nxt}?"),
            "current_question_field": nxt,
        })
    else:
        st.session_state["flow_stage"] = "planning"
        st.session_state["chat_messages"].append({"role":"bot","content":"✨ Crafting your journey with available details…","type":"status"})

# ══════════════════════════════════════════════════════════════════════════════
# CHAT PANEL
# ══════════════════════════════════════════════════════════════════════════════

def render_chat(col):
    with col:
        # Panel wrapper — distinct light background
        st.markdown(
            '<div style="background:#F8F4EE;'
            'border:2px solid #C9A84C;border-radius:16px;overflow:hidden;'
            'box-shadow:0 4px 20px rgba(0,0,0,0.3);">',
            unsafe_allow_html=True
        )
        # Header
        st.markdown(
            '<div style="background:linear-gradient(135deg,#1A1400,#2A2000);'
            'padding:0.75rem 1rem;border-bottom:2px solid #C9A84C;">'
            '<div style="display:flex;align-items:center;gap:8px;">'
            '<div style="width:34px;height:34px;background:linear-gradient(135deg,#C9A84C,#E8C97A);'
            'border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.1rem;">🧳</div>'
            '<div>'
            '<div style="font-family:Playfair Display,serif;font-weight:900;font-size:0.92rem;color:#E8C97A;">Thrillophilia</div>'
            '<div style="font-size:0.62rem;color:#C9A84C;letter-spacing:0.1em;text-transform:uppercase;">AI Concierge</div>'
            '</div></div></div>',
            unsafe_allow_html=True
        )
        # Messages area — light cream bg
        msgs_html = '<div style="padding:0.7rem;max-height:45vh;overflow-y:auto;background:#F8F4EE;">'
        for msg in st.session_state["chat_messages"]:
            role    = msg["role"]
            content = msg["content"]
            mtype   = msg.get("type","")
            if role == "user":
                msgs_html += f'<div class="chat-user">👤 {content}</div>'
            elif mtype == "question":
                msgs_html += (
                    f'<div class="chat-question">'
                    f'<div style="color:#C9A84C;font-size:0.68rem;font-weight:700;'
                    f'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:3px;">Concierge</div>'
                    f'{content}</div>'
                )
            elif mtype == "status":
                msgs_html += (
                    f'<div style="text-align:center;padding:4px 0;'
                    f'font-size:0.78rem;color:#888;">{content}</div>'
                )
            else:
                msgs_html += f'<div class="chat-bot">🤖 {content}</div>'
        msgs_html += '</div>'
        st.markdown(msgs_html, unsafe_allow_html=True)

        # Input area for clarification
        stage = st.session_state["flow_stage"]
        if stage == "clarifying":
            st.markdown(
                f'<div style="background:#FFFFFF;border:2px solid #1A4A8A;'
                f'border-radius:10px;padding:0.6rem 0.8rem;margin:0.4rem 0.7rem;">'
                f'<div style="color:#1A4A8A;font-size:0.72rem;font-weight:700;'
                f'text-transform:uppercase;margin-bottom:4px;">🤖 Concierge</div>'
                f'<div style="color:#111111;font-size:0.88rem;">{st.session_state["current_question"]}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            with st.container():
                ans = st.text_input("Answer", key="chat_ans", placeholder="Type here…", label_visibility="collapsed")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Submit ✓", type="primary", key="chat_ok", use_container_width=True):
                        if ans.strip(): _handle_clarification(ans.strip()); st.rerun()
                with c2:
                    if st.button("Skip →", type="secondary", key="chat_skip", use_container_width=True):
                        _skip_clarification(); st.rerun()

        elif stage == "complete":
            # Refine box
            st.markdown('<div style="padding:0 0.7rem 0.7rem;">', unsafe_allow_html=True)
            rq = st.text_input("Refine", key="refine_q", placeholder="e.g. cheaper hotel on Day 2…", label_visibility="collapsed")
            if st.button("Update Plan ✨", type="primary", key="refine_btn", use_container_width=True):
                if rq.strip():
                    allowed, blk, clean_rq = _apply_guardrails(rq.strip())
                    if not allowed: _show_block(blk)
                    else:
                        try:
                            r2 = run_planning(clean_rq, is_refine=True)
                            if r2:
                                r2["trip_preferences"].update(st.session_state["trip_preferences"])
                                st.session_state["result"] = r2
                                st.session_state["chat_messages"].append({"role":"bot","content":"✅ Plan updated!","type":"status"})
                                st.rerun()
                        except Exception as e: st.error(f"❌ {e}")
            st.markdown('</div>', unsafe_allow_html=True)

        # Rate limit indicator
        qcount = st.session_state.get("query_count", 0)
        remaining = max(0, RATE_LIMIT_MAX_QUERIES - qcount)
        if qcount > 0:
            st.markdown(
                f'<div style="padding:2px 7px;font-size:0.68rem;color:#888;'
                f'text-align:center;">🚦 {remaining}/{RATE_LIMIT_MAX_QUERIES} plans remaining</div>',
                unsafe_allow_html=True
            )

        # Stage pills
        stage_map = {"hero":1,"clarifying":2,"planning":3,"selecting_hotels":4,"complete":5}
        cur = stage_map.get(stage, 1)
        pills = ["Explore","Details","Planning","Hotels","Done"]
        pills_html = "".join(
            f'<span style="background:{"linear-gradient(135deg,#C9A84C,#E8C97A)" if i+1==cur else "#252525"};'
            f'color:{"#0D0D0D" if i+1==cur else "#666"};border-radius:20px;'
            f'padding:3px 9px;font-size:0.65rem;font-weight:700;">{p}</span>'
            for i,p in enumerate(pills)
        )
        st.markdown(
            f'<div style="padding:0.5rem 0.7rem;display:flex;gap:4px;flex-wrap:wrap;'
            f'border-top:1px solid #2E2E2E;">{pills_html}</div>',
            unsafe_allow_html=True
        )

        # New trip button
        if stage not in ("hero",):
            if st.button("🔄 New Trip", type="secondary", key="new_trip", use_container_width=True):
                for k, v in DEFAULTS.items(): st.session_state[k] = v
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)  # close panel wrapper

# ══════════════════════════════════════════════════════════════════════════════
# HERO STAGE
# ══════════════════════════════════════════════════════════════════════════════

def render_hero():
    # Full-width hero header
    st.markdown(
        '<div style="background:linear-gradient(180deg,#0D0D0D,#111108);">'
        '<div style="max-width:1400px;margin:0 auto;padding:2rem 2.5rem 1rem;">'
        # Nav bar
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2.5rem;">'
        '<div style="font-family:Playfair Display,serif;font-size:1.6rem;font-weight:900;'
        'background:linear-gradient(135deg,#C9A84C,#E8C97A);-webkit-background-clip:text;'
        '-webkit-text-fill-color:transparent;background-clip:text;">🧳 Thrillophilia</div>'
        '<div style="display:flex;gap:1.5rem;color:#888;font-size:0.82rem;">'
        '<span style="color:#C9A84C;cursor:pointer;">Destinations</span>'
        '<span style="cursor:pointer;">Experiences</span>'
        '<span style="cursor:pointer;">Deals</span>'
        '</div>'
        '<div style="background:linear-gradient(135deg,#C9A84C,#E8C97A);color:#0D0D0D;'
        'border-radius:6px;padding:5px 14px;font-size:0.78rem;font-weight:700;cursor:pointer;">Login</div>'
        '</div>'
        # Hero text
        '<div style="text-align:center;padding:1rem 0 2.5rem;">'
        '<div style="font-family:Playfair Display,serif;font-size:3.2rem;font-weight:900;'
        'color:#F0EAD6;line-height:1.1;margin-bottom:0.5rem;">'
        'Your Tour,<br><span style="background:linear-gradient(135deg,#C9A84C,#E8C97A);'
        '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
        'background-clip:text;">Perfectly Personalised!</span></div>'
        '<div style="color:#888;font-size:1rem;margin-top:0.8rem;letter-spacing:0.02em;">'
        'Explore Expert-led, AI-powered multi-day tours curated just for you</div>'
        '</div>'
        '</div></div>',
        unsafe_allow_html=True
    )

    # Main content
    st.markdown('<div style="max-width:1400px;margin:0 auto;padding:0 2.5rem 3rem;">', unsafe_allow_html=True)

    # ── Region selector — CENTERED ──────────────────────────────────────────────
    _, rc1, rc2, _ = st.columns([2, 1.2, 1.2, 2])
    with rc1:
        india_active = st.session_state["region"] == "India"
        if st.button(
            ("✓  India" if india_active else "🇮🇳  India"),
            key="btn_india",
            type="primary" if india_active else "secondary",
            use_container_width=True
        ):
            st.session_state["region"] = "India"
            st.session_state["selected_destination"] = None
            st.rerun()
    with rc2:
        abroad_active = st.session_state["region"] == "Abroad"
        if st.button(
            ("✓  Abroad" if abroad_active else "🌍  Abroad"),
            key="btn_abroad",
            type="primary" if abroad_active else "secondary",
            use_container_width=True
        ):
            st.session_state["region"] = "Abroad"
            st.session_state["selected_destination"] = None
            st.rerun()

    # ── Destination image cards (ONE click = select + proceed) ───────────────
    region = st.session_state["region"]
    if region:
        dests = INDIA_DESTINATIONS if region == "India" else ABROAD_DESTINATIONS
        st.markdown(
            f'<div style="color:#C9A84C;font-size:0.72rem;font-weight:700;'
            f'text-transform:uppercase;letter-spacing:0.1em;margin:1rem 0 0.5rem;">'
            f'Popular in {region}</div>',
            unsafe_allow_html=True
        )
        # Each destination gets ONE button styled as an image card.
        # CSS hides the default button text and shows image+name via label HTML.
        # We render them in rows of 6 so they fill width.
        chunk_size = 6
        for row_start in range(0, len(dests), chunk_size):
            row_dests = dests[row_start: row_start + chunk_size]
            row_cols  = st.columns(len(row_dests))
            for col_idx, d in enumerate(row_dests):
                selected = st.session_state["selected_destination"] == d["name"]
                border   = "#C9A84C" if selected else "#2E2E2E"
                bg       = "#2A2410" if selected else "#1A1A1A"
                name_col = "#C9A84C" if selected else "#F0EAD6"
                with row_cols[col_idx]:
                    # Card HTML shown above the button
                    st.markdown(
                        f'<div style="background:{bg};border:2px solid {border};'
                        f'border-radius:12px;overflow:hidden;cursor:pointer;'
                        f'transition:all 0.2s;margin-bottom:2px;">'
                        f'<div style="position:relative;height:72px;overflow:hidden;">'
                        f'<img src="{d["img"]}" style="width:100%;height:72px;object-fit:cover;"'
                        f' onerror="this.style.display=\'none\'">'
                        f'{"<div style=position:absolute;inset:0;background:rgba(201,168,76,0.2);></div>" if selected else ""}'
                        f'</div>'
                        f'<div style="color:{name_col};font-size:0.74rem;font-weight:{"700" if selected else "500"};'
                        f'padding:5px 4px;text-align:center;">{d["name"]}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                    # Single invisible button that triggers selection AND proceeds
                    if st.button(
                        d["name"], key=f"dest_{d['name']}",
                        use_container_width=True,
                        help=f"Plan a trip to {d['name']}"
                    ):
                        sel = d["name"]
                        st.session_state["selected_destination"] = sel
                        # Rate limit check on destination card click
                        rl_ok, rl_msg = _check_rate_limit()
                        if not rl_ok:
                            st.error(rl_msg)
                            st.stop()
                        st.session_state["trip_preferences"]["destination"] = sel
                        st.session_state["trip_preferences"]["currency"]    = "INR" if region == "India" else "USD"
                        from agents.agents import user_input_agent, clarification_agent
                        fake = {
                            "user_query": f"I want to go to {sel}",
                            "trip_preferences": st.session_state["trip_preferences"],
                            "clarification_answers": {},
                            "conversation_history": [],
                        }
                        ui = user_input_agent(fake)

                        ui_prefs = ui.get("trip_preferences", {})
                        if isinstance(ui_prefs, list):
                            ui_prefs = ui_prefs[0] if ui_prefs else {}
                        if not isinstance(ui_prefs, dict):
                            ui_prefs = {}
                            
                        st.session_state["trip_preferences"].update(ui.get("trip_preferences", {}))
                        cl = clarification_agent({
                            "trip_preferences": st.session_state["trip_preferences"],
                            "clarification_answers": {},
                        })  
                        st.session_state["chat_messages"].append({
                            "role":"bot",
                            "content":f"✨ {sel} — wonderful choice! Let me personalise this for you.",
                            "type":"status"
                        })
                        if cl["flow_stage"] == "clarifying":
                            q = cl["clarification_question"]
                            st.session_state.update({
                                "flow_stage": "clarifying",
                                "missing_fields": cl["missing_fields"],
                                "current_question": q,
                                "current_question_field": cl["missing_fields"][0],
                            })
                            st.session_state["chat_messages"].append({"role":"bot","content":q,"type":"question"})
                        else:
                            st.session_state["flow_stage"] = "planning"
                        st.rerun()

    # Or type custom query
    st.markdown(
        '<div style="color:#555;font-size:0.8rem;text-align:center;margin:1.5rem 0 0.5rem;">— or describe your trip directly —</div>',
        unsafe_allow_html=True
    )
    _, mid, _ = st.columns([1,4,1])
    with mid:
        prefill = st.session_state.pop("prefill","")
        query = st.text_area(
            "🗺️ Describe your dream trip",
            value=prefill,
            placeholder="e.g. 10-day Dubai honeymoon from Delhi for 2, budget ₹2,00,000…",
            height=80, label_visibility="visible"
        )
        if not check_api_key():
            api_k = st.text_input("🔑 OpenAI API Key", type="password", placeholder="sk-…")
            if api_k: os.environ["OPENAI_API_KEY"] = api_k
        if st.button("✨  Plan My Trip", type="primary", use_container_width=True):
            if not check_api_key(): st.error("Add your OpenAI API key above"); st.stop()
            if not query.strip(): st.warning("Describe your trip first"); st.stop()
            allowed, blk, clean_q = _apply_guardrails(query)
            if not allowed: _show_block(blk); st.stop()
            # Rate limit check
            rl_ok, rl_msg = _check_rate_limit()
            if not rl_ok:
                st.markdown(
                    f'<div style="background:#1F1A08;border:1px solid #C9A84C;'
                    f'border-radius:10px;padding:0.8rem 1rem;font-size:0.88rem;'
                    f'color:#E8C97A;">{rl_msg}</div>',
                    unsafe_allow_html=True
                )
                st.stop()
            st.session_state["initial_query"] = clean_q
            st.session_state["chat_messages"].append({"role":"user","content":clean_q,"type":"query"})
            from agents.agents import user_input_agent, clarification_agent
            fake = {"user_query":clean_q,"trip_preferences":st.session_state["trip_preferences"],
                    "clarification_answers":{},"conversation_history":[]}
            ui = user_input_agent(fake)
            st.session_state["trip_preferences"].update(ui.get("trip_preferences",{}))
            cl = clarification_agent({"trip_preferences":st.session_state["trip_preferences"],"clarification_answers":{}})
            if cl["flow_stage"] == "clarifying":
                q = cl["clarification_question"]
                st.session_state.update({
                    "flow_stage":"clarifying","missing_fields":cl["missing_fields"],
                    "current_question":q,"current_question_field":cl["missing_fields"][0],
                })
                st.session_state["chat_messages"].append({"role":"bot","content":q,"type":"question"})
            else:
                st.session_state["flow_stage"] = "planning"
                st.session_state["chat_messages"].append({"role":"bot","content":"✨ Crafting your journey…","type":"status"})
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# HOTEL SELECTION
# ══════════════════════════════════════════════════════════════════════════════

def render_hotel_selection(col):
    with col:
        locs  = st.session_state["itinerary_locations"]
        step  = st.session_state["hotel_selection_step"]
        total = len(locs)
        if step >= total:
            st.session_state["flow_stage"] = "complete"; st.rerun(); return

        loc      = locs[step]
        options  = st.session_state["hotel_options_by_loc"].get(loc, [])
        prefs    = st.session_state["trip_preferences"]
        currency = prefs.get("currency","INR")
        num_days = prefs.get("num_days",1)

        st.markdown(
            f'<div style="background:linear-gradient(135deg,#1A1400,#252510);'
            f'border:1px solid #C9A84C;border-radius:12px;padding:1rem 1.3rem;'
            f'margin-bottom:1.2rem;display:flex;justify-content:space-between;">'
            f'<div><div style="color:#C9A84C;font-weight:800;font-size:1rem;">Choose Your Hotel</div>'
            f'<div style="color:#888;font-size:0.8rem;">📍 {loc}</div></div>'
            f'<div style="color:#888;font-size:0.82rem;">{step+1} of {total}</div></div>',
            unsafe_allow_html=True
        )
        pct = int(step/total*100)
        st.markdown(
            f'<div style="background:#252525;border-radius:4px;height:5px;margin-bottom:1.2rem;">'
            f'<div style="background:linear-gradient(90deg,#C9A84C,#E8C97A);'
            f'width:{pct}%;height:5px;border-radius:4px;"></div></div>',
            unsafe_allow_html=True
        )

        tier_cfg = {
            "Budget":    ("#2E7D52","#0D1F15","💚"),
            "Mid-range": ("#1A4A8A","#0D1324","⭐"),
            "Premium":   ("#C9A84C","#1A1400","🏆"),
        }
        cols = st.columns(3)
        for i, opt in enumerate(options[:3]):
            tier = opt.get("tier",f"Option {i+1}")
            col_c, bg_c, icon = tier_cfg.get(tier,("#C9A84C","#1A1400","🏨"))
            ppn   = _f(opt.get("price_per_night",0))
            tot_c = _f(opt.get("total_for_stay", ppn*num_days))
            amen  = opt.get("amenities",[])
            with cols[i]:
                amen_html = " ".join(
                    f'<span style="background:{col_c}20;border:1px solid {col_c}40;'
                    f'color:{col_c};border-radius:4px;padding:1px 6px;font-size:0.68rem;">{a}</span>'
                    for a in amen[:4]
                )
                st.markdown(
                    f'<div style="background:{bg_c};border:2px solid {col_c};'
                    f'border-radius:12px;padding:1rem;min-height:260px;">'
                    f'<div style="color:{col_c};font-weight:800;font-size:0.72rem;'
                    f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:5px;">{icon} {tier}</div>'
                    f'<div style="color:#F0EAD6;font-weight:700;font-size:0.92rem;margin-bottom:3px;">'
                    f'{opt.get("name","N/A")}</div>'
                    f'<div style="color:#888;font-size:0.75rem;margin-bottom:8px;">'
                    f'📍 {opt.get("location",loc)} · {opt.get("stars","N/A")} · ⭐ {opt.get("rating","N/A")}</div>'
                    f'<div style="color:#F0EAD6;font-size:1.05rem;font-weight:800;margin-bottom:2px;">'
                    f'{currency} {ppn:,.0f}<span style="color:#666;font-size:0.7rem;">/night</span></div>'
                    f'<div style="color:#888;font-size:0.75rem;margin-bottom:8px;">'
                    f'Total: {currency} {tot_c:,.0f}</div>'
                    f'<div style="margin-bottom:6px;">{amen_html}</div>'
                    f'<div style="color:#888;font-size:0.75rem;font-style:italic;">'
                    f'{opt.get("highlight","")}</div></div>',
                    unsafe_allow_html=True
                )
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button(f"Select — {tier}", key=f"h_{loc}_{i}",
                             type="primary" if i==1 else "secondary", use_container_width=True):
                    sels = dict(st.session_state["hotel_selections"])
                    sels[loc] = i
                    st.session_state["hotel_selections"] = sels
                    st.session_state["hotel_selection_step"] = step+1
                    st.session_state["chat_messages"].append({
                        "role":"user","content":f"📍 {loc}: {opt.get('name',tier)} ({tier})","type":"selection"
                    })
                    if step+1 >= total: st.session_state["flow_stage"] = "complete"
                    st.rerun()

        if st.button("Skip → View full plan", type="secondary", key="skip_hotels"):
            st.session_state["flow_stage"] = "complete"; st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# FULL RESULTS
# ══════════════════════════════════════════════════════════════════════════════

def render_results(col, result):
    with col:
        prefs    = result.get("trip_preferences",{})
        weather  = result.get("weather_data",{})
        transport= result.get("transport_data",{})
        hotel    = result.get("hotel_data",{})
        places   = result.get("places_data",{})
        budget   = result.get("budget_summary",{})
        itin     = result.get("itinerary",{})
        review   = result.get("review_status",{})
        pdf_path = result.get("pdf_path")

        currency  = prefs.get("currency","INR")
        num_days  = prefs.get("num_days",5)
        total_bgt = _f(prefs.get("budget",0))
        bd        = budget.get("breakdown",{})
        estimated = _f(bd.get("estimated_total",0))
        surplus   = _f(budget.get("surplus_or_deficit",0))
        approved  = review.get("approved",False)
        trip_title= itin.get("trip_title", f"{num_days}-Day Trip")

        opts_map  = st.session_state.get("hotel_options_by_loc",{})
        sels      = st.session_state.get("hotel_selections",{})
        skipped   = st.session_state.get("skipped_activities",[])
        over      = surplus < 0

        # ── Trip banner ────────────────────────────────────────────────────────
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#1A1400,#252510);'
            f'border:1px solid #C9A84C;border-radius:14px;padding:1.2rem 1.5rem;margin-bottom:1rem;">'
            f'<div style="font-family:Playfair Display,serif;font-size:1.5rem;font-weight:900;'
            f'color:#F0EAD6;margin-bottom:4px;">{trip_title}</div>'
            f'<div style="color:#888;font-size:0.82rem;display:flex;gap:1rem;flex-wrap:wrap;">'
            f'<span>📍 {prefs.get("source","?")} → {prefs.get("destination","?")}</span>'
            f'<span>👥 {prefs.get("travelers",2)} travellers</span>'
            f'<span>📅 {num_days} days</span>'
            f'<span style="color:{"#2E7D52" if approved else "#C9A84C"};">'
            f'{"✅ Approved" if approved else "⚠️ Reviewed"}</span>'
            f'</div></div>',
            unsafe_allow_html=True
        )

        # Chosen hotels banner
        if sels:
            rows = ""
            for loc, idx in sels.items():
                opts = opts_map.get(loc,[])
                if opts and idx < len(opts):
                    o = opts[idx]
                    rows += (
                        f'<div style="display:flex;justify-content:space-between;'
                        f'padding:3px 0;border-bottom:1px solid #2E2E2E;">'
                        f'<span style="color:#888;font-size:0.8rem;">📍 {loc}</span>'
                        f'<span style="color:#F0EAD6;font-weight:600;font-size:0.8rem;">'
                        f'{o.get("name","?")} ({o.get("tier","?")}) — '
                        f'{currency} {_f(o.get("price_per_night",0)):,.0f}/night</span></div>'
                    )
            if rows:
                st.markdown(
                    f'<div style="background:#1E1E1E;border:1px solid #2E2E2E;'
                    f'border-radius:10px;padding:0.8rem 1rem;margin-bottom:0.8rem;">'
                    f'<div style="color:#C9A84C;font-weight:700;font-size:0.8rem;margin-bottom:5px;">🏨 Your Hotels</div>'
                    f'{rows}</div>',
                    unsafe_allow_html=True
                )

        # Metrics
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("💰 Budget",    f"{currency} {total_bgt:,.0f}")
        c2.metric("📊 Estimated", f"{currency} {estimated:,.0f}",
                  delta=f"{'+' if surplus>=0 else ''}{surplus:,.0f}",
                  delta_color="normal" if surplus>=0 else "inverse")
        c3.metric("✈️ Transport", transport.get("primary_option",{}).get("mode","N/A").title())
        c4.metric("🌤️ Weather",   weather.get("conditions","N/A").title())
        c5.metric("✅ Status",    "On Track" if surplus>=0 else "Over Budget")

        for c in review.get("conflicts",[]): st.error(f"⚠️ {c}")
        for w in review.get("warnings", []): st.warning(f"📋 {w}")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Tabs ───────────────────────────────────────────────────────────────
        # Always show Personalise tab (not just on overrun)
        tabs = st.tabs(["📅 Itinerary","🏨 Hotels","✈️ Transport","📍 Places","💰 Budget","🌤️ Weather","⚙️ Personalise"])

        # ════ ITINERARY ════════════════════════════════════════════════════════
        with tabs[0]:
            days = itin.get("days",[])
            if not days:
                st.info("Itinerary not generated yet. Try rebuilding from the Personalise tab.")
            else:
                for day in days:
                    d, theme = day.get("day","?"), day.get("theme","")
                    cost = _f(day.get("estimated_day_cost",0))
                    # Build weather pill for this day
                    day_weather = day.get("weather", {})
                    w_emoji  = day_weather.get("emoji", "")
                    w_max    = day_weather.get("max_temp", "")
                    w_min    = day_weather.get("min_temp", "")
                    w_cond   = day_weather.get("conditions", "")
                    w_prec   = day_weather.get("precipitation", "")
                    w_date   = day.get("date_label", "")
                    # Only show precipitation if it's non-zero
                    prec_html = ""
                    if w_prec and w_prec not in ("N/A", "0.0mm", "0mm"):
                        prec_html = f'<span style="color:#4A90E2;margin-left:4px;">🌧 {w_prec}</span>'
                    weather_pill = ""
                    if w_emoji or w_max:
                        weather_pill = (
                            f'<div style="background:rgba(0,0,0,0.3);border:1px solid #3A3A3A;'
                            f'border-radius:20px;padding:2px 10px;display:inline-flex;'
                            f'align-items:center;gap:5px;font-size:0.76rem;">'
                            f'<span>{w_emoji}</span>'
                            f'<span style="color:#F0EAD6;">{w_max}/{w_min}</span>'
                            f'<span style="color:#888;">·</span>'
                            f'<span style="color:#C9A84C;">{w_cond}</span>'
                            f'{prec_html}'
                            f'</div>'
                        )
                    date_html = f'<span style="color:#888;font-size:0.74rem;margin-left:8px;">{w_date}</span>' if w_date else ""
                    cost_html = f'<span style="color:#888;font-size:0.78rem;">{currency} {cost:,.0f}</span>' if cost else ""

                    st.markdown(
                        f'<div style="background:linear-gradient(90deg,#2A1F08,#1A1400);'
                        f'border-left:3px solid #C9A84C;border-radius:0 8px 8px 0;'
                        f'padding:0.6rem 1rem;margin:0.8rem 0 0.4rem;">'
                        f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">'
                        f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'
                        f'<span style="font-family:Playfair Display,serif;font-weight:700;'
                        f'color:#E8C97A;font-size:0.95rem;">Day {d} — {theme}</span>'
                        f'{date_html}'
                        f'</div>'
                        f'<div style="display:flex;align-items:center;gap:8px;">'
                        f'{weather_pill}'
                        f'{cost_html}'
                        f'</div>'
                        f'</div></div>',
                        unsafe_allow_html=True
                    )
                    # Hotel for this day
                    day_loc = (day.get("accommodation") or "").split(",")[0].strip()
                    if day_loc and day_loc in sels:
                        hi = sels[day_loc]
                        ho = opts_map.get(day_loc,[])
                        if ho and hi < len(ho):
                            h = ho[hi]
                            st.markdown(
                                f'<div style="background:#0D1324;border:1px solid #1A4A8A;'
                                f'border-radius:7px;padding:0.4rem 0.85rem;margin-bottom:0.4rem;'
                                f'display:flex;justify-content:space-between;">'
                                f'<span style="color:#4A90E2;font-weight:600;font-size:0.8rem;">'
                                f'🏨 {h.get("name","?")} ({h.get("tier","?")})</span>'
                                f'<span style="color:#F0EAD6;font-size:0.8rem;">'
                                f'{currency} {_f(h.get("price_per_night",0)):,.0f}/night</span></div>',
                                unsafe_allow_html=True
                            )
                    left, right = st.columns([3,2])
                    with left:
                        for period, emoji in [("morning","🌅"),("afternoon","☀️"),("evening","🌇"),("night","🌙")]:
                            blk = day.get(period,{})
                            if blk and blk.get("activity"):
                                st.markdown(
                                    f'<div style="padding:0.3rem 0;border-bottom:1px solid #2E2E2E;">'
                                    f'<div style="color:#C9A84C;font-size:0.68rem;text-transform:uppercase;'
                                    f'letter-spacing:0.04em;">{emoji} {period}</div>'
                                    f'<div style="color:#F0EAD6;font-size:0.86rem;">{blk["activity"]}</div>'
                                    f'{"<div style=color:#555;font-size:0.74rem;>📍 " + blk.get("location","") + "</div>" if blk.get("location") else ""}'
                                    f'</div>', unsafe_allow_html=True
                                )
                    with right:
                        meals = day.get("meals",{})
                        if any(v for v in meals.values()):
                            st.markdown('<div style="color:#C9A84C;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:3px;">🍽️ Meals</div>', unsafe_allow_html=True)
                            for meal, val in meals.items():
                                if val:
                                    st.markdown(f'<div style="font-size:0.8rem;color:#F0EAD6;padding:1px 0;"><span style="color:#666;">{meal.title()}:</span> {val}</div>', unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                cp, ct = st.columns(2)
                with cp:
                    cl = itin.get("packing_checklist",[])
                    if cl:
                        with st.expander("🧳 Packing Checklist"):
                            ci1,ci2 = st.columns(2); mid = len(cl)//2
                            for item in cl[:mid]:  ci1.markdown(f"☐ {item}")
                            for item in cl[mid:]:  ci2.markdown(f"☐ {item}")
                with ct:
                    tps = itin.get("travel_tips",[])
                    if tps:
                        with st.expander("💡 Travel Tips"):
                            for tip in tps: st.markdown(f"• {tip}")
                    ec = itin.get("emergency_contacts",{})
                    if ec:
                        with st.expander("🚨 Emergency Contacts"):
                            for k,v in ec.items(): st.markdown(f"**{k}:** {v}")

        # ════ HOTELS ══════════════════════════════════════════════════════════
        with tabs[1]:
            hopts = hotel.get("hotel_options",[])
            ridx  = hotel.get("recommended_index",1)
            if hopts:
                st.markdown(sec("🏨","Hotel Options",f"All within budget · {num_days} nights"), unsafe_allow_html=True)
                for i, opt in enumerate(hopts):
                    tier  = opt.get("tier",f"Option {i+1}")
                    col_c = {"Budget Pick":"#2E7D52","Best Value":"#C9A84C","Comfort Choice":"#8B5CF6"}.get(tier,"#C9A84C")
                    is_r  = (i == ridx)
                    amen  = " ".join(f'<span style="background:{col_c}18;border:1px solid {col_c}30;color:{col_c};border-radius:4px;padding:1px 6px;font-size:0.7rem;">{a}</span>' for a in opt.get("amenities",[])[:5])
                    rec_tag = f' <span style="background:#C9A84C18;border:1px solid #C9A84C40;color:#C9A84C;border-radius:5px;padding:1px 7px;font-size:0.7rem;">✦ Recommended</span>' if is_r else ""
                    st.markdown(
                        f'<div style="background:#1E1E1E;border:1px solid {"#C9A84C40" if is_r else "#2E2E2E"};'
                        f'border-left:3px solid {col_c};border-radius:0 10px 10px 0;'
                        f'padding:0.9rem 1.1rem;margin-bottom:0.6rem;">'
                        f'<div style="display:flex;justify-content:space-between;">'
                        f'<div><span style="color:{col_c};font-weight:700;font-size:0.72rem;'
                        f'text-transform:uppercase;">{tier}</span>{rec_tag}'
                        f'<div style="color:#F0EAD6;font-weight:700;margin-top:2px;">{opt.get("name","N/A")}</div>'
                        f'<div style="color:#888;font-size:0.78rem;">📍 {opt.get("location","N/A")} · {opt.get("category","N/A")} · ⭐ {opt.get("rating","N/A")}</div>'
                        f'</div><div style="text-align:right;">'
                        f'<div style="color:#F0EAD6;font-weight:700;font-size:1rem;">{currency} {_f(opt.get("price_per_night",0)):,.0f}<span style="color:#666;font-size:0.7rem;">/night</span></div>'
                        f'<div style="color:#888;font-size:0.76rem;">Total: {currency} {_f(opt.get("total_cost",0)):,.0f}</div>'
                        f'</div></div><div style="margin-top:6px;">{amen}</div>'
                        f'<div style="color:#888;font-size:0.78rem;margin-top:4px;">'
                        f'{opt.get("why_pick","") or opt.get("why_recommended","")} · Book: <span style="color:{col_c};">{opt.get("booking_platform","") or opt.get("booking_url","")}</span></div></div>',
                        unsafe_allow_html=True
                    )
            else:
                rec = hotel.get("recommended_hotel",{})
                if rec:
                    st.markdown(f'**{rec.get("name","N/A")}** — {currency} {_f(rec.get("price_per_night",0)):,.0f}/night')
            if hotel.get("hotel_tips"): st.info(f"💡 {hotel['hotel_tips']}")

        # ════ TRANSPORT ═══════════════════════════════════════════════════════
        with tabs[2]:
            prim = transport.get("primary_option",{})
            if prim:
                fits = prim.get("fits_budget",True)
                st.markdown(sec("✈️","Recommended Transport",prim.get("budget_note","")), unsafe_allow_html=True)
                st.markdown(
                    f'<div style="background:#1E1E1E;border:2px solid #1A4A8A;'
                    f'border-radius:10px;padding:1rem 1.2rem;margin-bottom:0.8rem;">'
                    f'<div style="display:flex;justify-content:space-between;">'
                    f'<div><div style="color:#F0EAD6;font-weight:700;margin-bottom:4px;">'
                    f'{prim.get("mode","").title()} — {prim.get("operator","N/A")}</div>'
                    f'<div style="color:#888;font-size:0.82rem;">⏱ {prim.get("duration","N/A")} · 🗓 {prim.get("schedule","N/A")} · 📱 {prim.get("booking_platform","N/A")}</div>'
                    f'<div style="color:{"#2E7D52" if fits else "#C9A84C"};font-size:0.8rem;margin-top:5px;">{"✅ Fits budget" if fits else "⚠️ May exceed budget"}</div>'
                    f'</div><div style="text-align:right;">'
                    f'<div style="color:#F0EAD6;font-weight:700;font-size:1rem;">{currency} {_f(prim.get("price_per_person",0)):,.0f}<span style="color:#666;font-size:0.7rem;">/person</span></div>'
                    f'<div style="color:#888;font-size:0.76rem;">Total ×{prefs.get("travelers",2)}: {currency} {_f(prim.get("total_price",0)):,.0f}</div>'
                    f'</div></div></div>',
                    unsafe_allow_html=True
                )

            alts = transport.get("alternative_options",[])
            if alts:
                st.markdown(sec("🔄","Alternatives"), unsafe_allow_html=True)
                for alt in alts:
                    st.markdown(
                        f'<div style="background:#1E1E1E;border:1px solid #2E2E2E;border-radius:8px;'
                        f'padding:0.6rem 0.9rem;margin-bottom:0.4rem;'
                        f'display:flex;justify-content:space-between;align-items:center;">'
                        f'<div><span style="color:#F0EAD6;font-weight:600;">{alt.get("mode","").title()}</span>'
                        f'<span style="color:#888;font-size:0.78rem;margin-left:8px;">⏱ {alt.get("duration","N/A")}</span>'
                        f'<div style="color:#666;font-size:0.76rem;">{alt.get("notes","")}</div></div>'
                        f'<span style="color:#F0EAD6;font-weight:700;">{currency} {_f(alt.get("price_per_person",0)):,.0f}<span style="color:#666;font-size:0.7rem;">/person</span></span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

            local = transport.get("local_transport",{})
            if local:
                st.markdown(sec("🛺","Local Transport"), unsafe_allow_html=True)
                lc1,lc2,lc3 = st.columns(3)
                lc1.metric("Mode",       local.get("recommended","N/A").title())
                lc2.metric("Daily",      f"{currency} {_f(local.get('daily_cost',0)):,.0f}")
                lc3.metric("Total Stay", f"{currency} {_f(local.get('total_local_cost',0)):,.0f}")
                if local.get("tips"): st.info(f"💡 {local['tips']}")

        # ════ PLACES ══════════════════════════════════════════════════════════
        with tabs[3]:
            atts  = places.get("top_attractions",[])
            rests = places.get("restaurants",[])
            acts  = places.get("activities",[])
            if atts:
                st.markdown(sec("🗺️","Top Attractions"), unsafe_allow_html=True)
                for att in atts:
                    is_sk = att.get("name","") in skipped
                    fee_t = f'{currency} {_f(att.get("entry_fee",0)):,.0f}' if att.get("entry_fee") else "Free"
                    st.markdown(
                        f'<div style="background:#1E1E1E;border:1px solid #2E2E2E;border-radius:8px;'
                        f'padding:0.65rem 0.9rem;margin-bottom:0.4rem;opacity:{0.4 if is_sk else 1};">'
                        f'<div style="display:flex;justify-content:space-between;">'
                        f'<div><div style="color:#F0EAD6;font-weight:600;font-size:0.88rem;'
                        f'text-decoration:{"line-through" if is_sk else "none"};">{att.get("name","")}</div>'
                        f'<div style="margin-top:3px;">'
                        f'<span style="background:#C9A84C18;border:1px solid #C9A84C30;color:#C9A84C;border-radius:4px;padding:1px 6px;font-size:0.7rem;">{att.get("type","")}</span>'
                        f'<span style="color:#666;font-size:0.74rem;margin-left:8px;">⏱ {att.get("duration","")}</span>'
                        f'<span style="color:#C9A84C;font-size:0.74rem;margin-left:8px;">⭐ {att.get("rating","")}</span>'
                        f'</div></div>'
                        f'<span style="color:#C9A84C;font-weight:600;font-size:0.82rem;">🎟 {fee_t}</span>'
                        f'</div></div>', unsafe_allow_html=True
                    )
            cr, ca = st.columns(2)
            with cr:
                if rests:
                    st.markdown(sec("🍽️","Where to Eat"), unsafe_allow_html=True)
                    for r in rests:
                        st.markdown(
                            f'<div style="background:#1E1E1E;border:1px solid #2E2E2E;border-radius:8px;'
                            f'padding:0.65rem 0.9rem;margin-bottom:0.4rem;">'
                            f'<div style="color:#F0EAD6;font-weight:600;font-size:0.86rem;">{r.get("name","")}</div>'
                            f'<div style="color:#888;font-size:0.76rem;margin-top:2px;">'
                            f'{r.get("cuisine","")} · ⭐ {r.get("rating","")} · ~{currency} {_f(r.get("avg_cost_per_person",0)):,.0f}/person</div>'
                            f'<div style="color:#666;font-size:0.74rem;margin-top:2px;font-style:italic;">Try: {r.get("must_try_dish","")}</div>'
                            f'</div>', unsafe_allow_html=True
                        )
            with ca:
                if acts:
                    st.markdown(sec("🏄","Activities"), unsafe_allow_html=True)
                    for act in acts:
                        is_sk = act.get("name","") in skipped
                        st.markdown(
                            f'<div style="background:#1E1E1E;border:1px solid #2E2E2E;border-radius:8px;'
                            f'padding:0.65rem 0.9rem;margin-bottom:0.4rem;opacity:{0.4 if is_sk else 1};">'
                            f'<div style="color:#F0EAD6;font-weight:600;font-size:0.86rem;'
                            f'text-decoration:{"line-through" if is_sk else "none"};">{act.get("name","")}</div>'
                            f'<div style="margin-top:3px;">'
                            f'<span style="background:#C9A84C18;border:1px solid #C9A84C30;color:#C9A84C;border-radius:4px;padding:1px 6px;font-size:0.7rem;">{act.get("type","")}</span>'
                            f'<span style="color:#666;font-size:0.74rem;margin-left:6px;">⏱ {act.get("duration","")}</span>'
                            f'</div><div style="color:#2E7D52;font-weight:700;font-size:0.85rem;margin-top:4px;">'
                            f'{currency} {_f(act.get("cost_per_person",0)):,.0f}/person</div></div>',
                            unsafe_allow_html=True
                        )
            gems = places.get("hidden_gems",[])
            if gems:
                with st.expander("💎 Hidden Gems"):
                    for g in gems: st.markdown(f"• {g}")

        # ════ BUDGET ══════════════════════════════════════════════════════════
        with tabs[4]:
            st.markdown(sec("💰","Budget Breakdown","Actual agent estimates"), unsafe_allow_html=True)
            bc  = "#1F0D0D" if over else "#0D1F15"
            bbd = "#B02A2A" if over else "#2E7D52"
            st.markdown(
                f'<div style="background:{bc};border:2px solid {bbd};border-radius:10px;'
                f'padding:0.85rem 1.1rem;margin-bottom:1rem;display:flex;justify-content:space-between;">'
                f'<div><div style="font-weight:700;font-size:0.95rem;color:{"#FFB3B3" if over else "#90EE90"};">'
                f'{"⚠️ Over by " + currency + " " + f"{abs(surplus):,.0f}" if over else "✅ " + currency + " " + f"{surplus:,.0f}" + " to spare"}</div>'
                f'<div style="color:#888;font-size:0.78rem;">{budget.get("budget_status","").replace("_"," ").title()}</div>'
                f'</div><div style="text-align:right;">'
                f'<div style="color:#F0EAD6;font-weight:700;">{currency} {estimated:,.0f} est.</div>'
                f'<div style="color:#888;font-size:0.78rem;">Budget: {currency} {total_bgt:,.0f}</div>'
                f'</div></div>',
                unsafe_allow_html=True
            )
            if bd:
                cats = [
                    ("✈️ Transport",     bd.get("transport",0),     "#1A4A8A"),
                    ("🏨 Accommodation", bd.get("accommodation",0), "#C9A84C"),
                    ("🍽️ Food",          bd.get("food",0),          "#2E7D52"),
                    ("🎯 Activities",    bd.get("activities",0),    "#8B5CF6"),
                    ("🛍️ Misc",          bd.get("miscellaneous",0), "#555555"),
                ]
                for label, cost, color in cats:
                    cost = _f(cost)
                    pct  = (cost/estimated*100) if estimated > 0 else 0
                    st.markdown(
                        f'<div style="margin-bottom:0.8rem;">'
                        f'<div style="display:flex;justify-content:space-between;font-size:0.84rem;margin-bottom:3px;">'
                        f'<span style="color:#F0EAD6;">{label}</span>'
                        f'<span style="color:#F0EAD6;font-weight:700;">{currency} {cost:,.0f} '
                        f'<span style="color:#666;font-weight:400;font-size:0.74rem;">({pct:.0f}%)</span></span>'
                        f'</div><div style="background:#2E2E2E;border-radius:4px;height:6px;">'
                        f'<div style="background:{color};width:{min(pct,100):.1f}%;height:6px;border-radius:4px;"></div>'
                        f'</div></div>',
                        unsafe_allow_html=True
                    )
                daily = _f(budget.get("daily_budget", estimated/num_days if num_days else 0))
                st.markdown(
                    f'<div style="background:#1E1E1E;border:1px solid #2E2E2E;border-radius:7px;'
                    f'padding:0.55rem 0.9rem;display:flex;justify-content:space-between;">'
                    f'<span style="color:#888;font-size:0.84rem;">📆 Daily average</span>'
                    f'<span style="color:#C9A84C;font-weight:700;font-size:0.84rem;">{currency} {daily:,.0f}/day</span>'
                    f'</div>', unsafe_allow_html=True
                )
            tips = budget.get("optimization_tips",[])
            if tips:
                st.markdown(sec("💡","Save Money"), unsafe_allow_html=True)
                for tip in tips[:5]:
                    st.markdown(
                        f'<div style="background:#1E1E1E;border:1px solid #2E2E2E;border-left:3px solid #C9A84C;'
                        f'border-radius:0 7px 7px 0;padding:0.4rem 0.8rem;margin-bottom:0.3rem;'
                        f'font-size:0.82rem;color:#F0EAD6;">💡 {tip}</div>',
                        unsafe_allow_html=True
                    )

        # ════ WEATHER ════════════════════════════════════════════════════════
        with tabs[5]:
            if weather:
                w1,w2,w3,w4 = st.columns(4)
                w1.metric("🌡️ Day",       weather.get("avg_temp_day","N/A"))
                w2.metric("🌙 Night",     weather.get("avg_temp_night","N/A"))
                w3.metric("🌧️ Rainfall",  weather.get("rainfall","N/A").title())
                w4.metric("☀️ Condition", weather.get("conditions","N/A").title())
                st.markdown("<br>", unsafe_allow_html=True)
                wc1, wc2 = st.columns(2)
                with wc1:
                    b = weather.get("beach_suitable",True); o = weather.get("outdoor_suitable",True)
                    st.markdown(f'{"✅" if b else "❌"} **Beach activities**')
                    st.markdown(f'{"✅" if o else "❌"} **Outdoor activities**')
                    if weather.get("clothing_advice"): st.info(f"👕 {weather['clothing_advice']}")
                with wc2:
                    if weather.get("weather_summary"):
                        st.markdown(
                            f'<div style="background:#1E1E1E;border:1px solid #2E2E2E;border-radius:8px;'
                            f'padding:0.8rem;font-size:0.86rem;color:#F0EAD6;line-height:1.6;">'
                            f'{weather["weather_summary"]}</div>',
                            unsafe_allow_html=True
                        )
                for w in weather.get("weather_warnings",[]):
                    if w and len(w) > 3: st.warning(f"⚠️ {w}")

        # ════ PERSONALISE TAB (always visible) ═══════════════════════════════
        with tabs[6]:
            st.markdown(sec("⚙️","Personalise Your Plan","Changes rebuild itinerary dynamically"), unsafe_allow_html=True)

            p_tabs = st.tabs(["🏨 Hotels","✈️ Transport","🎯 Activities","📊 Summary"])

            # ── Hotels ────────────────────────────────────────────────────────
            with p_tabs[0]:
                st.markdown(
                    '<div style="color:#888;font-size:0.85rem;margin-bottom:0.8rem;">'
                    'Select a different hotel for any location. Hit Rebuild to update your plan.</div>',
                    unsafe_allow_html=True
                )
                locs    = st.session_state.get("itinerary_locations",[])
                orig_s  = dict(st.session_state.get("hotel_selections",{}))
                swap_s  = dict(st.session_state.get("overrun_hotel_swaps",{}))
                total_hotel_save = 0.0

                for loc in locs:
                    opts = opts_map.get(loc,[])
                    if not opts: continue
                    orig_idx   = orig_s.get(loc,1)
                    active_idx = swap_s.get(loc, orig_idx)
                    orig_ppn   = _f(opts[min(orig_idx,len(opts)-1)].get("price_per_night",0))
                    active_ppn = _f(opts[min(active_idx,len(opts)-1)].get("price_per_night",0))
                    loc_save   = (orig_ppn - active_ppn) * num_days

                    loc_border = "#2E7D52" if loc_save > 0 else ("#B02A2A" if loc_save < 0 else "#2E2E2E")
                    st.markdown(
                        f'<div style="background:#1E1E1E;border:2px solid {loc_border};'
                        f'border-radius:10px;padding:0.8rem 1rem;margin-bottom:0.5rem;">'
                        f'<div style="display:flex;justify-content:space-between;">'
                        f'<div><div style="color:#F0EAD6;font-weight:700;margin-bottom:2px;">📍 {loc}</div>'
                        f'<div style="color:#888;font-size:0.78rem;">Original: <b style="color:#C9A84C;">'
                        f'{opts[min(orig_idx,len(opts)-1)].get("name","N/A")}</b> — {currency}{orig_ppn:,.0f}/night</div>'
                        f'</div><div style="color:{"#90EE90" if loc_save > 0 else ("#FFB3B3" if loc_save < 0 else "#888")};font-size:0.82rem;font-weight:700;">'
                        f'{"Save " + currency + " " + f"{loc_save:,.0f}" if loc_save > 0 else ("+" + currency + " " + f"{abs(loc_save):,.0f}" if loc_save < 0 else "No change")}'
                        f'</div></div></div>',
                        unsafe_allow_html=True
                    )
                    hcols = st.columns(3)
                    for i, opt in enumerate(opts[:3]):
                        ppn  = _f(opt.get("price_per_night",0))
                        diff = (orig_ppn - ppn) * num_days
                        tier = opt.get("tier",f"Option {i+1}")
                        is_a = (i == active_idx)
                        is_o = (i == orig_idx)
                        if is_o and is_a: bc2, bbg = "#C9A84C", "#2A1F08"
                        elif is_a:        bc2, bbg = "#2E7D52",  "#0D1F15"
                        else:             bc2, bbg = "#2E2E2E",  "#1A1A1A"
                        with hcols[i]:
                            diff_html = (f'<div style="color:#90EE90;font-size:0.72rem;">Save {currency} {diff:,.0f}</div>' if diff > 0 and not is_o
                                         else (f'<div style="color:#FFB3B3;font-size:0.72rem;">+{currency} {abs(diff):,.0f}</div>' if diff < 0
                                               else f'<div style="color:#888;font-size:0.72rem;">Original</div>'))
                            sel_lbl = "✓ Picked" if is_a else f"Pick {tier}"
                            st.markdown(
                                f'<div style="background:{bbg};border:2px solid {bc2};border-radius:8px;'
                                f'padding:0.65rem;text-align:center;min-height:95px;">'
                                f'<div style="color:#F0EAD6;font-weight:700;font-size:0.82rem;">{tier}</div>'
                                f'<div style="color:#F0EAD6;font-weight:800;font-size:0.9rem;margin:2px 0;">{currency} {ppn:,.0f}/night</div>'
                                f'{diff_html}'
                                f'{"<div style=color:#C9A84C;font-size:0.68rem;>★ Original</div>" if is_o and is_a else ""}'
                                f'</div>', unsafe_allow_html=True
                            )
                            st.markdown("<br style=margin:0;>", unsafe_allow_html=True)
                            if st.button(sel_lbl, key=f"ps_{loc}_{i}", use_container_width=True,
                                         type="primary" if is_a else "secondary"):
                                swap_s[loc] = i
                                st.session_state["overrun_hotel_swaps"] = swap_s
                                st.rerun()

                    final_idx = swap_s.get(loc, orig_idx)
                    final_ppn = _f(opts[min(final_idx,len(opts)-1)].get("price_per_night",0))
                    total_hotel_save += max(0.0, (orig_ppn - final_ppn) * num_days)

                has_hotel_changes = any(swap_s.get(l, orig_s.get(l,1)) != orig_s.get(l,1) for l in locs)
                st.markdown(
                    f'<div style="background:#1E1E1E;border:2px solid {"#2E7D52" if total_hotel_save > 0 else "#2E2E2E"};'
                    f'border-radius:10px;padding:0.8rem 1rem;margin-top:0.5rem;">'
                    f'<div style="color:{"#90EE90" if total_hotel_save > 0 else "#888"};font-weight:700;">'
                    f'Hotel savings: {currency} {total_hotel_save:,.0f}</div>'
                    f'<div style="color:#666;font-size:0.78rem;">'
                    f'{"Click Rebuild to apply changes" if has_hotel_changes else "No changes yet"}</div></div>',
                    unsafe_allow_html=True
                )

            # ── Transport ─────────────────────────────────────────────────────
            with p_tabs[1]:
                st.markdown(
                    '<div style="color:#888;font-size:0.85rem;margin-bottom:0.8rem;">'
                    'Change your preferred transport mode. Rebuild will regenerate transport options.</div>',
                    unsafe_allow_html=True
                )
                current_pref = prefs.get("transport_preference","flight")
                custom_t     = st.session_state.get("custom_transport", current_pref)
                modes = ["flight","train","bus","car"]
                sel_mode = st.radio(
                    "Preferred Transport Mode",
                    modes,
                    index=modes.index(custom_t) if custom_t in modes else 0,
                    horizontal=True, key="transport_radio"
                )
                if sel_mode != custom_t:
                    st.session_state["custom_transport"] = sel_mode

                # Show all alternatives for reference
                alts_ref = transport.get("alternative_options",[])
                if alts_ref:
                    st.markdown(sec("🔄","Available Options"), unsafe_allow_html=True)
                    for alt in alts_ref:
                        st.markdown(
                            f'<div style="background:#1E1E1E;border:1px solid #2E2E2E;border-radius:8px;'
                            f'padding:0.6rem 0.9rem;margin-bottom:0.4rem;'
                            f'display:flex;justify-content:space-between;">'
                            f'<div><span style="color:#F0EAD6;font-weight:600;">{alt.get("mode","").title()}</span>'
                            f'<span style="color:#888;font-size:0.78rem;margin-left:8px;">⏱ {alt.get("duration","N/A")}</span>'
                            f'<div style="color:#555;font-size:0.74rem;">{alt.get("notes","")}</div></div>'
                            f'<span style="color:#C9A84C;font-weight:700;">{currency} {_f(alt.get("price_per_person",0)):,.0f}/person</span>'
                            f'</div>', unsafe_allow_html=True
                        )

            # ── Activities ────────────────────────────────────────────────────
            with p_tabs[2]:
                st.markdown(
                    '<div style="color:#888;font-size:0.85rem;margin-bottom:0.8rem;">'
                    'Remove activities to reduce costs. Rebuild will update the itinerary.</div>',
                    unsafe_allow_html=True
                )
                act_save = 0.0
                for act in places.get("activities",[]):
                    name = act.get("name","")
                    cost = _f(act.get("cost_per_person",0)) * prefs.get("travelers",2)
                    is_sk = name in skipped
                    ac1, ac2, ac3 = st.columns([3,1,1])
                    with ac1:
                        st.markdown(
                            f'<div style="color:{"#555" if is_sk else "#F0EAD6"};'
                            f'text-decoration:{"line-through" if is_sk else "none"};'
                            f'font-size:0.86rem;padding:6px 0;">'
                            f'{name} <span style="color:#C9A84C;">({act.get("type","")})</span></div>',
                            unsafe_allow_html=True
                        )
                    with ac2:
                        st.markdown(f'<div style="color:#F0EAD6;font-size:0.84rem;padding:6px 0;">{currency} {cost:,.0f}</div>', unsafe_allow_html=True)
                    with ac3:
                        if is_sk:
                            if st.button("Add ✓", key=f"add_act_{name[:8]}", type="secondary"):
                                skipped.remove(name); st.session_state["skipped_activities"] = skipped; st.rerun()
                        else:
                            if st.button("Remove", key=f"rm_act_{name[:8]}", type="secondary"):
                                skipped.append(name); st.session_state["skipped_activities"] = skipped; st.rerun()
                    if is_sk: act_save += cost

                for att in places.get("top_attractions",[]):
                    if not att.get("entry_fee"): continue
                    name = att.get("name","")
                    cost = _f(att.get("entry_fee",0)) * prefs.get("travelers",2)
                    is_sk = name in skipped
                    ac1, ac2, ac3 = st.columns([3,1,1])
                    with ac1:
                        st.markdown(f'<div style="color:{"#555" if is_sk else "#F0EAD6"};text-decoration:{"line-through" if is_sk else "none"};font-size:0.84rem;padding:4px 0;">{name} (entry)</div>', unsafe_allow_html=True)
                    with ac2:
                        st.markdown(f'<div style="color:#F0EAD6;font-size:0.82rem;padding:4px 0;">{currency} {cost:,.0f}</div>', unsafe_allow_html=True)
                    with ac3:
                        if is_sk:
                            if st.button("Add ✓", key=f"add_att_{name[:8]}", type="secondary"):
                                skipped.remove(name); st.session_state["skipped_activities"] = skipped; st.rerun()
                        else:
                            if st.button("Remove", key=f"rm_att_{name[:8]}", type="secondary"):
                                skipped.append(name); st.session_state["skipped_activities"] = skipped; st.rerun()
                    if is_sk: act_save += cost
                if act_save > 0:
                    st.success(f"✅ Activity savings: {currency} {act_save:,.0f}")

            # ── Summary ───────────────────────────────────────────────────────
            with p_tabs[3]:
                swap_s  = st.session_state.get("overrun_hotel_swaps",{})
                skipped = st.session_state.get("skipped_activities",[])
                locs_   = st.session_state.get("itinerary_locations",[])
                hs = 0.0
                for loc in locs_:
                    opts = opts_map.get(loc,[])
                    oi   = orig_s.get(loc,1)
                    si   = swap_s.get(loc, oi)
                    if opts and si != oi:
                        op = _f(opts[min(oi,len(opts)-1)].get("price_per_night",0))
                        sp = _f(opts[min(si,len(opts)-1)].get("price_per_night",0))
                        hs += max(0, (op-sp)*num_days)
                as_ = sum(_f(a.get("cost_per_person",0))*prefs.get("travelers",2)
                          for a in places.get("activities",[]) if a.get("name","") in skipped)
                ts_ = hs + as_
                ne_ = estimated - ts_
                ns_ = total_bgt - ne_

                rows = [
                    ("Original estimate",   f"{currency} {estimated:,.0f}",  "#F0EAD6"),
                    ("Hotel savings",        f"− {currency} {hs:,.0f}",       "#90EE90"),
                    ("Activity savings",     f"− {currency} {as_:,.0f}",      "#90EE90"),
                    ("New estimate",         f"{currency} {ne_:,.0f}",        "#F0EAD6"),
                    ("Your budget",          f"{currency} {total_bgt:,.0f}",  "#F0EAD6"),
                    ("New surplus/deficit",
                     f"{'+ ' if ns_>=0 else '− '}{currency} {abs(ns_):,.0f}",
                     "#90EE90" if ns_>=0 else "#FFB3B3"),
                ]
                for label, val, color in rows:
                    st.markdown(
                        f'<div style="background:#1E1E1E;border:1px solid #2E2E2E;border-radius:7px;'
                        f'padding:0.45rem 0.9rem;margin-bottom:0.3rem;display:flex;justify-content:space-between;">'
                        f'<span style="color:#888;font-size:0.85rem;">{label}</span>'
                        f'<span style="color:{color};font-weight:700;font-size:0.88rem;">{val}</span></div>',
                        unsafe_allow_html=True
                    )
                if ns_ >= 0: st.success(f"✅ You'll be {currency} {ns_:,.0f} within budget!")
                else:        st.warning(f"⚠️ Still {currency} {abs(ns_):,.0f} over. Remove more activities.")

            # ── REBUILD BUTTON ─────────────────────────────────────────────────
            st.markdown("<br>", unsafe_allow_html=True)
            swap_s_now = st.session_state.get("overrun_hotel_swaps",{})
            custom_t_now = st.session_state.get("custom_transport", prefs.get("transport_preference","flight"))
            has_changes = (
                any(swap_s_now.get(l, orig_s.get(l,1)) != orig_s.get(l,1)
                    for l in st.session_state.get("itinerary_locations",[]))
                or bool(st.session_state.get("skipped_activities",[]))
                or custom_t_now != prefs.get("transport_preference","flight")
            )

            rb_col, rst_col = st.columns(2)
            with rb_col:
                if st.button(
                    "✨  Rebuild Itinerary",
                    type="primary", use_container_width=True,
                    key="rebuild_btn"
                ):
                    merged = dict(orig_s); merged.update(swap_s_now)
                    st.session_state["hotel_selections"] = merged
                    custom_final = custom_t_now if custom_t_now != prefs.get("transport_preference") else None
                    with st.spinner("⚙️ Rebuilding your personalised itinerary…"):
                        ok = rebuild_itinerary(
                            merged, opts_map,
                            st.session_state.get("skipped_activities",[]),
                            custom_final
                        )
                    if ok:
                        st.session_state["overrun_hotel_swaps"] = {}
                        st.session_state["chat_messages"].append({
                            "role":"bot",
                            "content":"✅ Itinerary rebuilt with your choices! PDF updated.",
                            "type":"status"
                        })
                        st.success("✅ Itinerary rebuilt!")
                        st.rerun()
                    else:
                        st.error("❌ Rebuild failed — partial update saved.")
            with rst_col:
                if st.button("↩ Reset Changes", type="secondary",
                             use_container_width=True, key="rst_btn"):
                    st.session_state["overrun_hotel_swaps"]  = {}
                    st.session_state["skipped_activities"]   = []
                    st.session_state["custom_transport"]     = None
                    st.rerun()

        # ── Evaluation dashboard ───────────────────────────────────────────────
        if EVALUATION_ENABLED:
            try:
                eval_report = evaluate_trip_result(result, prefs)
                render_evaluation_dashboard(eval_report)
            except Exception as eval_err:
                pass  # non-fatal

        # ── PDF download ───────────────────────────────────────────────────────
        if pdf_path and Path(pdf_path).exists():
            st.markdown("<br>", unsafe_allow_html=True)
            st.divider()
            st.download_button(
                "📥  Download Full PDF Report",
                data=Path(pdf_path).read_bytes(),
                file_name=Path(pdf_path).name,
                mime="application/pdf",
                use_container_width=True,
            )

# ══════════════════════════════════════════════════════════════════════════════
# APPLY GUARDRAILS HELPER
# ══════════════════════════════════════════════════════════════════════════════

def _show_guardrail_block(reason, category=""):
    icon_map = {"scope":"🌍","abuse":"⚠️","hate":"🚫","pii":"🔒"}
    icon = icon_map.get(category,"🚫")
    st.markdown(
        f'<div style="background:#1F0D0D;border:2px solid #B02A2A;border-radius:10px;'
        f'padding:0.9rem 1.1rem;margin:0.5rem 0;">'
        f'<div style="font-weight:700;color:#FFB3B3;margin-bottom:4px;">{icon} Blocked</div>'
        f'<div style="color:#888;font-size:0.88rem;">{reason}</div></div>',
        unsafe_allow_html=True
    )

def _show_pii_notice():
    st.markdown(
        '<div style="background:#1A1400;border:1px solid #C9A84C;border-radius:7px;'
        'padding:0.35rem 0.8rem;margin-bottom:0.4rem;font-size:0.76rem;color:#C9A84C;">'
        '🔒 Personal information masked for your security.</div>',
        unsafe_allow_html=True
    )

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def _check_rate_limit() -> tuple:
    """
    Check if user is within rate limits.
    Returns (allowed: bool, message: str)
    """
    import time
    count     = st.session_state.get("query_count", 0)
    last_time = st.session_state.get("last_query_time", 0.0)
    now       = time.time()
    elapsed   = now - last_time

    if count >= RATE_LIMIT_MAX_QUERIES:
        return False, (
            f"🚦 You've reached the session limit of {RATE_LIMIT_MAX_QUERIES} trip plans. "
            f"Please start a new session or wait a few minutes."
        )

    if elapsed < RATE_LIMIT_COOLDOWN_SECS and count > 0:
        wait = int(RATE_LIMIT_COOLDOWN_SECS - elapsed)
        return False, (
            f"⏳ Please wait {wait} seconds before planning another trip."
        )

    return True, ""


def _increment_rate_limit():
    """Increment query counter and record timestamp."""
    import time
    st.session_state["query_count"]     = st.session_state.get("query_count", 0) + 1
    st.session_state["last_query_time"] = time.time()


def main():
    stage = st.session_state["flow_stage"]

    # ── Two-column layout (except hero) ───────────────────────────────────────
    show_chat = stage not in ("hero",)
    if show_chat:
        chat_col, main_col = st.columns([1, 2.8], gap="medium")
        st.markdown(
            '<div style="max-width:100%;padding:1rem 0.5rem 0 0.5rem;">',
            unsafe_allow_html=True
        )
    else:
        chat_col = None
        main_col = st.container()

    # ════════════════════════════════════════════════════════════════════════════
    if stage == "hero":
        render_hero()

    elif stage == "clarifying":
        render_chat(chat_col)
        with main_col:
            st.markdown(
                '<div style="background:linear-gradient(135deg,#0D1324,#111A2E);'
                'border:2px solid #1A4A8A;border-radius:14px;'
                'padding:2.5rem;text-align:center;margin-top:2rem;">'
                '<div style="font-size:2.8rem;margin-bottom:1rem;">✈️</div>'
                '<div style="font-family:Playfair Display,serif;font-size:1.3rem;font-weight:700;'
                'color:#F0EAD6;margin-bottom:0.5rem;">Just a few more details…</div>'
                '<div style="color:#888;font-size:0.9rem;line-height:1.6;max-width:380px;margin:0 auto;">'
                'Our AI concierge is gathering everything needed to craft your perfect personalised journey.'
                '<br><br><span style="color:#C9A84C;">Answer the questions on the left ←</span>'
                '</div></div>',
                unsafe_allow_html=True
            )

    elif stage == "planning":
        render_chat(chat_col)
        with main_col:
            st.markdown(
                '<div style="background:linear-gradient(135deg,#1A1400,#252510);'
                'border:2px solid #C9A84C;border-radius:14px;'
                'padding:1.2rem 1.5rem;margin-top:1rem;">'
                '<div style="font-family:Playfair Display,serif;font-size:1rem;font-weight:700;'
                'color:#C9A84C;margin-bottom:0.5rem;">⚙️ AI agents are crafting your journey…</div>'
                '<div style="color:#888;font-size:0.82rem;">Live agent logs:</div>'
                '</div>',
                unsafe_allow_html=True
            )
            # Live log container
            log_placeholder = st.empty()
            try:
                prefs = st.session_state["trip_preferences"]
                parts = []
                if prefs.get("num_days"):    parts.append(f"{prefs['num_days']}-day")
                if prefs.get("destination"): parts.append(f"trip to {prefs['destination']}")
                if prefs.get("source"):      parts.append(f"from {prefs['source']}")
                if prefs.get("travelers"):   parts.append(f"for {prefs['travelers']} travellers")
                if prefs.get("budget"):      parts.append(f"budget {prefs.get('currency','INR')}{prefs['budget']}")
                sq = " ".join(parts) if parts else st.session_state.get("initial_query","Plan my trip")

                _increment_rate_limit()
                result = run_planning(sq, is_refine=False)
                if result:
                    result["trip_preferences"] = {**result.get("trip_preferences",{}), **prefs}
                    st.session_state["result"] = result

                    with st.spinner("🏨 Generating hotel options for each location…"):
                        result = run_hotel_options(result)

                    st.session_state.update({
                        "result":               result,
                        "hotel_options_by_loc": result.get("hotel_options_by_location",{}),
                        "itinerary_locations":  result.get("itinerary_locations",[]),
                        "hotel_selection_step": 0,
                        "flow_stage":           "selecting_hotels",
                    })
                    st.session_state["chat_messages"].append({
                        "role":"bot",
                        "content":"✅ Your journey is planned! Now let's pick your hotels.",
                        "type":"status"
                    })
            except Exception as e:
                st.error(f"❌ Planning failed: {e}")
                with st.expander("Error details"):
                    import traceback; st.code(traceback.format_exc())
                st.session_state["flow_stage"] = "hero"
            st.rerun()

    elif stage == "selecting_hotels":
        render_chat(chat_col)
        render_hotel_selection(main_col)

    elif stage == "complete":
        render_chat(chat_col)
        result = st.session_state.get("result",{})
        if not result:
            st.error("No result — start a new trip.")
            return
        result["trip_preferences"].update(st.session_state["trip_preferences"])
        render_results(main_col, result)

    else:
        render_hero()

if __name__ == "__main__":
    main()
