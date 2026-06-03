"""
Run from C:\Projects\Thrillophilia\
  py fix_pdf_generator.py

Fixes: 'NoneType' object has no attribute 'title'
in tools/pdf_generator.py
"""
import sys, re

path = 'tools/pdf_generator.py'
try:
    src = open(path, encoding='utf-8').read()
except FileNotFoundError:
    print(f"ERROR: {path} not found")
    sys.exit(1)

orig = src
changes = 0

# Fix 1: travel_type.title() crash
patterns = [
    # pattern, replacement
    (r'travel_type\.title\(\)', '(travel_type or "General").title()'),
    (r'"travel_type"\]\.title\(\)', '"travel_type"] or "General").title()'),
    # Fix None for travelers
    (r'\bnum_days\b(?!\s*or)', 'num_days or 5'),
    (r'\btravelers\b(?!\s*or)', 'travelers or 2'),
    (r'\bnum_travelers\b(?!\s*or)', 'num_travelers or 2'),
]

# Simpler targeted fix
if 'travel_type.title()' in src:
    src = src.replace('travel_type.title()', '(travel_type or "General").title()')
    changes += 1
    print("✓ Fixed travel_type.title()")

# Check for prefs.get("travel_type") without fallback
src = re.sub(
    r'prefs\.get\(["\']travel_type["\']\)(?!\s*or\s)',
    'prefs.get("travel_type") or "general"',
    src
)

# Check for state.get("trip_preferences", {}).get("travel_type") 
src = re.sub(
    r'\.get\(["\']travel_type["\']\)(?!\s*or\s)',
    '.get("travel_type") or "general"',
    src
)

if src != orig:
    open(path, 'w', encoding='utf-8').write(src)
    print(f"✅ pdf_generator.py patched")
else:
    print("ℹ No changes — travel_type already handled or different structure")
    print("Manual fix needed — open tools/pdf_generator.py and find:")
    print("  travel_type.title()")
    print("Replace with:")
    print("  (travel_type or 'General').title()")

import ast
try:
    ast.parse(src)
    print("✅ Syntax check passed")
except SyntaxError as e:
    print(f"❌ SYNTAX ERROR at line {e.lineno}: {e.msg}")