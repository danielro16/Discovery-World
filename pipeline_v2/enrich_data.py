"""
enrich_data.py (V2) — Enriches business data by scraping websites and extracting
structured info using Claude API. Works with data_v2/ directory.

Usage:
    python pipeline_v2/enrich_data.py --vertical dentists --city miami_fl
    python pipeline_v2/enrich_data.py --vertical dentists --city miami_fl --limit 50
    python pipeline_v2/enrich_data.py --all-target-cities --verticals dentists attorneys
    python pipeline_v2/enrich_data.py --vertical attorneys --city new_york_ny --limit 20

City slugs match data_v2 folder names (e.g., miami_fl, new_york_ny, austin_tx).

This script:
1. Loads places.json from data_v2/<vertical>/<city>/
2. For each business with a website that hasn't been enriched, fetches page content
3. Uses Claude API to extract structured fields (insurance, specialties, languages, etc.)
4. Analyzes reviews (sentiment, themes)
5. Recalculates profile_completeness score
6. Saves updated places.json in place
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Make pipeline_v2 importable
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import track
import anthropic

from pipeline_v2.config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    load_vertical,
    get_data_path,
    DATA_DIR,
)

console = Console()

# Target cities and verticals for the --all-target-cities flag
TARGET_CITIES = ["miami_fl", "new_york_ny", "austin_tx", "san_francisco_ca", "seattle_wa"]
HIGH_VALUE_VERTICALS = ["dentists", "attorneys"]


def fetch_website_text(url: str, max_chars: int = 15000) -> str:
    """Fetch a website and extract clean text content."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; AgentReady/1.0; business directory)"
        }
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "iframe"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines)

        return text[:max_chars]

    except Exception as e:
        return ""


def extract_with_claude(website_text: str, extraction_prompt: str, business_name: str) -> dict:
    """Use Claude API to extract structured data from website text."""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""You are analyzing the website of a business called "{business_name}".

Here is the text content from their website:

<website_content>
{website_text}
</website_content>

{extraction_prompt}

Return ONLY valid JSON, nothing else. No markdown, no explanation."""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()

        # Clean potential markdown fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        if text.startswith("json"):
            text = text[4:]

        return json.loads(text.strip())

    except json.JSONDecodeError:
        console.print(f"  [yellow]Warning: Could not parse Claude response for {business_name}[/yellow]")
        return {}
    except Exception as e:
        console.print(f"  [red]Error: Claude API error for {business_name}: {e}[/red]")
        return {}


def analyze_reviews(reviews: list) -> dict:
    """Analyze reviews to extract sentiment and key themes."""
    if not reviews:
        return {"sentiment": None, "themes": [], "summary": ""}

    review_texts = [r["text"] for r in reviews if r.get("text")]
    if not review_texts:
        return {"sentiment": None, "themes": [], "summary": ""}

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    combined = "\n---\n".join(review_texts[:10])  # Max 10 reviews

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": f"""Analyze these business reviews and return JSON only:

<reviews>
{combined}
</reviews>

Return this exact JSON structure:
{{
  "sentiment": "positive" or "mixed" or "negative",
  "score": 0-100 (overall sentiment score),
  "themes_positive": ["list of positive themes mentioned"],
  "themes_negative": ["list of negative themes or complaints"],
  "summary": "One sentence summary of what patients/customers say"
}}

