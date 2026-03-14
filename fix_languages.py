#!/usr/bin/env python3
"""
Re-processes languages_spoken for all enriched businesses.
Scrapes the website again (or uses cached text from reviews/name)
and applies the new strict find_languages() logic.
"""
import json, os, re, time, sys
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from heuristic_enrich import find_languages

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

def scrape_text(url: str, timeout=8) -> str:
    """Fetch page and return stripped visible text."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code != 200:
            return ''
        html = r.text
        # Remove scripts and styles
        html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.S|re.I)
        html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.S|re.I)
        # Strip tags
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:12000]
    except Exception:
        return ''

def process_business(b: dict) -> tuple[str, list, list]:
    """Returns (place_id, old_langs, new_langs)"""
    place_id = b.get('id') or b.get('place_id') or b.get('name', '')
    old_langs = b.get('languages_spoken', ['English'])
    website = b.get('website', '')

    if not website:
        new_langs = ['English']
    else:
        text = scrape_text(website)
        if not text:
            new_langs = ['English']
        else:
            new_langs = find_languages(text)

    return place_id, old_langs, new_langs

def process_file(places_file: str, workers: int = 20) -> dict:
    with open(places_file, 'r') as f:
        data = json.load(f)

    enriched = [b for b in data if b.get('enriched')]
    if not enriched:
        return {'file': places_file, 'total': 0, 'changed': 0}

    # Map place_id -> index for fast lookup
    id_to_idx = {}
    for i, b in enumerate(data):
        pid = b.get('id') or b.get('place_id') or b.get('name', '')
        id_to_idx[pid] = i

    changed = 0
    removed_langs = []
    added_langs = []

    with ThreadPoolExecutor(max_workers=workers) as exe:
        futures = {exe.submit(process_business, b): b for b in enriched}
        for future in as_completed(futures):
            try:
                place_id, old_langs, new_langs = future.result()
                idx = id_to_idx.get(place_id)
                if idx is not None:
                    if set(old_langs) != set(new_langs):
                        changed += 1
                        removed = [l for l in old_langs if l not in new_langs]
                        added = [l for l in new_langs if l not in old_langs]
                        if removed:
                            removed_langs.extend(removed)
                        if added:
                            added_langs.extend(added)
                    data[idx]['languages_spoken'] = new_langs
            except Exception as e:
                pass

    with open(places_file, 'w') as f:
        json.dump(data, f, ensure_ascii=False)

    return {
        'file': places_file,
        'total': len(enriched),
        'changed': changed,
        'removed_langs': removed_langs,
        'added_langs': added_langs
    }

def main():
    verticals = ['dentists', 'gyms', 'attorneys', 'therapists', 'restaurants']
    base_dir = os.path.dirname(os.path.abspath(__file__))

    total_changed = 0
    total_processed = 0
    all_removed = {}
    all_added = {}

    for vertical in verticals:
        vdir = os.path.join(base_dir, 'data', vertical)
        if not os.path.isdir(vdir):
            continue
        cities = sorted(os.listdir(vdir))
        print(f'\n{"="*60}')
        print(f' {vertical.upper()} — {len(cities)} ciudades')
        print(f'{"="*60}')

        for city in cities:
            places_file = os.path.join(vdir, city, 'places.json')
            if not os.path.isfile(places_file):
                continue

            result = process_file(places_file, workers=20)
            total_processed += result['total']
            total_changed += result['changed']

            for l in result.get('removed_langs', []):
                all_removed[l] = all_removed.get(l, 0) + 1
            for l in result.get('added_langs', []):
                all_added[l] = all_added.get(l, 0) + 1

            pct = result['changed']/result['total']*100 if result['total'] > 0 else 0
            print(f'  {city:25s}  {result["total"]:>4} enriched  →  {result["changed"]:>4} changed ({pct:.0f}%)')

    print(f'\n{"="*60}')
    print(f' RESUMEN FINAL')
    print(f'{"="*60}')
    print(f'  Total procesados: {total_processed}')
    print(f'  Total cambiados:  {total_changed} ({total_changed/total_processed*100:.1f}%)')

    if all_removed:
        print(f'\n  Idiomas REMOVIDOS (falsos positivos):')
        for l, c in sorted(all_removed.items(), key=lambda x: -x[1]):
            print(f'    {l:25s} -{c}')
    if all_added:
        print(f'\n  Idiomas AGREGADOS (English donde faltaba):')
        for l, c in sorted(all_added.items(), key=lambda x: -x[1]):
            print(f'    {l:25s} +{c}')

if __name__ == '__main__':
    main()
