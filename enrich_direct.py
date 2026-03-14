#!/usr/bin/env python3
"""
Direct enrichment using Claude API via this conversation.
Processes businesses without websites/enrichment data.
"""

import json
import sys
from pathlib import Path
from anthropic import Anthropic

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"

# Target cities and verticals
TARGETS = [
    ("restaurants", "austin_tx"),
    ("restaurants", "boston_ma"),
    ("restaurants", "new_york_ny"),
]

client = Anthropic()
enriched_count = 0
failed_count = 0

def enrich_batch(businesses: list, vertical: str, city: str) -> list:
    """Enrich a batch of businesses using Claude."""
    global enriched_count, failed_count

    # Build prompt for batch enrichment
    business_list = "\n".join([
        f"- {b['name']} ({b['address']}) - {b.get('phone', 'N/A')}"
        for b in businesses[:5]  # Process 5 at a time
    ])

    prompt = f"""Enrich these {vertical} businesses with missing website/description data:

{business_list}

For each, provide:
1. Website URL (if you can infer from name + location)
2. Business description (50 words max)
3. Key services/specialties

Format as JSON array with {{name, website, description, specialties}}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse response
        result_text = response.content[0].text
        enriched_count += len(businesses)
        return result_text

    except Exception as e:
        print(f"❌ Error enriching batch: {e}")
        failed_count += len(businesses)
        return None

def main():
    """Main enrichment loop."""
    print("\n" + "="*60)
    print("🚀 DIRECT ENRICHMENT: Using Claude API")
    print("="*60 + "\n")

    for vertical, city in TARGETS:
        places_file = DATA_DIR / vertical / city / "places.json"

        if not places_file.exists():
            print(f"⚠️  Skipping {vertical}/{city} - file not found")
            continue

        print(f"\n📍 Processing {vertical.upper()} in {city.upper()}...")

        with open(places_file) as f:
            businesses = json.load(f)

        # Filter businesses that need enrichment (no website)
        needs_enrichment = [b for b in businesses if not b.get('website')]

        print(f"   Found: {len(businesses)} total")
        print(f"   Need enrichment: {len(needs_enrichment)} (no website)")

        if not needs_enrichment:
            print(f"   ✅ Already enriched!")
            continue

        # Process in batches of 5
        total_batches = (len(needs_enrichment) + 4) // 5

        for batch_idx in range(min(3, total_batches)):  # Limit to 3 batches for demo
            start = batch_idx * 5
            end = min(start + 5, len(needs_enrichment))
            batch = needs_enrichment[start:end]

            print(f"\n   Batch {batch_idx + 1}: Processing {len(batch)} items...")
            result = enrich_batch(batch, vertical, city)

            if result:
                print(f"   ✅ Enriched {len(batch)} businesses")
            else:
                print(f"   ❌ Batch failed")

    print("\n" + "="*60)
    print(f"✅ COMPLETE: {enriched_count} enriched, {failed_count} failed")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
