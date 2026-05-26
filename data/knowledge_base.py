"""
data/knowledge_base.py — Travel Knowledge Base & FAISS Index Builder
====================================================================
Populates a FAISS vector store with structured travel data covering
destinations, hotels, transport, weather, attractions, restaurants, and tips.

Run directly:  python -m data.knowledge_base
or import:     from data.knowledge_base import build_index, load_index
"""

import json
import pickle
import logging
from pathlib import Path
from typing import List, Dict, Any

import faiss
import numpy as np
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS as LangchainFAISS

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    OPENAI_API_KEY, EMBEDDING_MODEL, FAISS_INDEX_PATH, logger
)

# ── Raw Travel Documents ──────────────────────────────────────────────────────

TRAVEL_DOCUMENTS: List[Dict[str, Any]] = [

    # ── GOA ──────────────────────────────────────────────────────────────────
    {
        "content": (
            "Goa is India's premier beach destination on the western coast. "
            "Best visited October–March with pleasant weather (20–32°C). "
            "Famous for: Baga Beach, Calangute Beach, Anjuna Beach, Vagator Beach, "
            "Palolem Beach (south Goa). Water sports: parasailing, jet ski, banana boat. "
            "Nightlife hubs: Tito's Lane, Club Cubana, Sinq Nightclub. "
            "Heritage: Old Goa churches (Se Cathedral, Basilica of Bom Jesus), "
            "Fontainhas Latin Quarter, Chapora Fort, Aguada Fort."
        ),
        "metadata": {
            "destination": "Goa",
            "category": "destination_overview",
            "location": "Goa, India",
            "rating": 4.5,
            "best_season": "October–March",
            "price_range": "budget_to_luxury",
        },
    },
    {
        "content": (
            "Goa weather December: Day 27–32°C, Night 18–22°C. Sunny with low humidity. "
            "Ideal for beach activities and outdoor sightseeing. "
            "January: similar, festive season with New Year events. "
            "November: slightly humid but good. Monsoon June–September: heavy rainfall, "
            "beaches close, many shacks shut."
        ),
        "metadata": {
            "destination": "Goa",
            "category": "weather",
            "location": "Goa, India",
            "season": "winter",
        },
    },
    {
        "content": (
            "Goa Hotels – Beach Resorts (Budget ₹30,000 for couple 5 nights): "
            "1. Taj Holiday Village Resort & Spa, Sinquerim – 5★ ₹8,000–12,000/night. "
            "2. W Goa, Vagator – 5★ ₹10,000–15,000/night, stunning infinity pool. "
            "3. Alila Diwa Goa, Majorda – 5★ ₹7,000–9,000/night, South Goa. "
            "4. Kenilworth Beach Resort, Calangute – 4★ ₹4,000–6,000/night. "
            "5. The Acacia Hotel & Spa – 3★ ₹2,500–4,000/night, beachfront. "
            "6. Zostel Goa (Anjuna) – hostel ₹700–1,500/bed. "
            "Mid-range pick for couples: Kenilworth (₹4,500/night incl breakfast) "
            "→ 5 nights = ₹22,500, stays within ₹30k budget."
        ),
        "metadata": {
            "destination": "Goa",
            "category": "hotels",
            "location": "Goa, India",
            "price_range": "budget_to_luxury",
            "rating": 4.2,
        },
    },
    {
        "content": (
            "Goa Flights from Bangalore (BLR → GOI): "
            "IndiGo: ₹2,500–4,500 one way, duration 1h 10m, daily 6–8 flights. "
            "Air India: ₹3,000–5,500 one way. SpiceJet: ₹2,200–4,000. "
            "Vistara: ₹3,500–6,000 (premium). Book 30+ days ahead for best rates. "
            "Return flight budget for couple: ₹5,000–8,000 (both ways). "
            "Alternatives: Goa Express train (16:30h, ₹1,200–2,500/person), "
            "Bus (Sleeper ₹600–900/person). Flight is fastest for 5-day trip."
        ),
        "metadata": {
            "destination": "Goa",
            "category": "transport",
            "route": "Bangalore to Goa",
            "transport_type": "flight",
            "price_range": "medium",
        },
    },
    {
        "content": (
            "Goa Food & Restaurants: "
            "Seafood specialties: Fish Curry Rice, Prawn Balchão, Goan Crab Masala, Rava Fried Fish. "
            "Must-visit: Fisherman's Wharf (₹800–1,500/person), "
            "Gunpowder Assagao (modern Indian ₹600–1,200), "
            "Thalassa Vagator (Greek-Goan fusion ₹1,000–1,800), "
            "Martin's Corner Betalbatim (local legend ₹400–800), "
            "Britto's Baga Beach (₹500–1,000). "
            "Street food: Ros Omelette (₹50), Choriz Pav (₹30), Bebinca dessert."
        ),
        "metadata": {
            "destination": "Goa",
            "category": "food",
            "cuisine": "Goan/Seafood",
            "price_range": "budget_to_medium",
        },
    },
    {
        "content": (
            "Goa Day-Wise Itinerary Skeleton (5 days): "
            "Day 1: Arrive → Check-in resort → Baga Beach sunset → Tito's nightlife. "
            "Day 2: North Goa: Calangute, Anjuna Flea Market (Wed/Sat), Vagator cliff. "
            "Day 3: Heritage trail – Old Goa churches, Fontainhas, Panjim cafés. "
            "Day 4: South Goa – Palolem Beach, Agonda Beach, boat trip. "
            "Day 5: Water sports at Baga, souvenir shopping, departure. "
            "Transport in Goa: Rented scooter (₹300–500/day) or taxi (₹1,500–2,500/day)."
        ),
        "metadata": {
            "destination": "Goa",
            "category": "itinerary",
            "duration": "5 days",
            "travel_type": "couple",
        },
    },
    {
        "content": (
            "Goa Budget Breakdown (Couple, 5 Days, ₹30,000): "
            "Flights (BLR-GOI return, 2 pax): ₹8,000–10,000. "
            "Hotel (mid-range resort, 5 nights): ₹18,000–22,500. "
            "Food (₹800/person/day): ₹8,000. "
            "Local transport (scooter/taxi): ₹2,500. "
            "Activities & entry fees: ₹1,500. "
            "Miscellaneous (shopping, nightlife): ₹2,000. "
            "TOTAL ESTIMATE: ₹40,000–46,500. "
            "To stay within ₹30k: Take train (save ₹5k), choose 3★ hotel (save ₹8k), "
            "cook/eat budget local food (save ₹3k) → achievable at ₹28,000–32,000."
        ),
        "metadata": {
            "destination": "Goa",
            "category": "budget",
            "travel_type": "couple",
            "budget_range": "30000_INR",
        },
    },

    # ── MANALI ───────────────────────────────────────────────────────────────
    {
        "content": (
            "Manali is a Himalayan hill station in Himachal Pradesh, India. "
            "Best season: Oct–June (pre-monsoon). December–Feb: snow, adventure sports. "
            "Key attractions: Rohtang Pass (3,978m, snow), Solang Valley (skiing, zorbing), "
            "Hadimba Devi Temple, Old Manali Market, Vashisht hot springs, "
            "Kullu Valley, Beas River rafting, Chandrakhani Pass trek."
        ),
        "metadata": {
            "destination": "Manali",
            "category": "destination_overview",
            "location": "Himachal Pradesh, India",
            "rating": 4.4,
            "best_season": "Oct–June",
            "price_range": "budget_to_medium",
        },
    },
    {
        "content": (
            "Manali Hotels: "
            "1. Span Resort & Spa – 5★ ₹8,000–12,000/night, riverside. "
            "2. Hotel Banjara Camps & Retreat – 4★ ₹5,000–7,000/night. "
            "3. Manu Allaya Resort – 4★ ₹4,000–6,000/night. "
            "4. Hotel Rockside – 3★ ₹1,500–2,500/night, good value. "
            "5. Zostel Manali – hostel ₹500–900/bed. "
            "Family recommendation: Hotel Rockside or Manu Allaya."
        ),
        "metadata": {
            "destination": "Manali",
            "category": "hotels",
            "location": "Manali, HP",
            "price_range": "budget_to_luxury",
            "rating": 4.0,
        },
    },
    {
        "content": (
            "Delhi to Manali transport options: "
            "1. HPTDC Volvo Bus: ₹700–1,200/person, 14–16 hours overnight. "
            "2. Private cab: ₹4,000–6,000 for sedan (one way). "
            "3. Flight: Delhi–Kullu (Bhuntar Airport) ₹3,000–6,000, then taxi 2h. "
            "Taxi within Manali: ₹1,500–2,500/day (full cab). "
            "Bike rental: ₹500–800/day (Royal Enfield)."
        ),
        "metadata": {
            "destination": "Manali",
            "category": "transport",
            "route": "Delhi to Manali",
            "price_range": "budget_to_medium",
        },
    },

    # ── KERALA ───────────────────────────────────────────────────────────────
    {
        "content": (
            "Kerala – 'God's Own Country' on India's southwest coast. "
            "Highlights: Alleppey backwaters (houseboat), Munnar tea estates, "
            "Wayanad wildlife, Kovalam beach, Varkala cliffs, Fort Kochi heritage, "
            "Thekkady wildlife sanctuary. "
            "Best time: Oct–Feb. Monsoon (June–Aug) for Ayurveda retreats. "
            "Famous: Kerala Ayurveda, Kathakali dance, Kalaripayattu martial art."
        ),
        "metadata": {
            "destination": "Kerala",
            "category": "destination_overview",
            "location": "Kerala, India",
            "rating": 4.6,
            "best_season": "October–February",
            "price_range": "budget_to_luxury",
        },
    },
    {
        "content": (
            "Kerala Houseboat Experience (Alleppey/Kumarakom): "
            "Private AC houseboat (1 bedroom, couple): ₹8,000–12,000/night all-inclusive. "
            "2-bedroom family houseboat: ₹12,000–18,000/night. "
            "Includes: bedroom, living area, sit-out deck, cook onboard, meals. "
            "Route: Alleppey → Vembanad Lake → Kuttanad paddy fields. "
            "Book via: Kerala Tourism (keralatourism.org), Airbnb, or local operators."
        ),
        "metadata": {
            "destination": "Kerala",
            "category": "hotels",
            "accommodation_type": "houseboat",
            "location": "Alleppey, Kerala",
            "price_range": "medium_to_luxury",
            "rating": 4.7,
        },
    },

    # ── RAJASTHAN ────────────────────────────────────────────────────────────
    {
        "content": (
            "Rajasthan Golden Triangle (Jaipur–Jodhpur–Jaisalmer): "
            "Jaipur (Pink City): Amber Fort, City Palace, Hawa Mahal, Jantar Mantar. "
            "Jodhpur (Blue City): Mehrangarh Fort, Jaswant Thada, Umaid Bhawan. "
            "Jaisalmer (Golden City): Sam Sand Dunes (camel safari), Jaisalmer Fort. "
            "Udaipur (City of Lakes): Lake Pichola, City Palace, Sajjangarh. "
            "Best time: Oct–March. Summer very hot (40–48°C)."
        ),
        "metadata": {
            "destination": "Rajasthan",
            "category": "destination_overview",
            "location": "Rajasthan, India",
            "rating": 4.5,
            "best_season": "October–March",
            "price_range": "budget_to_luxury",
        },
    },
    {
        "content": (
            "Rajasthan Heritage Hotels (Palace Hotels): "
            "1. Taj Lake Palace, Udaipur – 5★ ₹25,000–50,000/night (floating palace). "
            "2. Umaid Bhawan Palace, Jodhpur – 5★ ₹20,000–40,000/night. "
            "3. Samode Palace, Jaipur – 5★ ₹8,000–15,000/night. "
            "4. Zostel Jaipur – hostel ₹400–800/bed. "
            "Budget: OYO/Treebo properties ₹1,200–2,500/night in all cities."
        ),
        "metadata": {
            "destination": "Rajasthan",
            "category": "hotels",
            "accommodation_type": "heritage_palace",
            "location": "Rajasthan, India",
            "price_range": "medium_to_luxury",
            "rating": 4.5,
        },
    },

    # ── INTERNATIONAL: BALI ──────────────────────────────────────────────────
    {
        "content": (
            "Bali, Indonesia – The Island of Gods. "
            "Best time: April–October (dry season). "
            "Key areas: Seminyak (beach clubs, luxury), Ubud (culture, rice terraces), "
            "Nusa Dua (family resort zone), Canggu (surf, digital nomad vibe), "
            "Uluwatu (clifftop temples, surf). "
            "Must-do: Tegallalang Rice Terrace, Tanah Lot sunset, Uluwatu Kecak dance, "
            "Mount Batur sunrise trek, Ubud Monkey Forest, cooking class."
        ),
        "metadata": {
            "destination": "Bali",
            "category": "destination_overview",
            "location": "Bali, Indonesia",
            "rating": 4.7,
            "best_season": "April–October",
            "price_range": "budget_to_luxury",
        },
    },
    {
        "content": (
            "Bali Hotels & Villas: "
            "Luxury villas (private pool, 2 pax): USD 80–200/night. "
            "1. The Layar, Seminyak – 5★ USD 500+/night (ultra-luxury). "
            "2. Komaneka at Bisma, Ubud – 5★ USD 300–400/night. "
            "3. Alaya Resort Ubud – 4★ USD 150–200/night. "
            "4. Sanur Beach Villas – 3★ USD 80–120/night. "
            "Budget: Hostel/guesthouse USD 10–30/night in Canggu/Ubud. "
            "Best value: Airbnb private villa USD 60–100/night (Ubud/Canggu)."
        ),
        "metadata": {
            "destination": "Bali",
            "category": "hotels",
            "location": "Bali, Indonesia",
            "price_range": "budget_to_luxury",
            "currency": "USD",
            "rating": 4.5,
        },
    },
    {
        "content": (
            "Flights to Bali (Ngurah Rai Intl, DPS) from India: "
            "Mumbai (BOM–DPS): IndiGo/AirAsia ₹18,000–30,000 return. "
            "Delhi (DEL–DPS): ₹22,000–35,000 return (often via Singapore/KL). "
            "Bangalore (BLR–DPS): ₹20,000–32,000 return. "
            "Direct flights: Garuda Indonesia, Air India (seasonal). "
            "Duration: 5–8 hours depending on route. Visa on Arrival: USD 35 (30 days)."
        ),
        "metadata": {
            "destination": "Bali",
            "category": "transport",
            "transport_type": "international_flight",
            "price_range": "medium",
        },
    },

    # ── INTERNATIONAL: PARIS ─────────────────────────────────────────────────
    {
        "content": (
            "Paris, France – The City of Light. "
            "Best time: April–June, September–October (mild, fewer crowds). "
            "Iconic sights: Eiffel Tower, Louvre Museum, Notre Dame, Arc de Triomphe, "
            "Montmartre, Sacré-Cœur, Musée d'Orsay, Palace of Versailles (day trip). "
            "Romantic: Seine river cruise, Trocadéro view, Palais Royal, Luxembourg Gardens. "
            "Shopping: Champs-Élysées, Le Marais boutiques, Galeries Lafayette."
        ),
        "metadata": {
            "destination": "Paris",
            "category": "destination_overview",
            "location": "Paris, France",
            "rating": 4.8,
            "best_season": "April–June, September–October",
            "price_range": "medium_to_luxury",
        },
    },
    {
        "content": (
            "Paris Hotels: "
            "1. Ritz Paris – 5★ EUR 1,500–5,000/night. "
            "2. Le Bristol Paris – 5★ EUR 800–1,500/night. "
            "3. Hotel Le Marais – 4★ EUR 200–350/night, great location. "
            "4. Hotel du Petit Moulin – 4★ EUR 180–280/night (boutique). "
            "5. Generator Paris – hostel EUR 30–60/dorm, EUR 90–130 private. "
            "Metro: excellent network, day pass EUR 8. "
            "Budget tip: Stay near Bastille/République for value + metro access."
        ),
        "metadata": {
            "destination": "Paris",
            "category": "hotels",
            "location": "Paris, France",
            "price_range": "medium_to_luxury",
            "currency": "EUR",
            "rating": 4.4,
        },
    },

    # ── GENERAL TRAVEL TIPS ──────────────────────────────────────────────────
    {
        "content": (
            "Emergency Travel Tips – India: "
            "Tourist Helpline: 1363 (24/7). Police: 100. Ambulance: 108. "
            "Travel insurance: Always buy before departure (covers medical, cancellation). "
            "Store copies of passport/ID in cloud (Google Drive/email). "
            "IRCTC app for train bookings. MakeMyTrip/Goibibo for flights & hotels. "
            "UPI payments widely accepted (PhonePe, GPay). "
            "Medical: Apollo, Fortis hospitals in major cities."
        ),
        "metadata": {
            "destination": "India",
            "category": "emergency_tips",
            "location": "India",
        },
    },
    {
        "content": (
            "International Travel Checklist: "
            "Documents: Passport (6+ months validity), visa, insurance, forex card. "
            "Health: Vaccinations as required, travel sickness medicine, first-aid kit. "
            "Finance: Notify bank before travel, carry some local cash, Wise/Revolut card. "
            "Tech: Download offline maps (Maps.me), translation app, local SIM plan. "
            "Packing: Weather-appropriate clothes, universal adapter, power bank. "
            "Safety: Share itinerary with family, register with embassy (for long trips)."
        ),
        "metadata": {
            "destination": "International",
            "category": "packing_checklist",
            "location": "Global",
        },
    },
    {
        "content": (
            "Budget Optimization Tips for Travel: "
            "1. Book flights 6–8 weeks in advance for domestic, 3–6 months for international. "
            "2. Travel shoulder season (avoid peak holidays) – 30–50% cheaper. "
            "3. Use Hostelworld/Zostel for budget stays, Airbnb for groups (split cost). "
            "4. Google Flights 'Explore' map to find cheapest destination. "
            "5. City tourist passes (museum/transport bundles) often save 20–40%. "
            "6. Eat where locals eat – half the price, twice the authenticity. "
            "7. Train > Bus > Flight for short trips (< 500 km). "
            "8. Travel credit cards for air miles (HDFC Regalia, SBI Elite)."
        ),
        "metadata": {
            "destination": "Global",
            "category": "budget_tips",
            "price_range": "budget",
        },
    },
    {
        "content": (
            "Visa Information – Popular Destinations for Indians: "
            "Maldives: Visa on arrival (30 days, free). "
            "Thailand: Visa on arrival USD 35 or e-Visa. "
            "Bali/Indonesia: Visa on arrival USD 35. "
            "Sri Lanka: e-Visa USD 20. "
            "Dubai: Visa required, apply online (USD 90–150). "
            "Schengen (France/Italy/Germany): Apply at embassy, 15+ days processing. "
            "USA: B1/B2 tourist visa, apply 3–6 months ahead."
        ),
        "metadata": {
            "destination": "International",
            "category": "visa_info",
            "location": "Global",
        },
    },
    {
        "content": (
            "Top Adventure Activities in India: "
            "Trekking: Kedarkantha (Uttarakhand), Triund (HP), Valley of Flowers (UK). "
            "White-water rafting: Rishikesh (Grade 3–4), Spiti River. "
            "Paragliding: Billing-Bir (HP) – world class; Kamshet (Pune). "
            "Skiing: Auli (UK), Solang Valley (HP). "
            "Scuba Diving: Andaman Islands, Lakshadweep. "
            "Bungee Jumping: Rishikesh (83m, highest in India), Goa. "
            "Wildlife Safari: Jim Corbett, Ranthambore, Kanha, Bandhavgarh."
        ),
        "metadata": {
            "destination": "India",
            "category": "adventure_activities",
            "location": "India",
            "price_range": "budget_to_medium",
        },
    },
]


