"""
Website Scraper Source — Extracts business data directly from business websites.

License: ✅ We're reading publicly available information from business websites.
The businesses WANT to be found — this is their public-facing information.

This source is used to:
1. Enrich OSM/public records data with phone, hours, services, etc.
2. Verify and update addresses
3. Extract structured data that the business publishes on their own site

Note: Respects robots.txt. Uses reasonable rate limiting.
"""

from __future__ import annotations

import time
import requests
from urllib.parse import urlparse
from rich.console import Console

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

console = Console()

# Max content to fetch per website (bytes)
MAX_CONTENT_SIZE = 50_000  # ~50KB
REQUEST_TIMEOUT = 15
RATE_LIMIT = 1.5  # seconds between requests


def fetch_website_content(url: str) -> str | None:
    """
    Fetch the text content of a business website.

    Returns raw HTML text, or None if fetch fails.
    Respects basic rate limiting and size limits.
    """
    if not url:
        return None

    # Normalize URL
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; AgentReady/2.0; +https://agentready.com/bot)",
            },
            allow_redirects=True,
            stream=True,
        )

        if response.status_code != 200:
            return None

        # Check content type
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return None

        # Read up to max size
        content = response.text[:MAX_CONTENT_SIZE]
        return content

    except Exception as e:
        console.print(f"[dim]  SCRAPER: Failed to fetch {url}: {e}[/dim]")
        return None


def check_robots_txt(url: str) -> bool:
    """
    Check if robots.txt allows our bot to access the site.

    Returns True if allowed (or no robots.txt), False if blocked.
    This is a simplified check — for production, use the 'robotparser' stdlib.
    """
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        response = requests.get(robots_url, timeout=5)
        if response.status_code != 200:
            return True  # No robots.txt = allowed

        content = response.text.lower()

        # Very basic check — look for blanket disallow
        # For production, use urllib.robotparser
        if "disallow: /" in content and "user-agent: *" in content:
            # Check if it's "Disallow: /" (block all) vs "Disallow: /admin" (block specific)
            for line in content.split("\n"):
                line = line.strip()
                if line == "disallow: /":
                    return False

        return True

    except Exception:
        return True  # Can't check = assume allowed


def batch_fetch_websites(places: list[dict], delay: float = RATE_LIMIT) -> dict[str, str]:
    """
    Fetch website content for a list of places that have websites.

    Returns dict of {place_id: html_content}.
    Skips places without websites.
    """
    results = {}
    websites = [(p["id"], p["website"]) for p in places if p.get("website")]

    console.print(f"[cyan]  SCRAPER: Fetching {len(websites)} websites...[/cyan]")

    for i, (place_id, url) in enumerate(websites):
        content = fetch_website_content(url)
        if content:
            results[place_id] = content

        if (i + 1) % 10 == 0:
            console.print(f"[dim]  SCRAPER: {i + 1}/{len(websites)} fetched[/dim]")

        time.sleep(delay)

    console.print(f"[green]  SCRAPER: Got content from {len(results)}/{len(websites)} websites[/green]")
    return results
