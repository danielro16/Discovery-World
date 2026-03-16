"""
OSM Source — Fetches business data from OpenStreetMap via Overpass API.

License: ODbL 1.0 (Open Database License)
- Commercial use: ✅ allowed
- Caching/storage: ✅ allowed (derivative database, must share under ODbL)
- Attribution: required ("© OpenStreetMap contributors, ODbL")
- Production: must self-host Overpass (public instance is dev/test only)

Data available: name, address, phone, website, hours, coordinates, type
Data NOT available: ratings, reviews, photos
"""

from __future__ import annotations

import time
import requests
from rich.console import Console

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import (
    OVERPASS_URL,
    OVERPASS_RATE_LIMIT,
    OSM_TAGS,
    get_city_coords,
    slugify,
)

console = Console()


def build_overpass_query(vertical: str, city: str, radius: int = 30000) -> str:
    """
    Build an Overpass QL query for a vertical in a city.

    Uses 'around' filter with city center coordinates.
    Queries both nodes and ways (some businesses are mapped as building outlines).
    """
    coords = get_city_coords(city)
    lat, lng = coords["lat"], coords["lng"]

    tags = OSM_TAGS.get(vertical, [])
    if not tags:
        raise ValueError(f"No OSM tags defined for vertical '{vertical}'")

    # Build union of all tag queries
    query_parts = []
    for tag_dict in tags:
        for key, value in tag_dict.items():
            query_parts.append(f'  node["{key}"="{value}"](around:{radius},{lat},{lng});')
            query_parts.append(f'  way["{key}"="{value}"](around:{radius},{lat},{lng});')

    union_body = "\n".join(query_parts)

    query = f"""
[out:json][timeout:120];
(
{union_body}
);
out center body;
"""
    return query.strip()


def parse_osm_element(element: dict) -> dict | None:
    """
    Parse an OSM element (node or way) into our standard place schema.

    Returns None if the element lacks a name (not useful for a directory).
    """
    tags = element.get("tags", {})

    name = tags.get("name")
    if not name:
        return None

    # Get coordinates — nodes have lat/lon directly, ways have center
    if element["type"] == "node":
        lat = element.get("lat")
        lng = element.get("lon")
    else:
        center = element.get("center", {})
        lat = center.get("lat")
        lng = center.get("lon")

    if not lat or not lng:
        return None

    # Build address from addr:* tags
    address_parts = []
    house_number = tags.get("addr:housenumber", "")
    street = tags.get("addr:street", "")
    if house_number and street:
        address_parts.append(f"{house_number} {street}")
    elif street:
        address_parts.append(street)

    city = tags.get("addr:city", "")
    state = tags.get("addr:state", "")
    postcode = tags.get("addr:postcode", "")

    if city:
        address_parts.append(city)
    if state:
        address_parts.append(state)
    if postcode:
        address_parts.append(postcode)

    address = ", ".join(address_parts) if address_parts else ""

    # Parse opening hours (OSM format: "Mo-Fr 09:00-17:00; Sa 10:00-14:00")
    hours = parse_osm_hours(tags.get("opening_hours", ""))

    # Build OSM-specific ID
    osm_id = f"osm_{element['type']}_{element['id']}"

    return {
        "id": osm_id,
        "name": name,
        "address": address,
        "location": {"lat": lat, "lng": lng},
        "phone": tags.get("phone", tags.get("contact:phone", "")),
        "website": tags.get("website", tags.get("contact:website", "")),
        "google_maps_url": "",  # N/A — we're not using Google
        "osm_url": f"https://www.openstreetmap.org/{element['type']}/{element['id']}",
        "rating": None,  # OSM doesn't have ratings
        "review_count": 0,
        "business_status": "OPERATIONAL",  # OSM doesn't track this well
        "price_level": "",
        "types": extract_osm_types(tags),
        "hours": hours,
        "reviews": [],  # OSM doesn't have reviews
        "photos": [],  # OSM doesn't have photos
        "enriched": False,
        "enriched_data": {},
        "profile_completeness": 0,
        "claimed": False,
        # V2 metadata
        "source": "osm",
        "source_license": "ODbL 1.0",
        "osm_id": element["id"],
        "osm_type": element["type"],
        "osm_tags": tags,  # preserve raw tags for debugging/enrichment
    }


def parse_osm_hours(hours_str: str) -> dict:
    """
    Parse OSM opening_hours format into our standard hours dict.

    OSM format examples:
        "Mo-Fr 09:00-17:00; Sa 10:00-14:00"
        "Mo-Su 00:00-24:00"
        "Mo-Fr 08:00-12:00,13:00-17:00"

    This is a best-effort parser. OSM hours format is complex and varied.
    For production, consider using the 'opening_hours' Python library.
    """
    if not hours_str:
        return {}

    day_map = {
        "Mo": "Monday", "Tu": "Tuesday", "We": "Wednesday",
        "Th": "Thursday", "Fr": "Friday", "Sa": "Saturday", "Su": "Sunday",
    }
    day_order = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]

    hours = {}

    try:
        # Split by semicolons for different rules
        rules = [r.strip() for r in hours_str.split(";")]

        for rule in rules:
            if not rule:
                continue

            # Try to split into days and time parts
            parts = rule.strip().split(" ", 1)
            if len(parts) == 2:
                days_part, time_part = parts
            elif len(parts) == 1:
                # Might be "24/7" or just a time
                if parts[0] == "24/7":
                    for day_abbr in day_order:
                        hours[day_map[day_abbr]] = "00:00 - 24:00"
                    continue
                else:
                    continue
            else:
                continue

            # Parse day ranges (e.g., "Mo-Fr", "Mo,We,Fr", "Mo-We,Fr")
            expanded_days = []
            day_groups = days_part.split(",")
            for group in day_groups:
                group = group.strip()
                if "-" in group:
                    start_day, end_day = group.split("-", 1)
                    start_day = start_day.strip()
                    end_day = end_day.strip()
                    if start_day in day_order and end_day in day_order:
                        start_idx = day_order.index(start_day)
                        end_idx = day_order.index(end_day)
                        if end_idx >= start_idx:
                            expanded_days.extend(day_order[start_idx:end_idx + 1])
                        else:
                            # Wraps around (e.g., Fr-Mo)
                            expanded_days.extend(day_order[start_idx:])
                            expanded_days.extend(day_order[:end_idx + 1])
                elif group in day_order:
                    expanded_days.append(group)

            # Format time part
            time_display = time_part.replace(",", ", ").strip()

            for day_abbr in expanded_days:
                if day_abbr in day_map:
                    hours[day_map[day_abbr]] = time_display

    except Exception:
        # If parsing fails, store raw string under a special key
        hours["_raw"] = hours_str

    return hours


