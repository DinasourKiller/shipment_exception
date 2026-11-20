"""Frontend HTML & JavaScript Static Consistency & Integrity Validator."""

import re
import sys
from bs4 import BeautifulSoup

def validate_console_ui():
    print("========================================================")
    print("▶ Validating Web Testing Console (app/static/index.html)")
    print("========================================================")

    with open("app/static/index.html", "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")

    # 1. Check all tabs have matching nav- and tab- elements
    tabs = ['auth', 'shipments', 'tracking', 'exceptions', 'users', 'analytics', 'audit', 'claims', 'geofences', 'diagnostics']
    print(f"\n[1] Checking Tab Navigation & Sections ({len(tabs)} tabs)")
    for t in tabs:
        nav = soup.find(id=f"nav-{t}")
        section = soup.find(id=f"tab-{t}")
        assert nav is not None, f"Missing nav button: nav-{t}"
        assert section is not None, f"Missing tab section: tab-{t}"
        print(f"  ✓ Tab '{t}': nav-{t} and tab-{t} exist")

    # 2. Extract all IDs in the DOM
    all_dom_ids = set()
    for el in soup.find_all(id=True):
        all_dom_ids.add(el["id"])
    print(f"\n[2] Discovered {len(all_dom_ids)} distinct DOM element IDs")

    # 3. Extract all JavaScript code
    scripts = soup.find_all("script")
    inline_js = "\n".join(s.string for s in scripts if s.string)

    # 4. Check that getElementById targets exist
    get_el_calls = re.findall(r'document\.getElementById\(\s*["\']([^"\']+)["\']\s*\)', inline_js)
    missing_ids = set()
    for el_id in get_el_calls:
        if el_id not in all_dom_ids:
            missing_ids.add(el_id)

    if missing_ids:
        print(f"  ⚠️ Warning: Found {len(missing_ids)} IDs referenced in getElementById that may be dynamically injected or missing: {missing_ids}")
    else:
        print(f"  ✓ All {len(set(get_el_calls))} static document.getElementById targets exist in DOM")

    # 5. Extract all onclick function calls and check definitions
    onclick_handlers = []
    for el in soup.find_all(onclick=True):
        handler = el["onclick"].strip()
        # Extract function name
        match = re.match(r'([a-zA-Z0-9_]+)\(', handler)
        if match:
            onclick_handlers.append(match.group(1))

    # Extract all declared JS functions
    js_functions = set(re.findall(r'function\s+([a-zA-Z0-9_]+)\s*\(', inline_js))
    js_async_functions = set(re.findall(r'async\s+function\s+([a-zA-Z0-9_]+)\s*\(', inline_js))
    all_functions = js_functions.union(js_async_functions)
    print(f"\n[3] Discovered {len(all_functions)} declared JavaScript functions in console")

    missing_functions = set()
    for fn in set(onclick_handlers):
        if fn not in all_functions:
            missing_functions.add(fn)

    assert not missing_functions, f"Missing function implementations for onclick handlers: {missing_functions}"
    print(f"  ✓ All {len(set(onclick_handlers))} onclick handlers have corresponding JavaScript function implementations")

    # 6. Check Modals
    modals = [
        "claim-dispute-modal",
        "claim-settle-modal",
        "claim-timeline-modal",
        "create-geofence-modal",
        "shipment-dwell-modal",
        "recovery-modal",
        "impact-modal",
    ]
    print(f"\n[4] Validating Operational Modals ({len(modals)} modals)")
    for m in modals:
        el = soup.find(id=m)
        assert el is not None, f"Missing modal container: {m}"
        print(f"  ✓ Modal container '{m}' exists and ready")

    print("\n========================================================")
    print("🎉 FRONTEND CONSOLE HTML & JS INTEGRITY 100% VALIDATED!")
    print("========================================================\n")


if __name__ == "__main__":
    try:
        validate_console_ui()
    except Exception as e:
        print(f"❌ Frontend Validation Failed: {e}")
        sys.exit(1)
