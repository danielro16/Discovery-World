"""
Shared configuration for the AgentReady pipeline.
Loads environment variables and vertical configs.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# API Keys
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Paths
DATA_DIR = PROJECT_ROOT / "data"
VERTICALS_DIR = PROJECT_ROOT / "verticals"
SITE_DIR = PROJECT_ROOT / "site"
TEMPLATES_DIR = PROJECT_ROOT / "templates"

# Site config
SITE_NAME = os.getenv("SITE_NAME", "AgentReady")
SITE_DOMAIN = os.getenv("SITE_DOMAIN", "https://agentready.com")

# Google Places API
GOOGLE_PLACES_BASE_URL = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places"

# Claude API
CLAUDE_MODEL = "claude-sonnet-4-20250514"


def load_vertical(vertical_name: str) -> dict:
    """Load a vertical configuration by name."""
    config_path = VERTICALS_DIR / f"{vertical_name}.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Vertical config not found: {config_path}")
    with open(config_path) as f:
        return json.load(f)


def get_data_path(vertical: str, city: str) -> Path:
    """Get the data directory for a vertical+city combo."""
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