def extract_osm_types(tags: dict) -> list[str]:
    """Extract business type tags from OSM tags."""
    types = []

    type_keys = ["amenity", "healthcare", "leisure", "office", "shop", "sport",
                 "healthcare:speciality", "cuisine"]

    for key in type_keys:
        if key in tags:
            types.append(tags[key])

    return types


def _run_overpass_query(query: str) -> list[dict]:
    """Execute a single Overpass query and return raw elements."""
    try:
        response = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=180,
            headers={"User-Agent": "AgentReady-Directory/2.0 (contact@agentready.com)"},
        )

        if response.status_code == 429:
            console.print("[yellow]  OSM: Rate limited, waiting 60s...[/yellow]")
            time.sleep(60)
            response = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=180,
                headers={"User-Agent": "AgentReady-Directory/2.0 (contact@agentready.com)"},
            )

        if response.status_code != 200:
            console.print(f"[red]  OSM: Overpass error {response.status_code}: {response.text[:200]}[/red]")
            return []

        data = response.json()
        return data.get("elements", [])

    except requests.exceptions.Timeout:
        console.print("[red]  OSM: Overpass query timed out (180s)[/red]")
        return []
    except Exception as e:
        console.print(f"[red]  OSM: Error: {e}[/red]")
        return []


def _generate_grid_centers(center_lat: float, center_lng: float,
                           radius: int, sub_radius: int) -> list[tuple[float, float]]:
    """
    Generate a grid of sub-circle centers that cover the full radius.

    For a 30km radius with 10km sub-radius, generates ~7 overlapping circles.
    """
    import math

    if radius <= sub_radius:
        return [(center_lat, center_lng)]

    # How far apart to space centers (with some overlap)
    step = sub_radius * 1.5  # 1.5x gives ~25% overlap for good coverage
    step_deg_lat = step / 111_000  # ~111km per degree latitude
    step_deg_lng = step / (111_000 * math.cos(math.radians(center_lat)))

    # How many steps in each direction
    n_steps = math.ceil(radius / step)

    centers = []
    for dy in range(-n_steps, n_steps + 1):
        for dx in range(-n_steps, n_steps + 1):
            lat = center_lat + dy * step_deg_lat
            lng = center_lng + dx * step_deg_lng
            # Only include if within the original radius
            dist = math.sqrt((dy * step) ** 2 + (dx * step) ** 2)
            if dist <= radius:
                centers.append((lat, lng))

    return centers


def fetch_places(vertical: str, city: str, radius: int = 30000) -> list[dict]:
    """
    Fetch all businesses for a vertical in a city from OpenStreetMap.

    For radius > 12km, splits into sub-queries to avoid Overpass timeouts.
    Returns list of places in our standard schema.
    """
    SUB_RADIUS = 10_000  # 10km per sub-query — safe for public Overpass

    coords = get_city_coords(city)
    tags = OSM_TAGS.get(vertical, [])
    if not tags:
        raise ValueError(f"No OSM tags defined for vertical '{vertical}'")

    # Generate query centers
    if radius > SUB_RADIUS:
        centers = _generate_grid_centers(coords["lat"], coords["lng"], radius, SUB_RADIUS)
        console.print(f"[cyan]  OSM: {vertical} in {city} — {len(centers)} sub-areas (radius={radius}m)[/cyan]")
    else:
        centers = [(coords["lat"], coords["lng"])]
        console.print(f"[cyan]  OSM: {vertical} in {city} (radius={radius}m)[/cyan]")

    # Fetch all sub-areas
    all_places = {}
    for i, (lat, lng) in enumerate(centers):
        # Build query for this sub-area
        query_parts = []
        for tag_dict in tags:
            for key, value in tag_dict.items():
                r = min(radius, SUB_RADIUS)
                query_parts.append(f'  node["{key}"="{value}"](around:{r},{lat},{lng});')
                query_parts.append(f'  way["{key}"="{value}"](around:{r},{lat},{lng});')

        union_body = "\n".join(query_parts)
        query = f"[out:json][timeout:120];\n(\n{union_body}\n);\nout center body;"

        console.print(f"[dim]  OSM: Sub-area {i+1}/{len(centers)}...[/dim]")
        elements = _run_overpass_query(query)

        for element in elements:
            parsed = parse_osm_element(element)
            if parsed and parsed["id"] not in all_places:
                all_places[parsed["id"]] = parsed

        # Rate limit between sub-queries
        if i < len(centers) - 1:
            time.sleep(OVERPASS_RATE_LIMIT)

    result = list(all_places.values())
    console.print(f"[green]  OSM: {len(result)} unique businesses with names[/green]")

    return result
