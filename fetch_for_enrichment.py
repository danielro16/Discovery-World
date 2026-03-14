#!/usr/bin/env python3
"""
Fetch website content for top unenriched businesses.
Saves raw content to temp JSON for in-conversation enrichment.
"""
import json
import re
import ssl
import sys
import urllib.request
import urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

DATA_DIR = Path(__file__).parent / "data"
TMP_DIR = Path(__file__).parent / "tmp_enrich"
TMP_DIR.mkdir(exist_ok=True)

def fetch_page(url: str, timeout: int = 10) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    req = urllib.request.Request(url, headers=headers)
    resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
    raw = resp.read(300_000)
    ct = resp.headers.get('Content-Type', '')
    enc = 'utf-8'
    if 'charset=' in ct:
        enc = ct.split('charset=')[-1].split(';')[0].strip()
    try:
        return raw.decode(enc, errors='replace')
    except (UnicodeDecodeError, LookupError):
        return raw.decode('utf-8', errors='replace')

def clean_html(html: str) -> str:
    """Strip tags and condense whitespace."""
    # Remove scripts and styles
    html = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove tags
    html = re.sub(r'<[^>]+>', ' ', html)
    # Decode entities
    html = html.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>') \
               .replace('&nbsp;', ' ').replace('&#39;', "'").replace('&quot;', '"')
    # Collapse whitespace
    html = re.sub(r'\s+', ' ', html).strip()
    return html[:8000]  # Max 8KB of clean text

def fetch_business(place: dict) -> dict:
    website = place.get('website', '')
    if not website:
        return {'name': place['name'], 'content': None, 'error': 'no_website'}
    if not website.startswith('http'):
        website = 'https://' + website

    try:
        html = fetch_page(website)
        text = clean_html(html)

        # Also try /about if content is thin
        if len(text) < 500:
            parsed = urlparse(website)
            base = f"{parsed.scheme}://{parsed.netloc}"
            for path in ['/about', '/about-us', '/our-firm', '/our-team']:
                try:
                    html2 = fetch_page(base + path, timeout=8)
                    text2 = clean_html(html2)
                    if len(text2) > len(text):
                        text = text2
                    break
                except:
                    continue

        return {
            'name': place['name'],
            'website': website,
            'content': text,
            'error': None,
        }
    except Exception as e:
        return {'name': place['name'], 'website': website, 'content': None, 'error': str(e)[:100]}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--vertical', required=True)
    parser.add_argument('--city', required=True)
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--workers', type=int, default=15)
    args = parser.parse_args()

    places_path = DATA_DIR / args.vertical / args.city / 'places.json'
    if not places_path.exists():
        print(f"ERROR: {places_path} not found")
        sys.exit(1)

    with open(places_path) as f:
        places = json.load(f)

    # Top unenriched by weighted score
    candidates = [p for p in places if not p.get('enriched') and p.get('website')]
    candidates.sort(key=lambda p: (p.get('rating', 0) * (p.get('review_count', 0) ** 0.5)), reverse=True)
    batch = candidates[:args.limit]

    print(f"\n🎯 {args.vertical.upper()} / {args.city} — fetching {len(batch)} businesses...")

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(fetch_business, p): p for p in batch}
        done = 0
        for future in as_completed(futures):
            r = future.result()
            place = futures[future]
            r['id'] = place.get('id')
            r['address'] = place.get('address')
            r['rating'] = place.get('rating')
            r['review_count'] = place.get('review_count')
            r['phone'] = place.get('phone')
            results.append(r)
            done += 1
            status = "✅" if r['content'] else "❌"
            if done % 10 == 0 or done == len(batch):
                ok = sum(1 for r in results if r['content'])
                print(f"  [{done}/{len(batch)}] fetched: {ok} with content")

    # Save
    out_path = TMP_DIR / f"{args.vertical}_{args.city}.json"
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    ok = sum(1 for r in results if r['content'])
    print(f"\n✅ Saved {ok}/{len(batch)} with content → {out_path}")

if __name__ == '__main__':
    main()
