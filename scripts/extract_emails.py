#!/usr/bin/env python3
"""
Email extraction pass for enriched businesses.
Fetches each business website and looks for email addresses.
"""

import json
import os
import re
import time
import urllib.request
import urllib.error
import ssl
import gzip
from html.parser import HTMLParser

BASE = "/Users/daniel/Library/Mobile Documents/com~apple~CloudDocs/Discovery World/data_v2"

# Order: attorneys, dentists, gyms, therapists, restaurants (sample 30/city)
VERTICALS_ORDER = ["attorneys", "dentists", "gyms", "therapists", "restaurants"]
RESTAURANT_SAMPLE = 30

# Email regex - captures common patterns
EMAIL_RE = re.compile(
    r'\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b'
)

# Patterns to exclude (images, tracking, etc.)
EMAIL_EXCLUDE = re.compile(
    r'\.(png|jpg|jpeg|gif|svg|webp|pdf|zip|mp4|mp3)$'
    r'|@(example|domain|email|yourname|sentry|wix|squarespace|wordpress|godaddy'
    r'|amazonaws|cloudflare|googlemail|mailchimp|sendgrid|klaviyo|hubspot'
    r'|zendesk|intercom|freshdesk|mailgun|postmark|sparkpost|mandrill'
    r'|outlook|office365|sharepoint|livemail|hotmail|yahoo|gmail'  # generic providers often not biz email
    r')',
    re.IGNORECASE
)

# But always keep if it's the biz domain
GENERIC_PROVIDERS = re.compile(
    r'@(gmail|yahoo|hotmail|outlook|live|icloud|aol|protonmail|mail)\.',
    re.IGNORECASE
)

def fetch_url(url, timeout=12):
    """Fetch URL, return text or None."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,*/*',
                'Accept-Encoding': 'gzip, deflate',
            }
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
            enc = resp.headers.get('Content-Encoding', '')
            if enc == 'gzip':
                raw = gzip.decompress(raw)
            charset = 'utf-8'
            ct = resp.headers.get('Content-Type', '')
            m = re.search(r'charset=([^\s;]+)', ct)
            if m:
                charset = m.group(1).strip('"\'')
            return raw.decode(charset, errors='replace')
    except Exception:
        return None

def extract_emails_from_html(html, business_domain=None):
    """Extract valid emails from HTML content."""
    if not html:
        return [], None

    # Also decode HTML entities
    html = html.replace('&#64;', '@').replace('%40', '@')

    all_emails = EMAIL_RE.findall(html)

    good_emails = []
    for em in all_emails:
        em = em.lower().strip('.,;:')
        # Skip obvious junk
        if EMAIL_EXCLUDE.search(em):
            continue
        # Skip emails with multiple consecutive dots
        if '..' in em:
            continue
        # Skip very long local parts (likely tracking)
        local, domain = em.rsplit('@', 1)
        if len(local) > 64 or len(domain) > 255:
            continue
        # Skip noreply/support/etc unless it's the only one
        if re.match(r'^(noreply|no-reply|donotreply|bounce|mailer-daemon)$', local):
            continue
        good_emails.append(em)

    # Deduplicate preserving order
    seen = set()
    unique = []
    for e in good_emails:
        if e not in seen:
            seen.add(e)
            unique.append(e)

    # Prioritize: contact/info/office/hello over generic providers
    def email_priority(em):
        local = em.split('@')[0]
        if re.match(r'^(contact|info|office|hello|hi|team|appointments?|booking|reception|admin|support|inquir|query|queries|ask|mail|email)$', local):
            return 0
        if not GENERIC_PROVIDERS.search(em):
            return 1  # domain email
        return 2  # generic provider

    unique.sort(key=email_priority)

    # Look for booking/contact form URLs
    booking_url = None
    booking_patterns = re.compile(
        r'href=["\']([^"\']*(?:book|appointment|schedule|calendly|acuity|zocdoc|opentable|resy|tock|yelp.*biz|contact)[^"\']*)["\']',
        re.IGNORECASE
    )
    bm = booking_patterns.search(html)
    if bm:
        raw_url = bm.group(1)
        # Make absolute if relative
        if raw_url.startswith('http'):
            booking_url = raw_url

    return unique[:5], booking_url  # cap at 5 emails

def also_try_contact_page(base_url, timeout=10):
    """Try /contact, /contact-us, /about pages for email."""
    for suffix in ['/contact', '/contact-us', '/contact.html', '/about']:
        url = base_url.rstrip('/') + suffix
        html = fetch_url(url, timeout=timeout)
        if html:
            emails, _ = extract_emails_from_html(html)
            if emails:
                return emails, html
    return [], None

def process_city(vertical, city, data, restaurant_sample=None):
    """Process one city's places.json, return updated data and stats."""
    needs_email = []
    for i, place in enumerate(data):
        if place.get('enriched') == True and place.get('website') and not place.get('email'):
            needs_email.append((i, place))

    # For restaurants, sample
    if restaurant_sample and len(needs_email) > restaurant_sample:
        needs_email = needs_email[:restaurant_sample]

    found_count = 0
    booking_count = 0

    for idx, (data_idx, place) in enumerate(needs_email):
        website = place['website']
        if not website.startswith('http'):
            website = 'https://' + website

        print(f"  [{idx+1}/{len(needs_email)}] {place['name'][:50]}", end=' ... ', flush=True)

        html = fetch_url(website)
        emails, booking_url = extract_emails_from_html(html)

        # If no email found on homepage, try contact page
        if not emails:
            emails, contact_html = also_try_contact_page(website)
            if not emails and contact_html:
                emails, _ = extract_emails_from_html(contact_html)

        if emails:
            data[data_idx]['email'] = emails[0]
            found_count += 1
            print(f"EMAIL: {emails[0]}")
        else:
            print("no email")

        if booking_url and not data[data_idx].get('booking_url'):
            data[data_idx]['booking_url'] = booking_url
            booking_count += 1

        # Brief pause to be polite
        time.sleep(0.3)

    return data, found_count, len(needs_email), booking_count

