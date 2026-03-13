#!/usr/bin/env python3
"""Batch fetch all cities and verticals. Run from project root."""
import subprocess
import sys
import time
from pathlib import Path

# All cities to fetch, grouped by tier
CITIES = [
    # Tier 1 - Maximum potential
    "New York, NY",
    "Los Angeles, CA",
    "San Francisco, CA",
    "San Jose, CA",
    "Washington, DC",
    # Tier 2 - High potential
    "Boston, MA",
    "Seattle, WA",
    "Chicago, IL",
    "Dallas, TX",
    "Houston, TX",
    # Tier 3 - Good potential
    "Austin, TX",
    "Denver, CO",
    "San Diego, CA",
    "Orlando, FL",
    "Tampa, FL",
]

VERTICALS = ["dentists", "restaurants", "gyms", "attorneys", "therapists"]

# Larger cities need larger radius
CITY_RADIUS = {
    "New York, NY": 20000,       # NYC is dense, 20km covers a lot
    "Los Angeles, CA": 35000,    # LA is sprawling
    "Chicago, IL": 25000,
    "Houston, TX": 35000,        # Houston is huge
    "Dallas, TX": 30000,
}
DEFAULT_RADIUS = 30000


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Batch fetch all cities')
    parser.add_argument('--tier', type=int, help='Only fetch specific tier (1, 2, or 3)')
    parser.add_argument('--vertical', help='Only fetch specific vertical')
    parser.add_argument('--city', help='Only fetch specific city')
    parser.add_argument('--dry-run', action='store_true', help='Just show what would be fetched')
    args = parser.parse_args()

    cities = CITIES
    if args.tier:
        tier_slices = {1: (0, 5), 2: (5, 10), 3: (10, 15)}
        start, end = tier_slices.get(args.tier, (0, 15))
        cities = CITIES[start:end]
    if args.city:
        cities = [c for c in CITIES if args.city.lower() in c.lower()]

    verticals = VERTICALS
    if args.vertical:
        verticals = [args.vertical]

    total_jobs = len(cities) * len(verticals)
    print(f"\n🚀 Batch fetch: {len(cities)} cities × {len(verticals)} verticals = {total_jobs} jobs\n")

    for city in cities:
        print(f"  📍 {city}")
    print()

    if args.dry_run:
        print("🔍 Dry run — not fetching")
        return

    completed = 0
    failed = 0
    results = []

    for city in cities:
        radius = CITY_RADIUS.get(city, DEFAULT_RADIUS)
        for vertical in verticals:
            completed += 1
            print(f"\n[{completed}/{total_jobs}] 🔍 {vertical} in {city} (radius={radius}m)")

            try:
                result = subprocess.run(
                    [
                        sys.executable, "pipeline/fetch_places.py",
                        "--vertical", vertical,
                        "--city", city,
                        "--radius", str(radius),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 min timeout per job
                )
                if result.returncode == 0:
                    # Extract total from output
                    for line in result.stdout.split('\n'):
                        if 'Total businesses found' in line:
                            print(f"  ✅ {line.strip()}")
                            break
                    results.append((city, vertical, "OK"))
                else:
                    print(f"  ❌ Error: {result.stderr[:200]}")
                    failed += 1
                    results.append((city, vertical, "FAILED"))
            except subprocess.TimeoutExpired:
                print(f"  ⏰ Timeout!")
                failed += 1
                results.append((city, vertical, "TIMEOUT"))
            except Exception as e:
                print(f"  ❌ {e}")
                failed += 1
                results.append((city, vertical, str(e)))

            # Small delay between requests to be nice to the API
            time.sleep(1)

    print(f"\n{'='*60}")
    print(f"🎉 Done! {completed - failed}/{completed} successful, {failed} failed")
    print(f"{'='*60}\n")

    # Summary
    if failed:
        print("Failed jobs:")
        for city, vertical, status in results:
            if status not in ("OK",):
                print(f"  ❌ {vertical} in {city}: {status}")


if __name__ == '__main__':
    main()