Return ONLY valid JSON, nothing else."""
            }]
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        if text.startswith("json"):
            text = text[4:]

        return json.loads(text.strip())
    except Exception:
        return {"sentiment": None, "themes": [], "summary": ""}


def calculate_completeness(place: dict) -> int:
    """Recalculate profile completeness score (0-100)."""
    score = 0
    basic_fields = [
        ("name", 8), ("address", 8), ("phone", 8), ("website", 8),
        ("rating", 5), ("review_count", 5), ("hours", 10),
        ("reviews", 8), ("photos", 5),
    ]
    for field, points in basic_fields:
        value = place.get(field)
        if value and value != {} and value != [] and value != 0:
            score += points

    if place.get("enriched"):
        enriched = place.get("enriched_data", {})
        enriched_fields = len([v for v in enriched.values() if v is not None and v != [] and v != ""])
        score += min(enriched_fields * 5, 35)

    return min(score, 100)


def enrich_vertical(vertical_name: str, city_slug: str, limit: int = None, data_dir: Path = None) -> dict:
    """
    Enrich all businesses in a vertical+city with website data.
    Returns a summary dict with counts.
    """

    if not ANTHROPIC_API_KEY:
        console.print("[red]ERROR: ANTHROPIC_API_KEY not set in .env[/red]")
        return {"enriched": 0, "skipped": 0, "failed": 0}

    vertical = load_vertical(vertical_name)

    # Allow override of data directory (for testing or alternate paths)
    if data_dir:
        places_file = data_dir / vertical_name / city_slug / "places.json"
    else:
        # pipeline_v2 config.get_data_path uses DATA_DIR = data_v2
        places_file = DATA_DIR / vertical_name / city_slug / "places.json"

    if not places_file.exists():
        console.print(f"[red]No data found at {places_file}[/red]")
        return {"enriched": 0, "skipped": 0, "failed": 0}

    with open(places_file) as f:
        places = json.load(f)

    console.print(f"\n[bold cyan]Enriching {vertical['display_name']} in {city_slug}[/bold cyan]")
    console.print(f"   Total businesses: {len(places)}")

    # Filter to those with websites that haven't been enriched
    to_enrich = [p for p in places if p.get("website") and not p.get("enriched")]

    if limit:
        to_enrich = to_enrich[:limit]

    already_done = len([p for p in places if p.get("enriched")])
    console.print(f"   Already enriched: {already_done}")
    console.print(f"   To enrich now:    {len(to_enrich)}\n")

    if not to_enrich:
        console.print("   [dim]Nothing to enrich — all websites already processed.[/dim]")
        return {"enriched": 0, "skipped": 0, "failed": 0}

    enriched_count = 0
    failed_count = 0

    for place in track(to_enrich, description=f"  {city_slug}/{vertical_name}"):
        name = place["name"]
        website = place["website"]

        # Step 1: Fetch website content
        website_text = fetch_website_text(website)

        if not website_text:
            console.print(f"  [dim]Could not fetch: {name} ({website})[/dim]")
            failed_count += 1
            continue

        # Step 2: Extract structured data with Claude
        extracted = extract_with_claude(
            website_text,
            vertical["extraction_prompt"],
            name
        )

        if extracted:
            place["enriched_data"] = extracted
            place["enriched"] = True
            enriched_count += 1
        else:
            failed_count += 1

        # Step 3: Analyze reviews (only if reviews present and not yet analyzed)
        if place.get("reviews") and not place.get("review_analysis"):
            review_analysis = analyze_reviews(place["reviews"])
            place["review_analysis"] = review_analysis

        # Step 4: Recalculate completeness
        place["profile_completeness"] = calculate_completeness(place)

        # Rate limit: be gentle on Claude API and target websites
        time.sleep(1)

    # Save enriched data back in place
    with open(places_file, "w") as f:
        json.dump(places, f, indent=2, ensure_ascii=False)

    console.print(f"   [bold green]Done![/bold green] Enriched {enriched_count}, failed/skipped {failed_count}")
    console.print(f"   Saved to: {places_file}")

    # Show completeness stats
    completeness = [p.get("profile_completeness", 0) for p in places]
    avg = sum(completeness) / max(len(completeness), 1)
    enriched_all = [p for p in places if p.get("enriched")]
    console.print(f"   Total enriched: {len(enriched_all)}/{len(places)} | Avg completeness: {avg:.0f}%")

    return {"enriched": enriched_count, "skipped": failed_count, "failed": failed_count}


def main():
    parser = argparse.ArgumentParser(
        description="Enrich data_v2 business data with website info via Claude API"
    )
    parser.add_argument("--vertical", help="Vertical name (e.g., dentists, attorneys)")
    parser.add_argument(
        "--city",
        help="City slug matching data_v2 folder name (e.g., miami_fl, new_york_ny)"
    )
    parser.add_argument("--limit", type=int, help="Limit number of businesses to enrich per city/vertical")
    parser.add_argument(
        "--all-target-cities",
        action="store_true",
        help="Run enrichment for Miami, NYC, Austin, SF, Seattle"
    )
    parser.add_argument(
        "--verticals",
        nargs="+",
        default=HIGH_VALUE_VERTICALS,
        help="Verticals to process with --all-target-cities (default: dentists attorneys)"
    )
    parser.add_argument(
        "--data-dir",
        help="Override data directory (default: data_v2/)"
    )

    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else None

    if args.all_target_cities:
        verticals = args.verticals
        console.print(f"\n[bold]Running enrichment for target cities: {TARGET_CITIES}[/bold]")
        console.print(f"[bold]Verticals: {verticals}[/bold]\n")

        total_enriched = 0
        total_failed = 0

        for vertical in verticals:
            for city in TARGET_CITIES:
                result = enrich_vertical(
                    vertical_name=vertical,
                    city_slug=city,
                    limit=args.limit,
                    data_dir=data_dir
                )
                total_enriched += result["enriched"]
                total_failed += result["failed"]

        console.print(f"\n[bold green]All target cities complete![/bold green]")
        console.print(f"   Total enriched: {total_enriched} | Total failed/skipped: {total_failed}")

    elif args.vertical and args.city:
        enrich_vertical(
            vertical_name=args.vertical,
            city_slug=args.city,
            limit=args.limit,
            data_dir=data_dir
        )

    else:
        parser.print_help()
        console.print("\n[yellow]Examples:[/yellow]")
        console.print("  python pipeline_v2/enrich_data.py --vertical dentists --city miami_fl")
        console.print("  python pipeline_v2/enrich_data.py --all-target-cities --limit 20")
        console.print("  python pipeline_v2/enrich_data.py --all-target-cities --verticals dentists")
        sys.exit(1)


if __name__ == "__main__":
    main()
