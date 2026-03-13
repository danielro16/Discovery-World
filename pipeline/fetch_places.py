"""
fetch_places.py — Fetches business data from Google Places API (New).

Usage:
    python pipeline/fetch_places.py --vertical dentists --city "Miami, FL" --radius 30000
    python pipeline/fetch_places.py --vertical restaurants --city "Miami, FL" --radius 20000

This script:
1. Reads the vertical config for search queries
2. Searches Google Places API for matching businesses
3. Fetches detailed info for each business
4. Saves structured JSON to data/{vertical}/{city}/
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import requests
from rich.console import Console
from rich.progress import track

from config import (
    GOOGLE_PLACES_API_KEY,
    load_vertical,
    get_data_path,
    slugify,
)

console = Console()


def search_places(query: str, location: str, radius: int, page_token: str = None) -> dict:
    """Search for places using Google Places API (New) Text Search."""
    url = "https://places.googleapis.com/v1/places:searchText"
    
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,"
            "places.location,places.rating,places.userRatingCount,"
            "places.websiteUri,places.nationalPhoneNumber,"
            "places.currentOpeningHours,places.regularOpeningHours,"
            "places.businessStatus,places.priceLevel,"
            "places.googleMapsUri,places.types,"
            "places.reviews,places.photos,"
            "nextPageToken"
        ),
    }
    
    body = {
        "textQuery": f"{query} in {location}",
        "maxResultCount": 20,
    }
    
    if radius:
        # Use location bias with the city center
        body["locationBias"] = {
            "circle": {
                "center": get_city_coordinates(location),
                "radius": float(radius),
            }
        }
    
    if page_token:
        body["pageToken"] = page_token
    
    response = requests.post(url, headers=headers, json=body)
    
    if response.status_code != 200:
        console.print(f"[red]API Error {response.status_code}: {response.text}[/red]")
        return {"places": []}
    
    return response.json()


def get_city_coordinates(city: str) -> dict:
    """Get coordinates for a city using Google Geocoding via Places."""
    # Common city coordinates (expand as needed)
    coords = {
        "miami, fl": {"latitude": 25.7617, "longitude": -80.1918},
        "los angeles, ca": {"latitude": 34.0522, "longitude": -118.2437},
        "new york, ny": {"latitude": 40.7128, "longitude": -74.0060},
        "houston, tx": {"latitude": 29.7604, "longitude": -95.3698},
        "chicago, il": {"latitude": 41.8781, "longitude": -87.6298},
        "dallas, tx": {"latitude": 32.7767, "longitude": -96.7970},
        "phoenix, az": {"latitude": 33.4484, "longitude": -112.0740},
        "san francisco, ca": {"latitude": 37.7749, "longitude": -122.4194},
        "seattle, wa": {"latitude": 47.6062, "longitude": -122.3321},
        "boston, ma": {"latitude": 42.3601, "longitude": -71.0589},
        "denver, co": {"latitude": 39.7392, "longitude": -104.9903},
        "atlanta, ga": {"latitude": 33.7490, "longitude": -84.3880},
        "san diego, ca": {"latitude": 32.7157, "longitude": -117.1611},
        "austin, tx": {"latitude": 30.2672, "longitude": -97.7431},
    }
    
    city_lower = city.lower().strip()
    if city_lower in coords:
        return coords[city_lower]
    
    # Fallback: use Geocoding API
    console.print(f"[yellow]City '{city}' not in cache, using default Miami coords[/yellow]")
    return {"latitude": 25.7617, "longitude": -80.1918}


def parse_place(place: dict) -> dict:
    """Parse a Google Places API result into our standard schema."""
    
    # Extract reviews
    reviews = []
    for review in place.get("reviews", []):
        reviews.append({
            "rating": review.get("rating"),
            "text": review.get("text", {}).get("text", ""),
            "time": review.get("publishTime", ""),
            "author": review.get("authorAttribution", {}).get("displayName", ""),
        })
    
    # Extract opening hours
    hours = {}
    regular_hours = place.get("regularOpeningHours", {})
    if regular_hours:
        for period in regular_hours.get("periods", []):
            day = period.get("open", {}).get("day", 0)
            day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
            day_name = day_names[day] if day < 7 else f"Day {day}"
            open_time = f"{period.get('open', {}).get('hour', 0):02d}:{period.get('open', {}).get('minute', 0):02d}"
            close_time = f"{period.get('close', {}).get('hour', 0):02d}:{period.get('close', {}).get('minute', 0):02d}"
            hours[day_name] = f"{open_time} - {close_time}"
    
    # Extract photo references
    photos = []
    for photo in place.get("photos", [])[:5]:
        photos.append({
            "name": photo.get("name", ""),
            "width": photo.get("widthPx"),
            "height": photo.get("heightPx"),
        })
    
    return {
        "id": place.get("id", ""),
        "name": place.get("displayName", {}).get("text", ""),
        "address": place.get("formattedAddress", ""),
        "location": {
            "lat": place.get("location", {}).get("latitude"),
            "lng": place.get("location", {}).get("longitude"),
        },
        "phone": place.get("nationalPhoneNumber", ""),
        "website": place.get("websiteUri", ""),
        "google_maps_url": place.get("googleMapsUri", ""),
        "rating": place.get("rating"),
        "review_count": place.get("userRatingCount", 0),
        "business_status": place.get("businessStatus", ""),
        "price_level": place.get("priceLevel", ""),
        "types": place.get("types", []),
        "hours": hours,
        "reviews": reviews,
        "photos": photos,
        # These will be filled by enrich_data.py
        "enriched": False,
        "enriched_data": {},
        "profile_completeness": 0,
        "claimed": False,
    }


def calculate_completeness(place: dict) -> int:
    """Calculate profile completeness score (0-100)."""
    score = 0
    checks = [
        ("name", 10),
        ("address", 10),
        ("phone", 10),
        ("website", 10),
        ("rating", 5),
        ("review_count", 5),
        ("hours", 15),
        ("reviews", 10),
        ("photos", 10),
    ]
    for field, points in checks:
        value = place.get(field)
        if value and value != {} and value != [] and value != 0:
            score += points
    
    # Enriched data adds more
    if place.get("enriched"):
        score += 15
    
    return min(score, 100)


def fetch_vertical(vertical_name: str, city: str, radius: int):
    """Fetch all businesses for a vertical in a city."""
    
    if not GOOGLE_PLACES_API_KEY:
        console.print("[red]ERROR: GOOGLE_PLACES_API_KEY not set in .env[/red]")
        console.print("Get your key at: https://console.cloud.google.com/apis/credentials")
        return
    
    vertical = load_vertical(vertical_name)
    data_path = get_data_path(vertical_name, city)
    
    console.print(f"\n[bold cyan]🔍 Fetching {vertical['display_name']} in {city}[/bold cyan]")
    console.print(f"   Search queries: {len(vertical['search_queries'])}")
    console.print(f"   Radius: {radius}m")
    console.print(f"   Saving to: {data_path}\n")
    
    all_places = {}
    
    for query in track(vertical["search_queries"], description="Searching..."):
        result = search_places(query, city, radius)
        places = result.get("places", [])
        
        for place in places:
            parsed = parse_place(place)
            if parsed["id"] and parsed["id"] not in all_places:
                parsed["profile_completeness"] = calculate_completeness(parsed)
                all_places[parsed["id"]] = parsed
        
        # Respect rate limits
        time.sleep(0.5)
        
        # Handle pagination
        next_token = result.get("nextPageToken")
        while next_token:
            time.sleep(1.5)  # Required delay for page tokens
            result = search_places(query, city, radius, next_token)
            places = result.get("places", [])
            for place in places:
                parsed = parse_place(place)
                if parsed["id"] and parsed["id"] not in all_places:
                    parsed["profile_completeness"] = calculate_completeness(parsed)
                    all_places[parsed["id"]] = parsed
            next_token = result.get("nextPageToken")
    
    # Save results
    places_list = list(all_places.values())
    
    # Sort by rating * review_count (weighted relevance)
    places_list.sort(
        key=lambda x: (x.get("rating") or 0) * (x.get("review_count") or 0),
        reverse=True
    )
    
    output_file = data_path / "places.json"
    with open(output_file, "w") as f:
        json.dump(places_list, f, indent=2, ensure_ascii=False)
    
    # Save summary stats
    stats = {
        "vertical": vertical_name,
        "city": city,
        "total_places": len(places_list),
        "with_website": len([p for p in places_list if p.get("website")]),
        "with_phone": len([p for p in places_list if p.get("phone")]),
        "avg_rating": round(
            sum(p.get("rating") or 0 for p in places_list) / max(len(places_list), 1), 2
        ),
        "avg_reviews": round(
            sum(p.get("review_count") or 0 for p in places_list) / max(len(places_list), 1), 1
        ),
    }
    
    stats_file = data_path / "stats.json"
    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=2)
    
    console.print(f"\n[bold green]✅ Done![/bold green]")
    console.print(f"   Total businesses found: [bold]{len(places_list)}[/bold]")
    console.print(f"   With website: {stats['with_website']}")
    console.print(f"   With phone: {stats['with_phone']}")
    console.print(f"   Avg rating: {stats['avg_rating']} ⭐")
    console.print(f"   Avg reviews: {stats['avg_reviews']}")
    console.print(f"   Saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Fetch businesses from Google Places API")
    parser.add_argument("--vertical", required=True, help="Vertical name (e.g., dentists)")
    parser.add_argument("--city", required=True, help="City name (e.g., 'Miami, FL')")
    parser.add_argument("--radius", type=int, default=30000, help="Search radius in meters (default: 30000)")
    
    args = parser.parse_args()
    fetch_vertical(args.vertical, args.city, args.radius)


if __name__ == "__main__":
    main()
