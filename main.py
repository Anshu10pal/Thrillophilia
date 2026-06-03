"""
main.py — Trip Planner Entry Point & Demo
==========================================
Run this script to launch the interactive trip planner CLI
or execute the built-in demo conversation.

Usage:
    python main.py                 # Interactive CLI mode
    python main.py --demo          # Run built-in demo
    python main.py --build-index   # Rebuild FAISS knowledge base
"""

import sys
import argparse
import logging
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

from config import validate_config, logger, OPENAI_API_KEY


# ─────────────────────────────────────────────────────────────────────────────
# DEMO CONVERSATION
# ─────────────────────────────────────────────────────────────────────────────

def run_demo():
    """
    Demonstrate the full multi-agent pipeline with a Goa trip query.
    Covers: initial plan → budget feedback → refinement → PDF output.
    """
    print("\n" + "=" * 70)
    print("  🌍 AI TRIP PLANNER — Multi-Agent LangGraph Demo")
    print("=" * 70)

    from workflow import TripPlanner

    planner = TripPlanner()

    # ── Turn 1: Initial trip planning request ─────────────────────────────────
    query1 = (
        "Plan a 5-day Goa trip from Bangalore for a couple. "
        "Budget: ₹30,000. We want a beach resort, nightlife, sightseeing, "
        "and seafood. Prefer flight travel."
    )

    print(f"\n👤 USER: {query1}\n")
    print("⏳ Planning your trip (this may take 20–60 seconds)...\n")

    result1 = planner.plan(query1)

    print("\n" + "─" * 70)
    print("🤖 ASSISTANT:\n")
    print(result1.get("final_response", "No response generated."))

    if result1.get("pdf_path"):
        print(f"\n📄 PDF Report: {result1['pdf_path']}")

    # ── Show state summary ────────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("📊 AGENT STATE SUMMARY:")
    print(f"  Orchestrator iterations: {result1.get('iteration', 0)}")
    print(f"  Review status: {result1.get('review_status', {}).get('status', 'N/A')}")
    conflicts = result1.get("review_status", {}).get("conflicts", [])
    if conflicts:
        print(f"  Conflicts resolved: {conflicts}")
    print(f"  Budget status: {result1.get('budget_summary', {}).get('budget_status', 'N/A')}")
    print(f"  Days planned: {len(result1.get('itinerary', {}).get('days', []))}")
    errors = result1.get("errors", [])
    if errors:
        print(f"  Errors: {errors}")

    # ── Turn 2: Refinement request ────────────────────────────────────────────
    print("\n" + "=" * 70)
    query2 = (
        "The hotel is over budget. Can you find a cheaper option under ₹3,000/night? "
        "Also add a sunrise beach walk to the itinerary."
    )
    print(f"\n👤 USER: {query2}\n")
    print("⏳ Refining your plan...\n")

    result2 = planner.refine(query2)

    print("\n" + "─" * 70)
    print("🤖 ASSISTANT (Refined):\n")
    # Show just the accommodation and budget sections
    response2 = result2.get("final_response", "")
    if "## 🏨" in response2:
        hotel_section = response2[response2.find("## 🏨"):]
        budget_section = hotel_section[hotel_section.find("## 💰"):] if "## 💰" in hotel_section else ""
        print(hotel_section[:hotel_section.find("## 🎯")] if "## 🎯" in hotel_section else hotel_section[:500])
        if budget_section:
            print(budget_section[:600])
    else:
        print(response2[:800])

    if result2.get("pdf_path"):
        print(f"\n📄 Refined PDF Report: {result2['pdf_path']}")

    print("\n" + "=" * 70)
    print("✅ Demo complete! Check the ./output/ folder for your PDF reports.")
    print("=" * 70 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# INTERACTIVE CLI
# ─────────────────────────────────────────────────────────────────────────────

def run_interactive():
    """Launch an interactive multi-turn trip planning session."""
    print("\n" + "=" * 70)
    print("  🌍 AI TRIP PLANNER — Interactive Mode")
    print("  Type 'quit' or 'exit' to stop")
    print("  Type 'pdf' to generate/re-generate PDF for current plan")
    print("=" * 70 + "\n")

    from workflow import TripPlanner
    planner = TripPlanner()
    is_first_turn = True

    while True:
        try:
            prompt = "👤 You: " if is_first_turn else "👤 Refine: "
            user_input = input(prompt).strip()

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("\n👋 Happy travels!\n")
                break

            print("\n⏳ Processing...\n")

            if is_first_turn:
                result = planner.plan(user_input)
                is_first_turn = False
            else:
                result = planner.refine(user_input)

            response = result.get("final_response", "Sorry, I could not generate a plan.")
            print(f"\n🤖 Assistant:\n{response}\n")

            if result.get("pdf_path"):
                print(f"📄 PDF: {result['pdf_path']}\n")

            print("─" * 70)

        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Happy travels!\n")
            break
        except Exception as e:
            logger.error("Error: %s", e)
            print(f"\n❌ Error: {e}\n")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AI Multi-Agent Trip Planner using LangGraph"
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Run the built-in Goa trip demo"
    )
    parser.add_argument(
        "--build-index", action="store_true",
        help="Rebuild the FAISS travel knowledge base index"
    )
    parser.add_argument(
        "--query", type=str, default=None,
        help="Run a single query non-interactively"
    )
    args = parser.parse_args()

    # Validate API key
    if not OPENAI_API_KEY:
        print("❌ OPENAI_API_KEY not set. Create a .env file from .env.example.")
        sys.exit(1)

    validate_config()

    if args.build_index:
        print("🔨 Building FAISS knowledge base index…")
        from data.knowledge_base import build_index
        build_index(force_rebuild=True)
        print("✅ Index built successfully.")
        return

    if args.demo:
        run_demo()
        return

    if args.query:
        from workflow import TripPlanner
        planner = TripPlanner()
        print(f"\n⏳ Processing: {args.query}\n")
        result = planner.plan(args.query)
        print(result.get("final_response", "No response."))
        if result.get("pdf_path"):
            print(f"\n📄 PDF: {result['pdf_path']}")
        return

    # Default: interactive mode
    run_interactive()


if __name__ == "__main__":
    main()