def main():
    stats = {}

    for vertical in VERTICALS_ORDER:
        v_path = f"{BASE}/{vertical}"
        if not os.path.isdir(v_path):
            print(f"[SKIP] {vertical} - no directory")
            continue

        cities = sorted(os.listdir(v_path))
        v_found = 0
        v_total = 0

        for city in cities:
            path = f"{v_path}/{city}/places.json"
            if not os.path.exists(path):
                continue

            with open(path) as f:
                data = json.load(f)

            # Count how many need email
            needs = [p for p in data if p.get('enriched') == True and p.get('website') and not p.get('email')]
            if not needs:
                print(f"[SKIP] {vertical}/{city} - no emails needed")
                continue

            is_restaurant = (vertical == 'restaurants')
            print(f"\n[START] {vertical}/{city} - {len(needs)} businesses need email")

            data, found, total, booking = process_city(
                vertical, city, data,
                restaurant_sample=RESTAURANT_SAMPLE if is_restaurant else None
            )

            v_found += found
            v_total += total

            # Write back
            with open(path, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"  => Saved {vertical}/{city}: {found}/{total} emails found, {booking} booking URLs")

        stats[vertical] = {'found': v_found, 'total': v_total}
        print(f"\n=== {vertical} DONE: {v_found}/{v_total} emails found ===\n")

    print("\n\n=== FINAL SUMMARY ===")
    grand_found = 0
    grand_total = 0
    for v, s in stats.items():
        pct = round(100*s['found']/s['total']) if s['total'] else 0
        print(f"  {v}: {s['found']}/{s['total']} ({pct}%)")
        grand_found += s['found']
        grand_total += s['total']
    print(f"\n  TOTAL: {grand_found}/{grand_total} ({round(100*grand_found/grand_total) if grand_total else 0}%)")

if __name__ == '__main__':
    main()
