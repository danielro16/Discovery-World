"""
enrich_data.py — Enriches business data by scraping websites and extracting
structured info using Claude API.

Usage:
    python pipeline/enrich_data.py --vertical dentists --city miami
    python pipeline/enrich_data.py --vertical dentists --city miami --limit 50

This script:
1. Loads fetched places data
2. For each business with a website, fetches the page content
3. Uses Claude API to extract structured fields (insurance, specialties, etc.)
4. Saves enriched data back to the JSON
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import track
import anthropic

from config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    load_vertical,
    get_data_path,
)

console = Console()


def fetch_website_text(url: str, max_chars: int = 15000) -> str:
    """Fetch a website and extract clean text content."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; AgentReady/1.0; business directory)"
        }
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove script, style, nav, footer elements
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
        console.print(f"  [yellow]⚠ Could not parse Claude response for {business_name}[/yellow]")
        return {}
    except Exception as e:
        console.print(f"  [red]✗ Claude API error for {business_name}: {e}[/red]")
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
    except:
        return {"sentiment": None, "themes": [], "summary": ""}


def enrich_vertical(vertical_name: str, city: str, limit: int = None):
    """Enrich all businesses in a vertical with website data."""
    
    if not ANTHROPIC_API_KEY:
        console.print("[red]ERROR: ANTHROPIC_API_KEY not set in .env[/red]")
        return
    
    vertical = load_vertical(vertical_name)
    data_path = get_data_path(vertical_name, city)
    places_file = data_path / "places.json"
    
    if not places_file.exists():
        console.print(f"[red]No data found at {places_file}. Run fetch_places.py first.[/red]")
        return
    
    with open(places_file) as f:
        places = json.load(f)
    
    console.print(f"\n[bold cyan]🔬 Enriching {vertical['display_name']} in {city}[/bold cyan]")
    console.print(f"   Total businesses: {len(places)}")
    
    # Filter to those with websites that haven't been enriched
    to_enrich = [p for p in places if p.get("website") and not p.get("enriched")]
    
    if limit:
        to_enrich = to_enrich[:limit]
    
    console.print(f"   To enrich: {len(to_enrich)}\n")
    
    enriched_count = 0
    
    for place in track(to_enrich, description="Enriching..."):
        name = place["name"]
        website = place["website"]
        
        # Step 1: Fetch website content
        website_text = fetch_website_text(website)
        
        if not website_text:
            console.print(f"  [dim]⊘ Could not fetch: {name}[/dim]")
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
        
        # Step 3: Analyze reviews
        if place.get("reviews"):
            review_analysis = analyze_reviews(place["reviews"])
            place["review_analysis"] = review_analysis
        
        # Recalculate completeness
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
            enriched = place["enriched_data"]
            enriched_fields = len([v for v in enriched.values() if v is not None and v != []])
            score += min(enriched_fields * 5, 35)
        
        place["profile_completeness"] = min(score, 100)
        
        # Rate limit: ~1 request per second for Claude API
        time.sleep(1)
    
    # Save enriched data
    with open(places_file, "w") as f:
        json.dump(places, f, indent=2, ensure_ascii=False)
    
    console.print(f"\n[bold green]✅ Enrichment complete![/bold green]")
    console.print(f"   Successfully enriched: {enriched_count}/{len(to_enrich)}")
    console.print(f"   Saved to: {places_file}")
    
    # Show completeness distribution
    completeness = [p.get("profile_completeness", 0) for p in places]
    avg = sum(completeness) / max(len(completeness), 1)
    console.print(f"   Avg profile completeness: {avg:.0f}%")


def main():
    parser = argparse.ArgumentParser(description="Enrich business data with website info")
    parser.add_argument("--vertical", required=True, help="Vertical name")
    parser.add_argument("--city", required=True, help="City slug (e.g., miami)")
    parser.add_argument("--limit", type=int, help="Limit number of businesses to enrich")
    
    args = parser.parse_args()
    enrich_vertical(args.vertical, args.city, args.limit)


if __name__ == "__main__":
    main()
