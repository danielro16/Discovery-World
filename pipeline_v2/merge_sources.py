"""
merge_sources.py — Combines data from multiple sources into unified place records.

Matching strategy:
1. Exact name match (normalized) + same city → merge
2. Fuzzy name match (>85% similarity) + close coordinates (<500m) → merge
3. No match → keep as separate entries

Priority for field values:
- OSM wins for: address, coordinates, hours, phone, website (most complete)
- Public Records wins for: license_info (authoritative)
- Both contribute to: types, enriched_data

The merged output uses the same schema as V1 (places.json) for frontend compatibility.
"""

import math
from difflib import SequenceMatcher
from rich.console import Console

console = Console()


def normalize_name(name: str) -> str:
    """Normalize a business name for matching."""
    if not name:
        return ""
    name = name.lower().strip()
    # Remove common suffixes
    for suffix in [", llc", ", inc", ", pa", ", p.a.", ", dds", ", dmd", ", md",
                   " llc", " inc", " pa", " p.a.", " dds", " dmd", " md",
                   ", pllc", " pllc", ", pc", " pc"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    # Remove common prefixes
    for prefix in ["dr. ", "dr ", "the "]:
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.strip()


def name_similarity(name1: str, name2: str) -> float:
    """Calculate similarity between two business names (0-1)."""
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)
    if not n1 or not n2:
        return 0.0
    if n1 == n2:
        return 1.0
    return SequenceMatcher(None, n1, n2).ratio()


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two points in meters."""
    if not all([lat1, lng1, lat2, lng2]):
        return float("inf")

    R = 6371000  # Earth's radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def merge_two_places(osm_place: dict, pr_place: dict) -> dict:
    """
    Merge an OSM place with a public records place.

    OSM provides the base (address, coords, phone, website, hours).
    Public records adds license verification.
    """
    merged = dict(osm_place)  # start with OSM as base

    # Add license info from public records
    if pr_place.get("license_info"):
        merged["license_info"] = pr_place["license_info"]

    # Merge types (union)
    osm_types = set(osm_place.get("types", []))
    pr_types = set(pr_place.get("types", []))
    merged["types"] = list(osm_types | pr_types)

    # Track all sources
    merged["sources"] = list(set(
        [osm_place.get("source", "osm")] +
        [pr_place.get("source", "public_records")]
    ))

    # Use PR name if OSM name looks incomplete
    if len(pr_place.get("name", "")) > len(osm_place.get("name", "")):
        merged["name_alt"] = pr_place["name"]

    return merged


def merge_places(osm_places: list[dict], pr_places: list[dict]) -> list[dict]:
    """
    Merge OSM and public records places into a single list.

    Strategy:
    1. Try to match PR records to OSM records by name similarity
    2. Matched pairs are merged (OSM base + PR license info)
    3. Unmatched OSM records kept as-is
    4. Unmatched PR records kept as-is (less complete but have license data)
    """
    if not osm_places and not pr_places:
        return []

    if not pr_places:
        for p in osm_places:
            p["sources"] = ["osm"]
        return osm_places

    if not osm_places:
        for p in pr_places:
            p["sources"] = ["public_records"]
        return pr_places

    merged = []
    matched_pr_ids = set()
    match_count = 0

    for osm_place in osm_places:
        best_match = None
        best_score = 0.0

        for pr_place in pr_places:
            if pr_place["id"] in matched_pr_ids:
                continue

            score = name_similarity(osm_place["name"], pr_place["name"])

            # If we have coordinates on both sides, require proximity
            osm_loc = osm_place.get("location", {})
            pr_loc = pr_place.get("location", {})
            if (osm_loc.get("lat") and pr_loc.get("lat")):
                dist = haversine_distance(
                    osm_loc["lat"], osm_loc["lng"],
                    pr_loc["lat"], pr_loc["lng"],
                )
                if dist > 500:  # more than 500m apart
                    score *= 0.5  # penalize

            if score > best_score and score >= 0.85:
                best_score = score
                best_match = pr_place

        if best_match:
            merged_place = merge_two_places(osm_place, best_match)
            matched_pr_ids.add(best_match["id"])
            match_count += 1
            merged.append(merged_place)
        else:
            osm_place["sources"] = ["osm"]
            merged.append(osm_place)

    # Add unmatched public records
    unmatched_pr = [p for p in pr_places if p["id"] not in matched_pr_ids]
    for p in unmatched_pr:
        p["sources"] = ["public_records"]
    merged.extend(unmatched_pr)

    console.print(f"   Merged: {match_count} matched pairs")
    console.print(f"   OSM only: {len(osm_places) - match_count}")
    console.print(f"   Public Records only: {len(unmatched_pr)}")
    console.print(f"   Total: {len(merged)}")

    return merged


def calculate_completeness(place: dict) -> int:
    """
    Calculate profile completeness score (0-100).

    Same scoring as V1 but adds points for license verification.
    """
    score = 0
    checks = [
        ("name", 10),
        ("address", 10),
        ("phone", 10),
        ("website", 10),
        ("hours", 15),
        ("types", 5),
    ]
    for field, points in checks:
        value = place.get(field)
        if value and value != {} and value != [] and value != 0:
            score += points

    # Location with valid coordinates
    loc = place.get("location", {})
    if loc.get("lat") and loc.get("lng"):
        score += 5

    # License verification (V2 bonus — authoritative source)
    if place.get("license_info"):
        score += 15

    # Enriched data (filled later by enrich_data.py)
    if place.get("enriched"):
        score += 15

    # Rating (will come from our own system, not third party)
    if place.get("rating"):
        score += 5

    return min(score, 100)
