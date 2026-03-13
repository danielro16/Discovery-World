#!/usr/bin/env python3
"""Merge enriched data into places.json files."""
import json
import sys
from pathlib import Path

def merge_enriched(places_path, enriched_data):
    """Merge enriched data into places.json by matching index (0-based)."""
    with open(places_path) as f:
        places = json.load(f)

    # Build lookup by index
    enriched_by_index = {item['index']: item for item in enriched_data}

    updated = 0
    for idx, place in enumerate(places):
        # enriched_data uses 1-based index
        item = enriched_by_index.get(idx + 1)
        if not item:
            continue

        # Map enriched fields to place
        if item.get('specialties'):
            place['specialties'] = item['specialties']
        if item.get('classes'):
            place['classes'] = item['classes']
        if item.get('insurance'):
            place['insurance_accepted'] = item['insurance']
        if item.get('therapy_types'):
            place['therapy_types'] = item['therapy_types']
        if item.get('languages'):
            place['languages'] = item['languages']
        if item.get('description'):
            place['ai_description'] = item['description']
        if item.get('tags'):
            place['tags'] = item['tags']
        if item.get('year_established'):
            place['year_established'] = item['year_established']
        if item.get('certifications'):
            place['certifications'] = item['certifications']
        if item.get('email'):
            place['email'] = item['email']
        if item.get('emails_all'):
            place['emails_all'] = item['emails_all']

        place['enriched'] = True
        updated += 1

    with open(places_path, 'w') as f:
        json.dump(places, f, indent=2, ensure_ascii=False)

    print(f"✅ Updated {updated}/{len(places)} places in {places_path}")
    return updated

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: merge_enriched.py <places.json> <enriched.json>")
        sys.exit(1)

    places_path = sys.argv[1]
    enriched_path = sys.argv[2]

    with open(enriched_path) as f:
        enriched_data = json.load(f)

    merge_enriched(places_path, enriched_data)
