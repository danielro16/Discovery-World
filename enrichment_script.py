#!/usr/bin/env python3
"""
Business Enrichment Script using Anthropic Python SDK
Enriches restaurant and attorney data with website content extraction
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any
import logging

import requests
from bs4 import BeautifulSoup
import anthropic

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
BASE_DIR = Path("/Users/daniel/Library/Mobile Documents/com~apple~CloudDocs/Discovery World")
DATA_DIR = BASE_DIR / "data"

TARGET_FILES = [
    DATA_DIR / "restaurants/austin_tx/places.json",
    DATA_DIR / "restaurants/boston_ma/places.json",
    DATA_DIR / "restaurants/new_york_ny/places.json",
    DATA_DIR / "attorneys/austin_tx/places.json",
    DATA_DIR / "attorneys/boston_ma/places.json",
    DATA_DIR / "attorneys/new_york_ny/places.json",
]

# Request timeout in seconds
REQUEST_TIMEOUT = 10

# Initialize Anthropic client
client = anthropic.Anthropic()

def fetch_website_content(url: str) -> Optional[str]:
    """Fetch and clean website content"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers)
        response.raise_for_status()

        # Parse and clean HTML
        soup = BeautifulSoup(response.content, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        for nav in soup(["nav"]):
            nav.decompose()
        for footer in soup(["footer"]):
            footer.decompose()

        # Get text
        text = soup.get_text(separator=' ', strip=True)

        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        # Limit to first 8000 characters
        return text[:8000] if text else None
    except Exception as e:
        logger.debug(f"Failed to fetch {url}: {e}")
        return None

def extract_enrichment_data(business: Dict[str, Any], website_content: str, vertical: str) -> Dict[str, Any]:
    """Use Claude to extract structured enrichment data from website content"""

    if vertical == "restaurants":
        extraction_prompt = f"""Extract the following information from this restaurant website content:
- insurance_accepted: List of insurance types accepted (e.g., "Aetna", "BlueCross") or "Not specified"
- specialties: List of specialties or signature dishes
- hours: Operating hours in a standard format
- dietary_options: List of dietary options available (e.g., "vegetarian", "vegan", "gluten-free")
- cuisine_types: List of cuisine types
- price_range: Price range (e.g., "$", "$$", "$$$", "$$$$" or actual price)

Business name: {business.get('name', 'Unknown')}

Website content:
{website_content[:5000]}

Return ONLY valid JSON (no markdown, no code blocks) with these exact keys:
{{"insurance_accepted": [], "specialties": [], "hours": "", "dietary_options": [], "cuisine_types": [], "price_range": ""}}
"""
    else:  # attorneys
        extraction_prompt = f"""Extract the following information from this attorney/law firm website content:
- practice_areas: List of practice areas (e.g., "Personal Injury", "Family Law")
- experience_years: Years of experience if mentioned, otherwise null
- licenses: List of licenses/bar admissions
- certifications: List of certifications or specializations
- languages_spoken: List of languages spoken
- fees_structure: Fee structure description (e.g., "contingency", "hourly", fixed")

Business name: {business.get('name', 'Unknown')}

Website content:
{website_content[:5000]}

Return ONLY valid JSON (no markdown, no code blocks) with these exact keys:
{{"practice_areas": [], "experience_years": null, "licenses": [], "certifications": [], "languages_spoken": [], "fees_structure": ""}}
"""

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": extraction_prompt
                }
            ]
        )

        # Extract JSON from response
        response_text = message.content[0].text.strip()

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        enriched_data = json.loads(response_text)
        return enriched_data
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON response: {e}")
        return {}
    except Exception as e:
        logger.warning(f"Claude API error: {e}")
        return {}

def process_file(file_path: Path) -> tuple[int, int, float]:
    """Process a single places.json file. Returns (total_processed, newly_enriched, avg_completeness)"""

    if not file_path.exists():
        logger.warning(f"File not found: {file_path}")
        return 0, 0, 0.0

    # Determine vertical from path
    vertical = "restaurants" if "restaurants" in str(file_path) else "attorneys"
    city = file_path.parent.name

    logger.info(f"\nProcessing {vertical.upper()} in {city.upper()}")

    # Load data
    with open(file_path, 'r', encoding='utf-8') as f:
        businesses = json.load(f)

    newly_enriched = 0
    total_processed = 0
    completeness_scores = []

    for i, business in enumerate(businesses):
        # Check if already enriched
        if business.get('enriched'):
            completeness_scores.append(business.get('profile_completeness', 0))
            continue

        # Check if has website
        if not business.get('website'):
            continue

        total_processed += 1

        # Fetch website content
        website_content = fetch_website_content(business['website'])

        if not website_content:
            logger.debug(f"  [{i+1}/{len(businesses)}] Could not fetch {business.get('name', 'Unknown')}")
            continue

        # Extract enrichment data
        enriched_data = extract_enrichment_data(business, website_content, vertical)

        if enriched_data:
            # Calculate profile completeness
            field_count = sum(1 for v in enriched_data.values() if v and v != "" and v != [])
            profile_completeness = (field_count / len(enriched_data)) * 100

            # Update business record
            business['enriched'] = True
            business['enriched_data'] = enriched_data
            business['profile_completeness'] = profile_completeness
            newly_enriched += 1
            completeness_scores.append(profile_completeness)

            logger.info(f"  [{i+1}/{len(businesses)}] ✓ Enriched: {business.get('name', 'Unknown')[:40]}")
        else:
            logger.debug(f"  [{i+1}/{len(businesses)}] Failed to extract data from {business.get('name', 'Unknown')}")

        # Rate limiting to avoid overwhelming the API
        if newly_enriched % 5 == 0:
            time.sleep(1)

    # Calculate average completeness
    avg_completeness = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0.0

    # Save updated data
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(businesses, f, indent=2, ensure_ascii=False)

    logger.info(f"  Summary: {newly_enriched} newly enriched, avg completeness: {avg_completeness:.1f}%")

    return total_processed, newly_enriched, avg_completeness

def main():
    """Main execution function"""
    logger.info("=" * 70)
    logger.info("BUSINESS ENRICHMENT PIPELINE")
    logger.info("=" * 70)

    total_businesses_processed = 0
    total_enriched = 0
    all_completeness = []

    start_time = time.time()

    for file_path in TARGET_FILES:
        processed, enriched, avg_completeness = process_file(file_path)
        total_businesses_processed += processed
        total_enriched += enriched
        if avg_completeness > 0:
            all_completeness.append(avg_completeness)

    elapsed_time = time.time() - start_time
    overall_completeness = sum(all_completeness) / len(all_completeness) if all_completeness else 0.0

    logger.info("\n" + "=" * 70)
    logger.info("ENRICHMENT COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total businesses with websites processed: {total_businesses_processed}")
    logger.info(f"Newly enriched: {total_enriched}")
    logger.info(f"Overall profile completeness: {overall_completeness:.1f}%")
    logger.info(f"Time elapsed: {elapsed_time:.1f}s")
    logger.info("=" * 70)

if __name__ == "__main__":
    main()
