"""
fetch_places.py (V2) — Multi-source business data fetcher.

Replaces Google Places API with TOS-compliant sources:
  1. OpenStreetMap (ODbL) — base business data
  2. Public Records — professional license verification
  3. Website scraping — enrichment from business's own site

Usage:
    python pipeline_v2/fetch_places.py --vertical dentists --city "Miami, FL"
    python pipeline_v2/fetch_places.py --vertical restaurants --city "Miami, FL" --radius 20000
    python pipeline_v2/fetch_places.py --vertical dentists --city "Miami, FL" --sources osm,public_records
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console

from config import load_vertical, get_data_path, slugify
from sources import osm, public_records
from merge_sources import merge_places, calculate_completeness

console = Console()


def fetch_vertical(vertical_name: str, city: str, radius: int, sources: list[str] | None = None):
    """
    Fetch all businesses for a vertical in a city from multiple sources.

    Sources are fetched independently, then merged by name/address matching.
    Each source's raw data is saved separately for traceability + ODbL compliance.
    """
    vertical = load_vertical(vertical_name)
    data_path = get_data_path(vertical_name, city)

    if sources is None:
        sources = ["osm", "public_records"]

    console.print(f"\n[bold cyan]🔍 V2 Fetch: {vertical['display_name']} in {city}[/bold cyan]")
    console.print(f"   Sources: {', '.join(sources)}")
    console.print(f"   Radius: {radius}m")
    console.print(f"   Saving to: {data_path}\n")

    # --- Fetch from each source ---
    osm_places = []
    pr_places = []

    if "osm" in sources:
        console.print("[bold]📍 Source 1: OpenStreetMap[/bold]")
        osm_places = osm.fetch_places(vertical_name, city, radius)

        # Save raw OSM data (separate file for ODbL compliance)
        osm_file = data_path / "osm.json"
        with open(osm_file, "w") as f:
            json.dump(osm_places, f, indent=2, ensure_ascii=False)
        console.print(f"   Saved {len(osm_places)} OSM records → {osm_file.name}\n")

    if "public_records" in sources:
        console.print("[bold]📋 Source 2: Public Records[/bold]")
        pr_places = public_records.fetch_places(vertical_name, city, radius)

        if pr_places:
            pr_file = data_path / "public_records.json"
            with open(pr_file, "w") as f:
                json.dump(pr_places, f, indent=2, ensure_ascii=False)
            console.print(f"   Saved {len(pr_places)} license records → {pr_file.name}\n")

    # --- Merge sources ---
    console.print("[bold]🔗 Merging sources...[/bold]")
    merged = merge_places(osm_places, pr_places)

    # Calculate completeness scores
    for place in merged:
        place["profile_completeness"] = calculate_completeness(place)

    # Sort by completeness (most complete first)
    merged.sort(key=lambda x: x["profile_completeness"], reverse=True)

    # --- Save merged results ---
    places_file = data_path / "places.json"
    with open(places_file, "w") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    # Save stats
    stats = {
        "vertical": vertical_name,
        "city": city,
        "total_places": len(merged),
        "sources": {
            "osm": len(osm_places),
            "public_records": len(pr_places),
        },
        "with_website": len([p for p in merged if p.get("website")]),
        "with_phone": len([p for p in merged if p.get("phone")]),
        "with_address": len([p for p in merged if p.get("address")]),
        "with_license": len([p for p in merged if p.get("license_info")]),
        "avg_completeness": round(
            sum(p["profile_completeness"] for p in merged) / max(len(merged), 1), 1
        ),
        "attribution": [
            "© OpenStreetMap contributors (ODbL 1.0) — https://www.openstreetmap.org/copyright",
        ],
    }

    stats_file = data_path / "stats.json"
    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=2)

    # --- Summary ---
    console.print(f"\n[bold green]✅ Done![/bold green]")
    console.print(f"   Total businesses: [bold]{len(merged)}[/bold]")
    console.print(f"   From OSM: {len(osm_places)}")
    console.print(f"   From Public Records: {len(pr_places)}")
    console.print(f"   With website: {stats['with_website']}")
    console.print(f"   With phone: {stats['with_phone']}")
    console.print(f"   With address: {stats['with_address']}")
    console.print(f"   Avg completeness: {stats['avg_completeness']}%")
    console.print(f"   Saved to: {places_file}")


def main():
    parser = argparse.ArgumentParser(
        description="V2: Fetch businesses from TOS-compliant sources (OSM + Public Records)"
    )
    parser.add_argument("--vertical", required=True, help="Vertical name (e.g., dentists)")
    parser.add_argument("--city", required=True, help="City name (e.g., 'Miami, FL')")
    parser.add_argument("--radius", type=int, default=30000, help="Search radius in meters (default: 30000)")
    parser.add_argument(
        "--sources",
        default="osm,public_records",
        help="Comma-separated list of sources (default: osm,public_records)",
    )

    args = parser.parse_args()
    source_list = [s.strip() for s in args.sources.split(",")]
    fetch_vertical(args.vertical, args.city, args.radius, source_list)


if __name__ == "__main__":
    main()
