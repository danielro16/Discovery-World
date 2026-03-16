"""
fetch_all_cities.py (V2) — Batch fetch across all cities and verticals.

Usage:
    python pipeline_v2/fetch_all_cities.py
    python pipeline_v2/fetch_all_cities.py --vertical dentists
    python pipeline_v2/fetch_all_cities.py --city "Miami, FL"
    python pipeline_v2/fetch_all_cities.py --tier 1
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.table import Table

from config import list_verticals
from fetch_places import fetch_vertical

console = Console()

# City tiers — same as V1
CITY_TIERS = {
    1: [
        ("New York, NY", 25000),
        ("Los Angeles, CA", 35000),
        ("San Francisco, CA", 20000),
        ("San Jose, CA", 25000),
        ("Washington, DC", 20000),
    ],
    2: [
        ("Boston, MA", 20000),
        ("Seattle, WA", 25000),
        ("Chicago, IL", 30000),
        ("Dallas, TX", 30000),
        ("Houston, TX", 35000),
    ],
    3: [
        ("Austin, TX", 25000),
        ("Denver, CO", 25000),
        ("San Diego, CA", 30000),
        ("Orlando, FL", 25000),
        ("Tampa, FL", 25000),
        ("Miami, FL", 25000),
        ("Miami Beach, FL", 15000),
    ],
}


def main():
    parser = argparse.ArgumentParser(description="V2: Batch fetch all cities/verticals")
    parser.add_argument("--vertical", help="Only fetch this vertical")
    parser.add_argument("--city", help="Only fetch this city")
    parser.add_argument("--tier", type=int, help="Only fetch this tier (1, 2, or 3)")
    parser.add_argument(
        "--sources",
        default="osm,public_records",
        help="Comma-separated sources (default: osm,public_records)",
    )

    args = parser.parse_args()
    source_list = [s.strip() for s in args.sources.split(",")]

    # Build city list
    cities = []
    if args.city:
        cities = [(args.city, 30000)]
    else:
        tiers = [args.tier] if args.tier else [1, 2, 3]
        for tier in tiers:
            cities.extend(CITY_TIERS.get(tier, []))

    # Build vertical list
    verticals = [args.vertical] if args.vertical else list_verticals()

    total_jobs = len(cities) * len(verticals)
    console.print(f"\n[bold cyan]🚀 V2 Batch Fetch[/bold cyan]")
    console.print(f"   Cities: {len(cities)}")
    console.print(f"   Verticals: {len(verticals)}")
    console.print(f"   Total jobs: {total_jobs}")
    console.print(f"   Sources: {', '.join(source_list)}\n")

    results = []
    completed = 0

    for city, radius in cities:
        for vertical in verticals:
            completed += 1
            console.print(f"\n[bold]━━━ [{completed}/{total_jobs}] {vertical} in {city} ━━━[/bold]")

            try:
                fetch_vertical(vertical, city, radius, source_list)
                results.append({"city": city, "vertical": vertical, "status": "✅"})
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                results.append({"city": city, "vertical": vertical, "status": f"❌ {e}"})

            # Rate limit between jobs
            time.sleep(3)

    # Summary table
    console.print(f"\n\n[bold cyan]📊 Batch Results[/bold cyan]\n")
    table = Table()
    table.add_column("City")
    table.add_column("Vertical")
    table.add_column("Status")

    for r in results:
        table.add_row(r["city"], r["vertical"], r["status"])

    console.print(table)


if __name__ == "__main__":
    main()
