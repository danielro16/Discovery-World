#!/usr/bin/env python3
"""
Quick enrichment batch for restaurants + attorneys in 3 major cities.
Targets ~2,000 businesses in under 3 hours.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

# Target: 6 city-vertical combos
ENRICHMENT_JOBS = [
    ("restaurants", "austin_tx"),
    ("restaurants", "boston_ma"),
    ("restaurants", "new_york_ny"),
    ("attorneys", "austin_tx"),
    ("attorneys", "boston_ma"),
    ("attorneys", "new_york_ny"),
]

def run_enrichment(vertical: str, city: str):
    """Run enrichment for a vertical-city combo."""
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "pipeline" / "enrich_data.py"),
        "--vertical", vertical,
        "--city", city,
    ]

    print(f"\n{'='*60}")
    print(f"🚀 Enriching {vertical.upper()} in {city.upper()}")
    print(f"{'='*60}\n")

    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode == 0

if __name__ == "__main__":
    print("\n" + "="*60)
    print("BATCH ENRICHMENT: Restaurants + Attorneys (3 cities)")
    print("Target: ~2,000 businesses in <3 hours")
    print("="*60 + "\n")

    successful = 0
    failed = 0

    for vertical, city in ENRICHMENT_JOBS:
        try:
            if run_enrichment(vertical, city):
                successful += 1
            else:
                failed += 1
        except KeyboardInterrupt:
            print("\n⚠️  Enrichment interrupted by user")
            break
        except Exception as e:
            print(f"❌ Error enriching {vertical}/{city}: {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"✅ COMPLETE: {successful} succeeded, {failed} failed")
    print("="*60 + "\n")
