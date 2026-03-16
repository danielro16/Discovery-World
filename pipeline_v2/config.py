"""
Pipeline V2 Configuration — Multi-source, TOS-compliant.
No Google API keys needed. Uses OSM + public records.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# API Keys (only Anthropic needed for enrichment)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Paths — V2 uses separate data directory to preserve legacy data
DATA_DIR = PROJECT_ROOT / "data_v2"
LEGACY_DATA_DIR = PROJECT_ROOT / "data"
VERTICALS_DIR = PROJECT_ROOT / "verticals"  # shared with v1

# Site config
SITE_NAME = os.getenv("SITE_NAME", "AgentReady")
SITE_DOMAIN = os.getenv("SITE_DOMAIN", "https://agentready.com")

# Claude API
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# --- Source configuration ---

# OSM Overpass API
# ⚠️  Public instance is for development/testing only.
#     For production, self-host Overpass or use planet.osm extracts.
OVERPASS_URL = os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
OVERPASS_RATE_LIMIT = 2.0  # seconds between requests (be respectful)

# City coordinates (shared with v1, no Google dependency)
CITY_COORDS = {
    # Florida
    "miami, fl": {"lat": 25.7617, "lng": -80.1918},
    "miami beach, fl": {"lat": 25.7907, "lng": -80.1300},
    "orlando, fl": {"lat": 28.5383, "lng": -81.3792},
    "tampa, fl": {"lat": 27.9506, "lng": -82.4572},
    # California
    "los angeles, ca": {"lat": 34.0522, "lng": -118.2437},
    "san francisco, ca": {"lat": 37.7749, "lng": -122.4194},
    "san jose, ca": {"lat": 37.3382, "lng": -121.8863},
    "san diego, ca": {"lat": 32.7157, "lng": -117.1611},
    # Texas
    "houston, tx": {"lat": 29.7604, "lng": -95.3698},
    "dallas, tx": {"lat": 32.7767, "lng": -96.7970},
    "austin, tx": {"lat": 30.2672, "lng": -97.7431},
    # Northeast
    "new york, ny": {"lat": 40.7128, "lng": -74.0060},
    "boston, ma": {"lat": 42.3601, "lng": -71.0589},
    "washington, dc": {"lat": 38.9072, "lng": -77.0369},
    # Midwest
    "chicago, il": {"lat": 41.8781, "lng": -87.6298},
    # Pacific Northwest
    "seattle, wa": {"lat": 47.6062, "lng": -122.3321},
    # Mountain
    "denver, co": {"lat": 39.7392, "lng": -104.9903},
}

# OSM tag mapping: vertical -> OSM tags to query
# See https://wiki.openstreetmap.org/wiki/Map_features
OSM_TAGS = {
    "dentists": [
        {"amenity": "dentist"},
        {"healthcare": "dentist"},
        {"healthcare:speciality": "orthodontics"},
    ],
    "restaurants": [
        {"amenity": "restaurant"},
        {"amenity": "fast_food"},
        {"amenity": "cafe"},
    ],
    "gyms": [
        {"leisure": "fitness_centre"},
        {"leisure": "sports_centre"},
        {"sport": "fitness"},
    ],
    "attorneys": [
        {"office": "lawyer"},
        {"office": "attorney"},
    ],
    "therapists": [
        {"healthcare": "psychotherapist"},
        {"healthcare": "counselling"},
        {"healthcare:speciality": "psychiatry"},
        {"office": "therapist"},
    ],
}

# Public records sources by state (for regulated professions)
# Format: { state_abbrev: { vertical: { url, type, notes } } }
PUBLIC_RECORDS_SOURCES = {
    "FL": {
        "dentists": {
            "url": "https://mqa-internet.doh.state.fl.us/MQASearchServices/HealthCareProviders",
            "type": "api_search",
            "board": "Dentistry",
            "notes": "Florida DOH MQA — public record, no explicit commercial restriction",
        },
        "attorneys": {
            "url": "https://www.floridabar.org/directories/find-mbr/",
            "type": "web_search",
            "notes": "Florida Bar — verify TOS before scraping, consider FOIA",
        },
        "therapists": {
            "url": "https://mqa-internet.doh.state.fl.us/MQASearchServices/HealthCareProviders",
            "type": "api_search",
            "board": "Clinical Social Work, Marriage & Family Therapy, and Mental Health Counseling",
            "notes": "Florida DOH MQA",
        },
    },
    "TX": {
        "dentists": {
            "url": "https://tsbde.texas.gov/resources/public-license-search/",
            "type": "web_search",
            "notes": "Texas SBDE — public record",
        },
        "therapists": {
            "url": "https://www.bhec.texas.gov/verify-a-license/index.html",
            "type": "csv_download",
            "csv_urls": {
                "LPC": "https://www.bhec.texas.gov/sites/default/files/LPC.csv",
                "MFT": "https://www.bhec.texas.gov/sites/default/files/MFT.csv",
                "PSY": "https://www.bhec.texas.gov/sites/default/files/PSY.csv",
                "SW": "https://www.bhec.texas.gov/sites/default/files/SW.csv",
            },
            "notes": "Texas BHEC — CSV downloads updated daily, no address included",
        },
    },
    "CA": {
        "dentists": {
            "url": "https://search.dca.ca.gov/",
            "type": "web_search",
            "board": "Dental Board of California",
            "notes": "California DCA — verify TOS, consider public records request",
        },
    },
    "NY": {
        "dentists": {
            "url": "https://eservices.nysed.gov/professions/verification-search",
            "type": "web_search",
            "notes": "NYSED Office of Professions — covers all licensed professions",
        },
        "therapists": {
            "url": "https://eservices.nysed.gov/professions/verification-search",
            "type": "web_search",
            "notes": "NYSED — social work, mental health counselors",
        },
    },
}

# Map city to state abbreviation
CITY_TO_STATE = {
    "miami, fl": "FL",
    "miami beach, fl": "FL",
    "orlando, fl": "FL",
    "tampa, fl": "FL",
    "los angeles, ca": "CA",
    "san francisco, ca": "CA",
    "san jose, ca": "CA",
    "san diego, ca": "CA",
    "houston, tx": "TX",
    "dallas, tx": "TX",
    "austin, tx": "TX",
    "new york, ny": "NY",
    "boston, ma": "MA",
    "washington, dc": "DC",
    "chicago, il": "IL",
    "seattle, wa": "WA",
    "denver, co": "CO",
}


# --- Shared utilities (from v1) ---

def load_vertical(vertical_name: str) -> dict:
    """Load a vertical configuration by name."""
    config_path = VERTICALS_DIR / f"{vertical_name}.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Vertical config not found: {config_path}")
    with open(config_path) as f:
        return json.load(f)


def get_data_path(vertical: str, city: str) -> Path:
    """Get the data directory for a vertical+city combo (V2)."""
    city_slug = city.lower().replace(" ", "_").replace(",", "")
    path = DATA_DIR / vertical / city_slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_verticals() -> list[str]:
    """List all available vertical names."""
    return [f.stem for f in VERTICALS_DIR.glob("*.json")]


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def get_city_coords(city: str) -> dict:
    """Get coordinates for a city. Returns {'lat': ..., 'lng': ...}."""
    city_lower = city.lower().strip()
    if city_lower in CITY_COORDS:
        return CITY_COORDS[city_lower]
    raise ValueError(f"City '{city}' not in CITY_COORDS. Add it to config.py")


def get_state(city: str) -> str:
    """Get state abbreviation for a city."""
    city_lower = city.lower().strip()
    if city_lower in CITY_TO_STATE:
        return CITY_TO_STATE[city_lower]
    # Try to extract from city string (e.g., "Miami, FL" -> "FL")
    parts = city.split(",")
    if len(parts) == 2:
        return parts[1].strip().upper()
    raise ValueError(f"Cannot determine state for '{city}'")
