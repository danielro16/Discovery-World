#!/usr/bin/env python3
"""Scrape emails from business websites and save to places.json files."""
import json
import re
import sys
import time
import urllib.request
import urllib.error
import ssl
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin

# Email regex pattern - matches common email formats
EMAIL_PATTERN = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE
)

# Common junk emails to exclude
JUNK_EMAILS = {
    'example@example.com', 'email@example.com', 'your@email.com',
    'name@domain.com', 'info@example.com', 'test@test.com',
    'username@domain.com', 'user@example.com', 'email@domain.com',
    'yourname@email.com', 'someone@example.com', 'support@wix.com',
    'noreply@squarespace.com', 'noreply@wordpress.com',
}

# File extensions to ignore in email-like patterns
JUNK_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js',
    '.woff', '.woff2', '.ttf', '.eot', '.ico', '.pdf', '.zip',
    '.map', '.json', '.xml', '.html', '.htm', '.php', '.asp',
}

# Common contact page paths to also check
CONTACT_PATHS = ['/contact', '/contact-us', '/contacto', '/about', '/about-us']


def is_valid_email(email: str) -> bool:
    """Check if an email looks legit (not junk/image/file)."""
    email = email.lower().strip()
    if email in JUNK_EMAILS:
        return False
    # Check for file extensions masquerading as emails
    for ext in JUNK_EXTENSIONS:
        if email.endswith(ext):
            return False
    # Must have reasonable length
    if len(email) < 6 or len(email) > 80:
        return False
    # Domain must have at least one dot after @
    parts = email.split('@')
    if len(parts) != 2:
        return False
    domain = parts[1]
    if '.' not in domain or domain.startswith('.') or domain.endswith('.'):
        return False
    # Skip if domain looks like a placeholder
    if domain in ('domain.com', 'email.com', 'example.com', 'test.com', 'yoursite.com'):
        return False
    return True


