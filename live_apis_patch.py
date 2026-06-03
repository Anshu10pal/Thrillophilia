"""
Run from C:\Projects\Thrillophilia\
  py live_apis_patch.py

Fixes:
1. Xotelo crash — NoneType has no attribute 'get'
2. Geoapify 400 — category list too long
3. Stream.py SSE timeout increase
"""
import sys, re

# ── Fix 1 + 2: live_apis.py ───────────────────────────────────────────────────
path = 'tools/live_apis.py'
try:
    src = open(path, encoding='utf-8').read()
except FileNotFoundError:
    print(f"ERROR: {path} not found — run from C:\\Projects\\Thrillophilia\\")
    sys.exit(1)

orig = src

# Fix Geoapify categories — shorten the category string
# Find and replace the long category string
src = re.sub(
    r'categories=[\'"](catering\.cafe[^\'\"]{50,})[\'"]',
    'categories="tourism.attraction,tourism.sights,catering.restaurant,natural,entertainment,leisure"',
    src
)

# Fix Xotelo — wrap result.get() calls safely
if "'NoneType' object has no attribute 'get'" or "result.get(" in src:
    # Find the Xotelo section and add None checks
    # Pattern: any place where we do xotelo_result.get or result.get after xotelo call
    src = re.sub(
        r'(location_result|search_result|result)\s*=\s*(.*?\.json\(\))',
        r'\1 = \2\n    if not \1 or not isinstance(\1, dict): return []',
        src
    )
    # More targeted: wrap the specific call that crashes
    src = src.replace(
        "result.get(\"result\", {}).get(",
        "(result or {}).get(\"result\", {}).get("
    )
    src = src.replace(
        'if not result or "result" not in result:',
        'if not result or not isinstance(result, dict) or "result" not in result:'
    )

print("Geoapify categories shortened:", 'tourism.attraction,tourism.sights' in src and 'catering.cafe%2Ccatering.fast_food' not in src)
print("Xotelo None guard:", '(result or {})' in src or 'isinstance(result, dict)' in src)

if src != orig:
    open(path, 'w', encoding='utf-8').write(src)
    print(f"✅ {path} patched")
else:
    print(f"⚠  {path} — no changes matched, may need manual fix")
    print("   Manual fix: Find 'result.get' after Xotelo API call and add 'if not result: return []' guard")

# ── Fix 3: stream.py — increase SSE timeout ───────────────────────────────────
stream_path = 'backend/routers/stream.py'
try:
    stream_src = open(stream_path, encoding='utf-8').read()
    stream_src = stream_src.replace('max_wait    = 180', 'max_wait    = 600')
    stream_src = stream_src.replace('max_wait    = 300', 'max_wait    = 600')
    stream_src = stream_src.replace('max_wait = 180',    'max_wait = 600')
    stream_src = stream_src.replace('max_wait = 300',    'max_wait = 600')
    open(stream_path, 'w', encoding='utf-8').write(stream_src)
    print("✅ stream.py SSE timeout → 600s (10 min)")
except FileNotFoundError:
    print(f"⚠  {stream_path} not found")

print("\nDone.")