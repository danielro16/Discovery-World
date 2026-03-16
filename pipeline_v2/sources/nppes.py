"""
NPPES NPI Registry Source — Fetches licensed therapists and dentists from the
National Plan and Provider Enumeration System (CMS/HHS).

License: Public Domain (FOIA-required disclosure)
- Commercial use: ✅ allowed — FOIA-disclosable per CMS
- Caching/storage: ✅ allowed
- Attribution: not legally required, good practice
- Source: https://npiregistry.cms.hhs.gov

Data available: name, address, phone, NPI number, credential, taxonomy/specialty
Data NOT available: coordinates, website, ratings, reviews, photos

API: https://npiregistry.cms.hhs.gov/api/?version=2.1
- Free, no auth, no API key required
- Returns up to 1,200 results per query (limit=200, paginate with skip)
- Rate limit: none documented — use politely (0.5s between pages)
"""

from __future__ import annotations

import argparse
import json
import time
import sys
from pathlib import Path
from difflib import SequenceMatcher

import requests
from rich.console import Console

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATA_DIR, get_state, slugify

console = Console()

NPPES_API_URL = "https://npiregistry.cms.hhs.gov/api/"
NPPES_PAGE_SIZE = 200      # max allowed per request
NPPES_MAX_PAGES = 6        # 6 x 200 = 1,200 (API hard limit per query)
NPPES_RATE_LIMIT = 0.5     # seconds between page requests

# Taxonomy codes per vertical
# Source: NUCC Health Care Provider Taxonomy (used by NPPES)
TAXONOMY_CODES = {
    "dentists": {
        "122300000X":  "Dentist",
        "1223G0001X":  "Dentist, General Practice",
        "1223P0221X":  "Dentist, Pediatric",
        "1223S0112X":  "Oral & Maxillofacial Surgery",
        "1223X0400X":  "Orthodontics",
        "1223E0200X":  "Endodontics",
        "1223P0106X":  "Periodontics",
        "1223D0001X":  "Prosthodontics",
    },
    "therapists": {
        "101Y00000X":  "Counselor",
        "101YM0800X":  "Mental Health Counselor",
        "101YP2500X":  "Professional Counselor (LPC)",
        "106H00000X":  "Marriage & Family Therapist",
        "1041C0700X":  "Clinical Social Worker (LCSW)",
        "104100000X":  "Social Worker",
        "103T00000X":  "Psychologist",
        "103TC0700X":  "Clinical Psychologist",
    },
}

