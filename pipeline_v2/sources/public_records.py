"""
Public Records Source — Fetches professional license data from government registries.

License: Public domain / public record
- Commercial use: ✅ (government data is public record)
- Caching/storage: ✅
- Attribution: not legally required, but good practice
- Method: FOIA requests preferred over scraping (cleaner legally)

Best for: dentists, attorneys, therapists (regulated professions)
NOT useful for: restaurants, gyms (not regulated the same way)

Data available: name, license number, status, specialties, disciplinary actions
Data NOT available: phone, website, hours, ratings, reviews, photos
"""

from __future__ import annotations

import csv
import io
import time
import requests
from rich.console import Console

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    PUBLIC_RECORDS_SOURCES,
    CITY_TO_STATE,
    slugify,
)

console = Console()

# Verticals that have regulated professions with public license data
REGULATED_VERTICALS = {"dentists", "attorneys", "therapists"}


def fetch_places(vertical: str, city: str, radius: int = 30000) -> list[dict]:
    """
    Fetch professional license data for a vertical in a city.

    Returns list of places in our standard schema (partial — only license fields).
    These records should be merged with OSM data to create complete listings.

    Returns empty list for non-regulated verticals (restaurants, gyms).
    """
    if vertical not in REGULATED_VERTICALS:
        console.print(f"[dim]  PUBLIC_RECORDS: Skipping {vertical} (not a regulated profession)[/dim]")
        return []

    city_lower = city.lower().strip()
    state = CITY_TO_STATE.get(city_lower)

    if not state:
        console.print(f"[yellow]  PUBLIC_RECORDS: Unknown state for '{city}'[/yellow]")
        return []

    sources = PUBLIC_RECORDS_SOURCES.get(state, {})
    source = sources.get(vertical)

    if not source:
        console.print(f"[yellow]  PUBLIC_RECORDS: No source configured for {vertical} in {state}[/yellow]")
        return []

    console.print(f"[cyan]  PUBLIC_RECORDS: Fetching {vertical} licenses in {state}[/cyan]")
    console.print(f"[dim]  Source: {source['url']}[/dim]")
    console.print(f"[dim]  Type: {source['type']}[/dim]")

    if source["type"] == "csv_download":
        return _fetch_csv_source(source, vertical, city, state)
    elif source["type"] == "api_search":
        console.print(f"[yellow]  PUBLIC_RECORDS: API search not yet implemented for {state} {vertical}[/yellow]")
        console.print(f"[dim]  TODO: Implement {source['url']}[/dim]")
        return []
    elif source["type"] == "web_search":
        console.print(f"[yellow]  PUBLIC_RECORDS: Web search not yet implemented for {state} {vertical}[/yellow]")
        console.print(f"[dim]  Consider FOIA request to: {source['url']}[/dim]")
        return []
    else:
        console.print(f"[red]  PUBLIC_RECORDS: Unknown source type: {source['type']}[/red]")
        return []


def _fetch_csv_source(source: dict, vertical: str, city: str, state: str) -> list[dict]:
    """Fetch from a CSV download source (e.g., Texas BHEC)."""
    csv_urls = source.get("csv_urls", {})
    if not csv_urls:
        return []

    all_records = []

    for license_type, url in csv_urls.items():
        console.print(f"[dim]  Downloading {license_type} CSV...[/dim]")

        try:
            response = requests.get(
                url,
                timeout=60,
                headers={"User-Agent": "AgentReady-Directory/2.0"},
            )

            if response.status_code != 200:
                console.print(f"[red]  Failed to download {license_type}: {response.status_code}[/red]")
                continue

            # Parse CSV
            content = response.text
            reader = csv.DictReader(io.StringIO(content))

            count = 0
            for row in reader:
                parsed = _parse_license_record(row, license_type, state)
                if parsed:
                    all_records.append(parsed)
                    count += 1

            console.print(f"[cyan]  {license_type}: {count} active licenses[/cyan]")
            time.sleep(1)  # be polite

        except Exception as e:
            console.print(f"[red]  Error fetching {license_type}: {e}[/red]")

    console.print(f"[green]  PUBLIC_RECORDS: {len(all_records)} total license records[/green]")
    return all_records


def _parse_license_record(row: dict, license_type: str, state: str) -> dict | None:
    """
    Parse a license CSV row into our standard place schema.

    Note: Public records typically lack address, phone, website.
    These fields will be filled by merging with OSM data or website scraping.
    """
    # Field names vary by state — this handles Texas BHEC format
    name_fields = ["Name", "name", "Licensee Name", "LICENSEE_NAME", "Full Name"]
    name = None
    for field in name_fields:
        if field in row and row[field]:
            name = row[field].strip()
            break

    if not name:
        return None

    # Check license status — only include active
    status_fields = ["License Status", "Status", "LICENSE_STATUS", "status"]
    status = ""
    for field in status_fields:
        if field in row and row[field]:
            status = row[field].strip().upper()
            break

    if status and status not in ("ACTIVE", "CURRENT", "CLEAR", ""):
        return None

    # Extract license number
    license_fields = ["License Number", "License No", "LICENSE_NUMBER", "license_number"]
    license_number = ""
    for field in license_fields:
        if field in row and row[field]:
            license_number = row[field].strip()
            break

    record_id = f"pr_{state.lower()}_{license_type.lower()}_{license_number or slugify(name)}"

    return {
        "id": record_id,
        "name": name,
        "address": "",  # often not in CSV downloads
        "location": {"lat": None, "lng": None},
        "phone": "",
        "website": "",
        "google_maps_url": "",
        "osm_url": "",
        "rating": None,
        "review_count": 0,
        "business_status": "OPERATIONAL",
        "price_level": "",
        "types": [license_type.lower()],
        "hours": {},
        "reviews": [],
        "photos": [],
        "enriched": False,
        "enriched_data": {},
        "profile_completeness": 0,
        "claimed": False,
        # V2 metadata
        "source": "public_records",
        "source_license": "public_domain",
        "license_info": {
            "state": state,
            "type": license_type,
            "number": license_number,
            "status": status or "ACTIVE",
            "raw_record": {k: v for k, v in row.items() if v},  # preserve non-empty fields
        },
    }
