"""
mcp_server.py — MCP Server for AgentReady (Future Phase)

This exposes your business directory as a Model Context Protocol server
that AI agents can discover and use to find, compare, and interact with
local businesses.

This is the FUTURE layer that turns your directory into agentic infrastructure.
Activate when agent adoption reaches critical mass.

Usage:
    python pipeline/mcp_server.py --port 8080

An agent can then:
    - Search for businesses by criteria
    - Get detailed business profiles
    - Check availability (when connected to booking systems)
    - Compare businesses side by side
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# ── MCP Server skeleton ──
# When ready to activate, install: pip install mcp
# For now, this serves as the architectural blueprint

# The tools this MCP server will expose:

MCP_TOOLS = [
    {
        "name": "search_businesses",
        "description": "Search for local businesses by type, location, and criteria. Returns structured data including ratings, reviews, services, insurance accepted, languages, and more.",
        "parameters": {
            "type": "object",
            "properties": {
                "vertical": {
                    "type": "string",
                    "description": "Business type: dentists, restaurants, gyms, attorneys, therapists",
                    "enum": ["dentists", "restaurants", "gyms", "attorneys", "therapists"],
                },
                "city": {
                    "type": "string",
                    "description": "City to search in (e.g., 'Miami, FL')",
                },
                "specialty": {
                    "type": "string",
                    "description": "Specific specialty or service (e.g., 'implants', 'immigration law', 'yoga')",
                },
                "insurance": {
                    "type": "string",
                    "description": "Insurance plan name (for healthcare verticals)",
                },
                "language": {
                    "type": "string",
                    "description": "Language spoken by staff",
                },
                "min_rating": {
                    "type": "number",
                    "description": "Minimum rating (1-5)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default 5)",
                    "default": 5,
                },
            },
            "required": ["vertical", "city"],
        },
    },
    {
        "name": "get_business_profile",
        "description": "Get the complete profile of a specific business including all services, insurance, hours, reviews, and contact information.",
        "parameters": {
            "type": "object",
            "properties": {
                "business_id": {
                    "type": "string",
                    "description": "The unique business ID",
                },
            },
            "required": ["business_id"],
        },
    },
    {
        "name": "compare_businesses",
        "description": "Compare two or more businesses side by side on key metrics.",
        "parameters": {
            "type": "object",
            "properties": {
                "business_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of business IDs to compare",
                },
                "criteria": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "What to compare (e.g., ['rating', 'insurance', 'price'])",
                },
            },
            "required": ["business_ids"],
        },
    },
    {
        "name": "check_availability",
        "description": "Check if a business is currently open and if they have availability (for businesses with connected booking systems).",
        "parameters": {
            "type": "object",
            "properties": {
                "business_id": {
                    "type": "string",
                    "description": "The unique business ID",
                },
                "date": {
                    "type": "string",
                    "description": "Date to check (YYYY-MM-DD format)",
                },
                "service": {
                    "type": "string",
                    "description": "Specific service to book (e.g., 'cleaning', 'consultation')",
                },
            },
            "required": ["business_id"],
        },
    },
]


def search_businesses(vertical: str, city: str, **filters) -> list:
    """
    Search the business database with filters.
    This is the core function that agents will call.
    """
    from config import get_data_path
    
    city_slug = city.lower().replace(" ", "_").replace(",", "")
    data_path = get_data_path(vertical, city_slug)
    places_file = data_path / "places.json"
    
    if not places_file.exists():
        return []
    
    with open(places_file) as f:
        places = json.load(f)
    
    results = places
    
    # Apply filters
    if filters.get("specialty"):
        specialty = filters["specialty"].lower()
        results = [
            p for p in results
            if specialty in str(p.get("enriched_data", {})).lower()
        ]
    
    if filters.get("insurance"):
        insurance = filters["insurance"].lower()
        results = [
            p for p in results
            if insurance in str(
                p.get("enriched_data", {}).get("insurance_accepted", [])
            ).lower()
        ]
    
    if filters.get("language"):
        language = filters["language"].lower()
        results = [
            p for p in results
            if language in str(
                p.get("enriched_data", {}).get("languages", [])
            ).lower()
        ]
    
    if filters.get("min_rating"):
        results = [
            p for p in results
            if (p.get("rating") or 0) >= filters["min_rating"]
        ]
    
    # Sort by relevance score
    import math
    results.sort(
        key=lambda x: (
            (x.get("rating") or 0) * math.log(max(x.get("review_count", 1), 1))
            + (10 if x.get("enriched") else 0)
            + (5 if x.get("claimed") else 0)
        ),
        reverse=True,
    )
    
    max_results = filters.get("max_results", 5)
    
    # Return clean, structured data for the agent
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "address": p["address"],
            "phone": p.get("phone"),
            "website": p.get("website"),
            "rating": p.get("rating"),
            "review_count": p.get("review_count"),
            "specialties": p.get("enriched_data", {}).get("specialties", []),
            "insurance_accepted": p.get("enriched_data", {}).get("insurance_accepted", []),
            "languages": p.get("enriched_data", {}).get("languages", []),
            "hours": p.get("hours", {}),
            "review_summary": p.get("review_analysis", {}).get("summary", ""),
            "profile_completeness": p.get("profile_completeness", 0),
            "verified": p.get("claimed", False),
        }
        for p in results[:max_results]
    ]


def get_business_profile(business_id: str) -> dict:
    """Get complete profile for a business."""
    from config import DATA_DIR
    
    # Search across all verticals and cities
    for vertical_dir in DATA_DIR.iterdir():
        if not vertical_dir.is_dir():
            continue
        for city_dir in vertical_dir.iterdir():
            if not city_dir.is_dir():
                continue
            places_file = city_dir / "places.json"
            if not places_file.exists():
                continue
            with open(places_file) as f:
                places = json.load(f)
            for place in places:
                if place["id"] == business_id:
                    return place
    
    return {"error": "Business not found"}


# ── Print tool definitions for reference ──
if __name__ == "__main__":
    print("=" * 60)
    print("  AgentReady MCP Server — Tool Definitions")
    print("=" * 60)
    print()
    print("These tools will be exposed via MCP when the server is activated.")
    print("For now, the business data and search logic are ready.")
    print()
    
    for tool in MCP_TOOLS:
        print(f"  🔧 {tool['name']}")
        print(f"     {tool['description'][:80]}...")
        params = tool["parameters"]["properties"]
        required = tool["parameters"].get("required", [])
        for param, details in params.items():
            req = " (required)" if param in required else ""
            print(f"     - {param}: {details['type']}{req}")
        print()
    
    print("=" * 60)
    print("  To activate: pip install mcp && python pipeline/mcp_server.py")
    print("=" * 60)