def get_embeddings() -> OpenAIEmbeddings:
    """Return configured OpenAI embeddings model."""
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=OPENAI_API_KEY,
    )


def build_index(force_rebuild: bool = False) -> LangchainFAISS:
    """
    Build (or load) the FAISS vector index from TRAVEL_DOCUMENTS.

    Args:
        force_rebuild: If True, rebuild even if a saved index exists.

    Returns:
        LangchainFAISS vector store ready for similarity search.
    """
    index_path = Path(FAISS_INDEX_PATH)

    if not force_rebuild and (index_path / "index.faiss").exists():
        logger.info("Loading existing FAISS index from %s", index_path)
        return LangchainFAISS.load_local(
            str(index_path),
            get_embeddings(),
            allow_dangerous_deserialization=True,
        )

    logger.info("Building FAISS index with %d travel documents…", len(TRAVEL_DOCUMENTS))
    documents = [
        Document(page_content=doc["content"], metadata=doc["metadata"])
        for doc in TRAVEL_DOCUMENTS
    ]
    embeddings = get_embeddings()
    vector_store = LangchainFAISS.from_documents(documents, embeddings)
    vector_store.save_local(str(index_path))
    logger.info("FAISS index saved to %s", index_path)
    return vector_store


def load_index() -> LangchainFAISS:
    """Load an existing FAISS index (builds if missing)."""
    return build_index(force_rebuild=False)


def similarity_search(
    query: str,
    k: int = 8,
    filter_metadata: Dict[str, Any] = None,
) -> List[Document]:
    """
    Run a similarity search against the travel knowledge base.

    Args:
        query: User query string.
        k: Number of results to return.
        filter_metadata: Optional metadata filter dict.

    Returns:
        List of Document objects sorted by relevance.
    """
    store = load_index()
    if filter_metadata:
        results = store.similarity_search(query, k=k, filter=filter_metadata)
    else:
        results = store.similarity_search(query, k=k)
    return results


if __name__ == "__main__":
    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Set OPENAI_API_KEY before running this script.")
    else:
        store = build_index(force_rebuild=True)
        results = similarity_search("beach resort in Goa for couple", k=3)
        for i, doc in enumerate(results, 1):
            print(f"\n{'='*60}")
            print(f"Result {i} [{doc.metadata.get('category')}]")
            print(doc.page_content[:200])