# Human-readable taxonomy description strings to query the API with
# The API's taxonomy_description parameter does a substring match on these descriptions
TAXONOMY_QUERIES = {
    "dentists":   ["dentist", "orthodontics", "endodontics", "periodontics",
                   "prosthodontics", "oral surgery"],
    "therapists": ["counselor", "mental health", "marriage", "social worker",
                   "psychologist"],
}


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _fetch_page(taxonomy_description: str, city: str, state: str,
                limit: int, skip: int) -> dict:
    """Fetch a single page from the NPPES API."""
    params = {
        "version":              "2.1",
        "taxonomy_description": taxonomy_description,
        "city":                 city.upper(),
        "state":                state.upper(),
        "limit":                limit,
        "skip":                 skip,
    }
    try:
        resp = requests.get(
            NPPES_API_URL,
            params=params,
            timeout=30,
            headers={"User-Agent": "AgentReady-Directory/2.0 (contact@agentready.com)"},
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            console.print(f"[red]  NPPES: HTTP {resp.status_code} for '{taxonomy_description}' skip={skip}[/red]")
            return {}
    except Exception as e:
        console.print(f"[red]  NPPES: Request error: {e}[/red]")
        return {}


def _fetch_all_for_query(taxonomy_description: str, city: str, state: str,
                          limit: int = NPPES_PAGE_SIZE) -> list[dict]:
    """
    Paginate through all results for a single taxonomy_description query.

    The API returns at most 1,200 records (6 pages × 200). For larger datasets
    (statewide queries) use the bulk CSV download instead.
    """
    all_results = []
    skip = 0

    while skip < NPPES_MAX_PAGES * limit:
        data = _fetch_page(taxonomy_description, city, state, limit, skip)
        results = data.get("results", [])
        result_count = data.get("result_count", 0)

        if not results:
            break

        all_results.extend(results)
        console.print(
            f"[dim]  NPPES '{taxonomy_description}': page skip={skip}, "
            f"got {len(results)}, total_available={result_count}[/dim]"
        )

        # Stop if we got everything
        if len(results) < limit or len(all_results) >= result_count:
            break

        skip += limit
        time.sleep(NPPES_RATE_LIMIT)

    return all_results


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _get_practice_address(addresses: list[dict]) -> dict:
    """
    Return the practice location address from the addresses array.

    NPPES returns two address records per provider: LOCATION and MAILING.
    We want LOCATION (practice address, not mailing address).
    Falls back to the first address if LOCATION isn't present.
    """
    for addr in addresses:
        if addr.get("address_purpose", "").upper() == "LOCATION":
            return addr
    # Fallback: return first address (often only one is present)
    return addresses[0] if addresses else {}


def _build_address_string(addr: dict) -> str:
    """Build a human-readable address string from an NPPES address dict."""
    parts = []
    line1 = addr.get("address_1", "").strip()
    line2 = addr.get("address_2", "").strip()
    city  = addr.get("city", "").strip().title()
    state = addr.get("state", "").strip().upper()
    zip_  = addr.get("postal_code", "").strip()

    if line1:
        parts.append(line1.title())
    if line2:
        parts.append(line2.title())
    if city:
        parts.append(city)
    if state:
        parts.append(state)
    if zip_:
        # Normalize ZIP+4 to standard 5-digit
        zip_display = zip_[:5] if len(zip_) > 5 else zip_
        parts.append(zip_display)

    return ", ".join(parts)


def _get_provider_name(basic: dict) -> str:
    """
    Extract provider name from the basic block.

    NPI-2 (organizations) have organization_name.
    NPI-1 (individuals) have first_name + last_name.
    """
    org_name = basic.get("organization_name", "").strip()
    if org_name:
        return org_name.title()

    first  = basic.get("first_name", "").strip()
    middle = basic.get("middle_name", "").strip()
    last   = basic.get("last_name", "").strip()
    cred   = basic.get("credential", "").strip()

    parts = [p for p in [first, middle, last] if p]
    name  = " ".join(parts).title()
    if cred:
        name = f"{name}, {cred}"
    return name


def _get_primary_taxonomy(taxonomies: list[dict]) -> dict:
    """Return the primary taxonomy entry, or the first one if none is marked primary."""
    for t in taxonomies:
        if t.get("primary"):
            return t
    return taxonomies[0] if taxonomies else {}


def _build_types(taxonomy: dict, vertical: str) -> list[str]:
    """Build the types list from taxonomy data."""
    types = [vertical.rstrip("s")]  # "dentists" -> "dentist", "therapists" -> "therapist"
    code = taxonomy.get("code", "")
    desc = taxonomy.get("desc", "")

    # Add specific specialty type if it's more specific than the generic
    code_map = TAXONOMY_CODES.get(vertical, {})
    if code in code_map:
        specific = code_map[code].lower().replace(" ", "_").replace(",", "")
        if specific not in types:
            types.append(specific)
    elif desc:
        types.append(desc.lower().replace(" ", "_").replace(",", ""))

    return types


def parse_npi_record(record: dict, vertical: str) -> dict | None:
    """
    Parse a single NPPES API result into our standard place schema.

    Returns None if the record doesn't have enough data to be useful.
    """
    npi = record.get("number", "")
    if not npi:
        return None

    basic      = record.get("basic", {})
    addresses  = record.get("addresses", [])
    taxonomies = record.get("taxonomies", [])

    # Skip inactive providers
    status = basic.get("status", "").upper()
    if status and status != "A":
        return None

    name = _get_provider_name(basic)
    if not name:
        return None

    addr     = _get_practice_address(addresses)
    address  = _build_address_string(addr)
    phone    = addr.get("telephone_number", "").strip()

    taxonomy = _get_primary_taxonomy(taxonomies)
    types    = _build_types(taxonomy, vertical)

    credential = basic.get("credential", "").strip()

    return {
        "id": f"nppes_{npi}",
        "name": name,
        "address": address,
        "location": {"lat": None, "lng": None},  # NPPES has no coordinates
        "phone": phone,
        "website": None,  # not in NPPES
        "google_maps_url": "",
        "osm_url": "",
        "rating": None,
        "review_count": 0,
        "business_status": "OPERATIONAL",
        "price_level": "",
        "types": types,
        "hours": {},
        "reviews": [],
        "photos": [],
        "enriched": False,
        "enriched_data": {
            "npi": npi,
            "credential": credential,
            "taxonomy_code": taxonomy.get("code", ""),
            "taxonomy_desc": taxonomy.get("desc", ""),
            "license_number": taxonomy.get("license", ""),
            "license_state": taxonomy.get("state", ""),
        },
        "profile_completeness": 0,
        "claimed": False,
        # V2 metadata
        "source": "nppes",
        "source_license": "Public Domain (FOIA)",
        "license_info": {
            "npi": npi,
            "credential": credential,
            "taxonomy_code": taxonomy.get("code", ""),
            "taxonomy_desc": taxonomy.get("desc", ""),
            "license_number": taxonomy.get("license", ""),
            "license_state": taxonomy.get("state", ""),
            "status": status or "A",
            "enumeration_date": basic.get("enumeration_date", ""),
            "last_updated": basic.get("last_updated", ""),
        },
    }


# ---------------------------------------------------------------------------
# Deduplication / merge into places.json
# ---------------------------------------------------------------------------

def _normalize_name(name: str) -> str:
    """Normalize a business name for matching (mirrors merge_sources.py)."""
    if not name:
        return ""
    name = name.lower().strip()
    for suffix in [", llc", ", inc", ", pa", ", p.a.", ", dds", ", dmd", ", md",
                   " llc", " inc", " pa", " p.a.", " dds", " dmd", " md",
                   ", pllc", " pllc", ", pc", " pc", ", lcsw", " lcsw",
                   ", lmft", " lmft", ", lpc", " lpc"]:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    for prefix in ["dr. ", "dr ", "the "]:
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.strip()


def _name_similarity(a: str, b: str) -> float:
    n1 = _normalize_name(a)
    n2 = _normalize_name(b)
    if not n1 or not n2:
        return 0.0
    if n1 == n2:
        return 1.0
    return SequenceMatcher(None, n1, n2).ratio()


def _addresses_similar(addr1: str, addr2: str) -> bool:
    """
    Check if two address strings are similar enough to consider a match.

    For NPPES records (no coordinates), we fall back to address substring
    matching — the street number + street name should overlap.
    """
    if not addr1 or not addr2:
        return True  # can't rule out, don't penalise

    a1 = addr1.lower().split(",")[0].strip()  # just street portion
    a2 = addr2.lower().split(",")[0].strip()

    if not a1 or not a2:
        return True

    # Consider similar if one address starts with the other (accounts for
    # slight formatting differences like "Suite 100" inclusion)
    return a1 in a2 or a2 in a1 or SequenceMatcher(None, a1, a2).ratio() >= 0.80


def merge_nppes_into_places(
    existing_places: list[dict], nppes_places: list[dict]
) -> list[dict]:
    """
    Merge NPPES records into an existing places list.

    Strategy:
    - Match on name similarity >= 0.85 AND address similarity
    - If matched: enrich the existing place with NPPES license_info, NPI data
    - If unmatched: append NPPES record as a new place (it has valid address/phone)

    Returns the merged list.
    """
    merged = list(existing_places)
    matched_nppes_ids = set()
    match_count = 0

    for nppes_place in nppes_places:
        best_match_idx = None
        best_score = 0.0

        for i, existing in enumerate(merged):
            score = _name_similarity(existing["name"], nppes_place["name"])
            if score < 0.85:
                continue

            # Require address similarity when NPPES has an address
            if nppes_place.get("address") and existing.get("address"):
                if not _addresses_similar(existing["address"], nppes_place["address"]):
                    score *= 0.5

            if score > best_score:
                best_score = score
                best_match_idx = i

        if best_match_idx is not None and best_score >= 0.85:
            # Enrich existing record with NPPES license data
            existing = merged[best_match_idx]
            existing.setdefault("license_info", {})
            existing["license_info"].update(nppes_place["license_info"])
            existing["enriched_data"].update(nppes_place["enriched_data"])

            # Add nppes to sources list
            sources = existing.get("sources", [existing.get("source", "osm")])
            if "nppes" not in sources:
                sources.append("nppes")
            existing["sources"] = sources

            # Fill phone if missing
            if not existing.get("phone") and nppes_place.get("phone"):
                existing["phone"] = nppes_place["phone"]

            # Fill address if missing
            if not existing.get("address") and nppes_place.get("address"):
                existing["address"] = nppes_place["address"]

            matched_nppes_ids.add(nppes_place["id"])
            match_count += 1
        else:
            # No match — add as a new place
            nppes_place["sources"] = ["nppes"]
            merged.append(nppes_place)
            matched_nppes_ids.add(nppes_place["id"])

    new_count = sum(1 for p in nppes_places if p["id"] in matched_nppes_ids
                    and p["id"] not in {ep["id"] for ep in existing_places})
    console.print(f"   NPPES matched (enriched existing): {match_count}")
    console.print(f"   NPPES new places added: {len(nppes_places) - match_count}")
    console.print(f"   Total after merge: {len(merged)}")
    return merged


# ---------------------------------------------------------------------------
# Profile completeness
# ---------------------------------------------------------------------------

def calculate_completeness(place: dict) -> int:
    """Calculate profile completeness score (0-100), matching pipeline convention."""
    score = 0
    if place.get("name"):          score += 10
    if place.get("address"):       score += 10
    if place.get("phone"):         score += 10
    if place.get("website"):       score += 10
    if place.get("hours"):         score += 15
    if place.get("types"):         score += 5
    loc = place.get("location", {})
    if loc.get("lat") and loc.get("lng"):
        score += 5
    if place.get("license_info"):  score += 15
    if place.get("enriched"):      score += 15
    if place.get("rating"):        score += 5
    return min(score, 100)


# ---------------------------------------------------------------------------
# Main fetch function (importable by other pipeline scripts)
# ---------------------------------------------------------------------------

def fetch_places(vertical: str, city: str, limit: int = NPPES_PAGE_SIZE) -> list[dict]:
    """
    Fetch all NPPES records for a vertical in a city.

    vertical: "dentists" or "therapists"
    city: e.g. "Miami, FL" (city and state together) or just "Miami"
    limit: page size (default 200, max 200; use 10 for quick tests)

    Returns a list of place dicts in our standard schema.
    """
    # Parse city/state
    city_clean = city.strip()
    try:
        state = get_state(city_clean)
    except ValueError:
        # Try to extract state from city string directly
        parts = city_clean.split(",")
        if len(parts) == 2:
            city_clean = parts[0].strip()
            state = parts[1].strip().upper()
        else:
            console.print(f"[red]  NPPES: Cannot determine state for '{city}'[/red]")
            return []

    # city_name is just the city part (without state)
    city_name = city_clean.split(",")[0].strip()

    queries = TAXONOMY_QUERIES.get(vertical)
    if not queries:
        console.print(f"[red]  NPPES: Unknown vertical '{vertical}'[/red]")
        return []

    console.print(f"[cyan]  NPPES: Fetching {vertical} in {city_name}, {state}[/cyan]")

    # Collect raw results, deduplicated by NPI number
    seen_npis: dict[str, dict] = {}

    for query_term in queries:
        console.print(f"[dim]  NPPES: querying taxonomy_description='{query_term}'...[/dim]")
        raw_results = _fetch_all_for_query(query_term, city_name, state, limit=limit)

        for record in raw_results:
            npi = record.get("number", "")
            if npi and npi not in seen_npis:
                seen_npis[npi] = record

        time.sleep(NPPES_RATE_LIMIT)

    console.print(f"[dim]  NPPES: {len(seen_npis)} unique NPI records before parsing[/dim]")

    # Parse records into our schema
    places = []
    skipped = 0
    for record in seen_npis.values():
        parsed = parse_npi_record(record, vertical)
        if parsed:
            parsed["profile_completeness"] = calculate_completeness(parsed)
            places.append(parsed)
        else:
            skipped += 1

    console.print(f"[green]  NPPES: {len(places)} valid places ({skipped} skipped/inactive)[/green]")
    return places


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fetch therapist/dentist data from NPPES NPI Registry API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test — 10 dentists in Miami FL
  python nppes.py --vertical dentists --city "Miami, FL" --limit 10

  # Full fetch — all therapists in Miami FL, save to data_v2
  python nppes.py --vertical therapists --city "Miami, FL"

  # Full dentists, merge into places.json
  python nppes.py --vertical dentists --city "Miami, FL" --merge
        """,
    )
    parser.add_argument(
        "--vertical",
        required=True,
        choices=["dentists", "therapists"],
        help="Which vertical to fetch",
    )
    parser.add_argument(
        "--city",
        required=True,
        help='City and state, e.g. "Miami, FL"',
    )
    parser.add_argument(
        "--state",
        help="State abbreviation (optional if included in --city)",
    )
    parser.add_argument(
        "--radius",
        type=int,
        default=None,
        help="(Optional) radius in meters — not used by NPPES API (city-level query only)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=NPPES_PAGE_SIZE,
        help=f"Page size (default {NPPES_PAGE_SIZE}, max 200). Use 10 for quick tests.",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge NPPES results into existing places.json (default: save nppes.json only)",
    )
    args = parser.parse_args()

    # Combine city + state if --state provided separately
    city_arg = args.city
    if args.state and "," not in city_arg:
        city_arg = f"{city_arg}, {args.state}"

    # Determine output paths
    city_clean = city_arg.strip()
    parts = city_clean.split(",")
    city_name = parts[0].strip()
    state = parts[1].strip().upper() if len(parts) > 1 else ""

    city_slug = city_name.lower().replace(" ", "_") + (f"_{state.lower()}" if state else "")
    out_dir = DATA_DIR / args.vertical / city_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    nppes_file  = out_dir / "nppes.json"
    places_file = out_dir / "places.json"

    console.print(f"\n[bold]NPPES Fetch[/bold]")
    console.print(f"  Vertical : {args.vertical}")
    console.print(f"  City     : {city_name}, {state}")
    console.print(f"  Limit    : {args.limit} per page")
    console.print(f"  Output   : {out_dir}")
    console.print()

    # Fetch
    places = fetch_places(args.vertical, city_arg, limit=args.limit)

    if not places:
        console.print("[yellow]No results returned. Exiting.[/yellow]")
        sys.exit(0)

    # Save raw NPPES results
    with open(nppes_file, "w") as f:
        json.dump(places, f, indent=2)
    console.print(f"\n[green]Saved {len(places)} records → {nppes_file}[/green]")

    # Optionally merge into places.json
    if args.merge:
        if places_file.exists():
            with open(places_file) as f:
                existing = json.load(f)
            console.print(f"\n[cyan]Merging into {places_file} ({len(existing)} existing)...[/cyan]")
        else:
            existing = []
            console.print(f"\n[cyan]No existing places.json — creating from NPPES data...[/cyan]")

        merged = merge_nppes_into_places(existing, places)

        # Recalculate completeness for all
        for p in merged:
            p["profile_completeness"] = calculate_completeness(p)

        with open(places_file, "w") as f:
            json.dump(merged, f, indent=2)
        console.print(f"[green]Saved {len(merged)} total places → {places_file}[/green]")

    console.print("\n[bold green]Done.[/bold green]")


if __name__ == "__main__":
    main()