def fetch_page(url: str, timeout: int = 10) -> str:
    """Fetch a web page and return its text content."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    req = urllib.request.Request(url, headers=headers)
    response = urllib.request.urlopen(req, timeout=timeout, context=ctx)

    # Read and decode
    content_type = response.headers.get('Content-Type', '')
    encoding = 'utf-8'
    if 'charset=' in content_type:
        encoding = content_type.split('charset=')[-1].split(';')[0].strip()

    raw = response.read(500_000)  # Max 500KB
    try:
        return raw.decode(encoding, errors='replace')
    except (UnicodeDecodeError, LookupError):
        return raw.decode('utf-8', errors='replace')


def extract_emails_from_html(html: str) -> set:
    """Extract emails from HTML content."""
    # Also decode HTML entities
    html = html.replace('&#64;', '@').replace('&#46;', '.').replace('[at]', '@').replace('[dot]', '.')

    emails = set()
    for match in EMAIL_PATTERN.findall(html):
        email = match.lower().strip()
        if is_valid_email(email):
            emails.add(email)
    return emails


def scrape_emails_for_place(place: dict) -> dict:
    """Scrape emails from a business website. Returns {name, emails, error}."""
    name = place.get('name', 'Unknown')
    website = place.get('website', '')

    if not website:
        return {'name': name, 'emails': [], 'error': 'no_website'}

    # Normalize URL
    if not website.startswith('http'):
        website = 'https://' + website

    all_emails = set()
    pages_tried = []

    try:
        # 1. Try main page
        html = fetch_page(website)
        all_emails.update(extract_emails_from_html(html))
        pages_tried.append(website)

        # 2. If no emails found, try contact pages
        if not all_emails:
            parsed = urlparse(website)
            base_url = f"{parsed.scheme}://{parsed.netloc}"

            for path in CONTACT_PATHS:
                try:
                    contact_url = base_url + path
                    html = fetch_page(contact_url, timeout=8)
                    all_emails.update(extract_emails_from_html(html))
                    pages_tried.append(contact_url)
                    if all_emails:
                        break  # Found emails, stop
                except:
                    continue

        # 3. Also check for mailto: links specifically
        domain = urlparse(website).netloc.replace('www.', '')

        # Prioritize emails from the business's own domain
        own_domain_emails = {e for e in all_emails if domain in e}

        if own_domain_emails:
            result_emails = sorted(own_domain_emails)
        else:
            result_emails = sorted(all_emails)

        return {
            'name': name,
            'emails': result_emails,
            'error': None,
            'pages_tried': len(pages_tried),
        }

    except Exception as e:
        error_type = type(e).__name__
        return {
            'name': name,
            'emails': list(all_emails),
            'error': f'{error_type}: {str(e)[:100]}',
            'pages_tried': len(pages_tried),
        }


def scrape_emails_for_file(places_path: str, max_workers: int = 10, dry_run: bool = False):
    """Scrape emails for all places in a JSON file."""
    with open(places_path) as f:
        places = json.load(f)

    total = len(places)
    with_website = [p for p in places if p.get('website')]
    already_have_email = [p for p in places if p.get('email')]
    need_scraping = [p for p in with_website if not p.get('email')]

    print(f"\n📂 {places_path}")
    print(f"   Total: {total} | With website: {len(with_website)} | Already have email: {len(already_have_email)} | To scrape: {len(need_scraping)}")

    if not need_scraping:
        print("   ✅ Nothing to scrape!")
        return 0

    if dry_run:
        print("   🔍 Dry run — not scraping")
        return 0

    found_count = 0
    error_count = 0
    results = []

    # Use thread pool for concurrent scraping
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {}
        for place in need_scraping:
            future = executor.submit(scrape_emails_for_place, place)
            future_to_idx[future] = place

        for i, future in enumerate(as_completed(future_to_idx), 1):
            place = future_to_idx[future]
            result = future.result()

            if result['emails']:
                # Save first email (most relevant) to place
                place['email'] = result['emails'][0]
                if len(result['emails']) > 1:
                    place['emails_all'] = result['emails']
                found_count += 1
                status = f"📧 {result['emails'][0]}"
            elif result['error'] == 'no_website':
                status = "⏭️  no website"
            elif result['error']:
                error_count += 1
                status = f"❌ {result['error'][:60]}"
            else:
                status = "🔍 no email found"

            # Progress
            if i % 10 == 0 or i == len(need_scraping):
                print(f"   [{i}/{len(need_scraping)}] Found: {found_count} | Errors: {error_count}")

    # Save updated places
    with open(places_path, 'w') as f:
        json.dump(places, f, indent=2, ensure_ascii=False)

    print(f"   ✅ Done! Found {found_count} emails out of {len(need_scraping)} scraped")
    return found_count


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Scrape emails from business websites')
    parser.add_argument('--vertical', help='Specific vertical (e.g., dentists)')
    parser.add_argument('--city', help='Specific city (e.g., miami_fl)')
    parser.add_argument('--workers', type=int, default=10, help='Concurrent workers (default: 10)')
    parser.add_argument('--dry-run', action='store_true', help='Just show stats, don\'t scrape')
    args = parser.parse_args()

    data_dir = Path(__file__).parent.parent / 'data'

    total_found = 0

    for vertical_dir in sorted(data_dir.iterdir()):
        if not vertical_dir.is_dir() or vertical_dir.name.startswith('.'):
            continue
        if args.vertical and vertical_dir.name != args.vertical:
            continue

        for city_dir in sorted(vertical_dir.iterdir()):
            if not city_dir.is_dir() or city_dir.name.startswith('.'):
                continue
            if args.city and city_dir.name != args.city:
                continue

            places_path = city_dir / 'places.json'
            if places_path.exists():
                found = scrape_emails_for_file(
                    str(places_path),
                    max_workers=args.workers,
                    dry_run=args.dry_run,
                )
                total_found += found

    print(f"\n🎉 Total emails found: {total_found}")


if __name__ == '__main__':
    main()
