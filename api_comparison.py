#!/usr/bin/env python
"""
API comparison script — verifies that the local and live APIs return
the same shape of data for the endpoints consumed by NPDA.

Usage:
    # Against local API (no API key needed):
    python api_comparison.py --local

    # Against live API (requires API key):
    python api_comparison.py --live --api-key YOUR_KEY

    # Compare both:
    python api_comparison.py --compare --api-key YOUR_KEY

The script checks:
  1. /paediatric_diabetes_units/parent/ — all PDUs with their trust/LHB parent
  2. /organisations/{ods_code}/ — individual organisation detail
  3. /local_authority_districts/within_radius/ — LADs within radius
  4. /trusts/ — all trusts
  5. /integrated_care_boards/ — all ICBs
  6. /local_health_boards/ — all LHBs
  7. /nhs_england_regions/ — all NHS England regions

For each endpoint, it checks:
  - HTTP status code is 200
  - Response is valid JSON
  - The shape of the response (keys present, types) matches between local and live
  - The count of items matches (for list endpoints)

It does NOT compare exact values (names, addresses) — only shape and count.
This is because the local database may have been backfilled with additional
historical rows that the live database doesn't have yet.
"""

import argparse
import json
import sys
import requests


def fetch(url, api_key=None, params=None):
    """Fetch JSON from a URL, optionally with an API key."""
    headers = {}
    if api_key:
        headers["Ocp-Apim-Subscription-Key"] = api_key
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json(), response.status_code
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}, getattr(e.response, "status_code", 0)


def get_shape(obj, depth=0, max_depth=3):
    """Return the 'shape' of a JSON object — keys and types, not values."""
    if depth > max_depth:
        return "..."
    if isinstance(obj, dict):
        return {k: get_shape(v, depth + 1, max_depth) for k, v in list(obj.items())[:20]}
    if isinstance(obj, list):
        if not obj:
            return ["empty"]
        return [get_shape(obj[0], depth + 1, max_depth)]
    return type(obj).__name__


def check_endpoint(base_url, endpoint, api_key=None, params=None, label=""):
    """Check a single endpoint and return a summary."""
    url = f"{base_url}{endpoint}"
    data, status = fetch(url, api_key, params)
    ok = status == 200 and isinstance(data, (dict, list))
    count = len(data) if isinstance(data, list) else len(data.get("results", [data])) if isinstance(data, dict) else 0
    shape = get_shape(data)
    print(f"  [{'✓' if ok else '✗'}] {label or endpoint} — status={status}, count={count}")
    if not ok:
        print(f"      Error: {data}")
    return {"endpoint": endpoint, "status": status, "count": count, "shape": shape, "ok": ok}


def run_checks(base_url, api_key=None):
    """Run all endpoint checks against a base URL."""
    results = []
    print(f"\nChecking {base_url}")
    print("=" * 60)

    # 1. PDU parent endpoint (the one NPDA calls)
    results.append(check_endpoint(
        base_url, "/paediatric_diabetes_units/parent/",
        api_key, label="PDU parent (list)"
    ))

    # 2. Individual organisation
    results.append(check_endpoint(
        base_url, "/organisations/RM102/",
        api_key, label="Organisation detail (RM102)"
    ))

    # 3. LAD within radius
    results.append(check_endpoint(
        base_url, "/local_authority_districts/within_radius/",
        api_key, params={"long": -2.0, "lat": 53.0, "radius": 50000},
        label="LAD within radius"
    ))

    # 4. Trusts
    results.append(check_endpoint(
        base_url, "/trusts/",
        api_key, label="Trusts (list)"
    ))

    # 5. ICBs
    results.append(check_endpoint(
        base_url, "/integrated_care_boards/",
        api_key, label="ICBs (list)"
    ))

    # 6. LHBs
    results.append(check_endpoint(
        base_url, "/local_health_boards/",
        api_key, label="LHBs (list)"
    ))

    # 7. NHS England regions
    results.append(check_endpoint(
        base_url, "/nhs_england_regions/",
        api_key, label="NHS England regions (list)"
    ))

    # 8. PDU parent for a specific PZ code
    results.append(check_endpoint(
        base_url, "/paediatric_diabetes_units/PZ002/parent/",
        api_key, label="PDU parent (PZ002)"
    ))

    return results


def compare_results(local_results, live_results):
    """Compare local and live results."""
    print("\n" + "=" * 60)
    print("COMPARISON: local vs live")
    print("=" * 60)
    all_match = True
    for local, live in zip(local_results, live_results):
        label = local["endpoint"]
        shape_match = local["shape"] == live["shape"]
        # Count may differ if local has been backfilled with more rows.
        # Flag it but don't fail.
        count_match = local["count"] == live["count"]
        status_match = local["status"] == live["status"]

        if shape_match and status_match:
            symbol = "✓"
        else:
            symbol = "✗"
            all_match = False

        print(f"  [{symbol}] {label}")
        print(f"      status: local={local['status']} live={live['status']}")
        print(f"      count:  local={local['count']} live={live['count']}")
        print(f"      shape:  {'match' if shape_match else 'MISMATCH'}")
        if not shape_match:
            print(f"      local shape: {json.dumps(local['shape'], indent=6)[:200]}")
            print(f"      live shape:  {json.dumps(live['shape'], indent=6)[:200]}")

    return all_match


def main():
    parser = argparse.ArgumentParser(description="Compare local and live API responses")
    parser.add_argument("--local", action="store_true", help="Check local API (port 8003)")
    parser.add_argument("--live", action="store_true", help="Check live API")
    parser.add_argument("--compare", action="store_true", help="Compare local vs live")
    parser.add_argument("--api-key", type=str, default=None, help="API key for live API")
    parser.add_argument("--local-url", type=str, default="http://localhost:8003", help="Local API URL")
    parser.add_argument("--live-url", type=str, default=None, help="Live API URL (must be set for --live or --compare)")
    args = parser.parse_args()

    if args.compare or args.live:
        if not args.live_url:
            print("ERROR: --live-url is required for --live or --compare")
            sys.exit(1)
        if not args.api_key:
            print("ERROR: --api-key is required for --live or --compare")
            sys.exit(1)

    if args.compare:
        local_results = run_checks(args.local_url)
        live_results = run_checks(args.live_url, args.api_key)
        all_match = compare_results(local_results, live_results)
        sys.exit(0 if all_match else 1)
    elif args.local:
        run_checks(args.local_url)
    elif args.live:
        run_checks(args.live_url, args.api_key)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
