"""
generate_content.py — Generates SEO/LLM-optimized blog posts from business data.

Usage:
    python pipeline/generate_content.py --vertical dentists --city miami --count 5
    python pipeline/generate_content.py --vertical restaurants --city miami --count 10

This script:
1. Loads enriched business data
2. Selects content templates from the vertical config
3. Uses Claude API to generate high-quality, data-driven blog posts
4. Outputs markdown files optimized for LLM indexing
"""

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
import anthropic

from config import (
    ANTHROPIC_API_KEY,
    CLAUDE_MODEL,
    SITE_NAME,
    SITE_DOMAIN,
    load_vertical,
    get_data_path,
    slugify,
)

console = Console()

# Miami neighborhoods for local content
MIAMI_NEIGHBORHOODS = [
    "Brickell", "Wynwood", "Coral Gables", "Doral", "Kendall",
    "Miami Beach", "Coconut Grove", "Little Havana", "Hialeah",
    "Aventura", "Key Biscayne", "Pinecrest", "South Beach",
    "Midtown", "Design District", "Edgewater", "Downtown Miami",
]

INSURANCE_PLANS = [
    "Delta Dental", "Cigna", "Aetna", "MetLife", "United Healthcare",
    "Humana", "Guardian", "BlueCross BlueShield", "Medicaid",
]

DENTAL_SPECIALTIES = [
    "implants", "orthodontics", "cosmetic", "pediatric",
    "emergency", "root canal", "whitening", "veneers",
]


def select_businesses_for_article(places: list, criteria: dict, count: int = 10) -> list:
    """Select the best businesses for an article based on criteria."""
    
    filtered = places.copy()
    
    # Filter by neighborhood if specified
    if criteria.get("neighborhood"):
        neighborhood = criteria["neighborhood"].lower()
        filtered = [p for p in filtered if neighborhood in p.get("address", "").lower()]
    
    # Filter by specialty/enriched data if specified
    if criteria.get("specialty"):
        specialty = criteria["specialty"].lower()
        enriched_filtered = []
        for p in filtered:
            enriched = p.get("enriched_data", {})
            specialties = enriched.get("specialties", []) or []
            procedures = enriched.get("procedures", []) or []
            all_text = " ".join(str(s).lower() for s in specialties + procedures)
            if specialty in all_text:
                enriched_filtered.append(p)
        if enriched_filtered:
            filtered = enriched_filtered
    
    # Filter by insurance if specified
    if criteria.get("insurance"):
        insurance = criteria["insurance"].lower()
        ins_filtered = []
        for p in filtered:
            enriched = p.get("enriched_data", {})
            accepted = enriched.get("insurance_accepted", []) or []
            if any(insurance in str(i).lower() for i in accepted):
                ins_filtered.append(p)
        if ins_filtered:
            filtered = ins_filtered
    
    # Sort by weighted score (rating * log(review_count))
    import math
    filtered.sort(
        key=lambda x: (x.get("rating") or 0) * math.log(max(x.get("review_count", 1), 1)),
        reverse=True
    )
    
    return filtered[:count]


def generate_article(
    template: str,
    businesses: list,
    vertical: dict,
    city: str,
    variables: dict,
) -> dict:
    """Generate a blog article using Claude API."""
    
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    # Build the title
    year = datetime.now().year
    title = template.format(
        count=len(businesses),
        city=city,
        year=year,
        **variables,
    )
    
    # Build business data summary for Claude
    biz_summaries = []
    for i, biz in enumerate(businesses, 1):
        enriched = biz.get("enriched_data", {})
        review_analysis = biz.get("review_analysis", {})
        
        summary = f"""
Business #{i}: {biz['name']}
- Address: {biz['address']}
- Rating: {biz.get('rating', 'N/A')} ({biz.get('review_count', 0)} reviews)
- Phone: {biz.get('phone', 'N/A')}
- Website: {biz.get('website', 'N/A')}
- Hours: {json.dumps(biz.get('hours', {}), indent=2) if biz.get('hours') else 'N/A'}
- Enriched data: {json.dumps(enriched, indent=2) if enriched else 'None'}
- Review sentiment: {review_analysis.get('summary', 'N/A')}
- Positive themes: {review_analysis.get('themes_positive', [])}
"""
        biz_summaries.append(summary)
    
    businesses_text = "\n".join(biz_summaries)
    
    prompt = f"""You are writing a blog article for {SITE_NAME}, a directory that helps people find the best local {vertical['display_name'].lower()}.

ARTICLE TITLE: {title}

BUSINESS DATA:
{businesses_text}

INSTRUCTIONS:
1. Write a helpful, informative article of 1200-1800 words
2. Structure with an engaging intro, then cover each business with specific details
3. Include practical info: what makes each place stand out, who it's best for, pricing if available
4. Use natural, conversational tone — not salesy or generic
5. Include structured data hints: mention specific services, insurance plans, neighborhoods, etc.
6. Add a "How We Ranked These" section explaining methodology (ratings, reviews, patient feedback)
7. End with a "Quick Comparison" section summarizing key differences
8. DO NOT fabricate information. Only use the data provided. If data is missing, don't mention that field.

FORMAT:
- Write in Markdown
- Use H2 (##) for main sections
- Use H3 (###) for each business
- Include a front-matter block with metadata

Write the complete article now."""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        content = response.content[0].text
        
        # Create front-matter
        slug = slugify(title)
        front_matter = f"""---
title: "{title}"
slug: "{slug}"
date: "{datetime.now().strftime('%Y-%m-%d')}"
city: "{city}"
vertical: "{vertical['name']}"
businesses_featured: {len(businesses)}
schema_type: "Article"
description: "{title} - Updated guide with ratings, reviews, and detailed information."
---

"""
        
        return {
            "title": title,
            "slug": slug,
            "content": front_matter + content,
            "date": datetime.now().isoformat(),
            "businesses_featured": [b["name"] for b in businesses],
            "city": city,
            "vertical": vertical["name"],
        }
    
    except Exception as e:
        console.print(f"[red]Error generating article: {e}[/red]")
        return None


def generate_content(vertical_name: str, city: str, count: int = 5):
    """Generate blog content for a vertical in a city."""
    
    if not ANTHROPIC_API_KEY:
        console.print("[red]ERROR: ANTHROPIC_API_KEY not set in .env[/red]")
        return
    
    vertical = load_vertical(vertical_name)
    data_path = get_data_path(vertical_name, city)
    places_file = data_path / "places.json"
    
    if not places_file.exists():
        console.print(f"[red]No data found. Run fetch_places.py and enrich_data.py first.[/red]")
        return
    
    with open(places_file) as f:
        places = json.load(f)
    
    console.print(f"\n[bold cyan]📝 Generating {count} articles for {vertical['display_name']} in {city}[/bold cyan]")
    console.print(f"   Total businesses in database: {len(places)}\n")
    
    # Create content output directory
    content_dir = data_path / "content"
    content_dir.mkdir(exist_ok=True)
    
    # Generate articles from templates
    templates = vertical["content_templates"]
    articles_generated = []
    
    for i in range(min(count, len(templates))):
        template = templates[i]
        
        # Determine variables for this template
        variables = {
            "neighborhood": random.choice(MIAMI_NEIGHBORHOODS),
            "insurance": random.choice(INSURANCE_PLANS),
            "specialty": random.choice(DENTAL_SPECIALTIES),
            "cuisine": "sushi",  # For restaurants
            "type": "CrossFit",  # For gyms
        }
        
        # Select appropriate businesses
        criteria = {}
        template_lower = template.lower()
        
        if "{neighborhood}" in template:
            criteria["neighborhood"] = variables["neighborhood"]
        if "{insurance}" in template:
            criteria["insurance"] = variables["insurance"]
        if "{specialty}" in template:
            criteria["specialty"] = variables["specialty"]
        
        businesses = select_businesses_for_article(places, criteria, count=10)
        
        if len(businesses) < 3:
            # Fallback: use top-rated overall
            businesses = select_businesses_for_article(places, {}, count=10)
        
        if not businesses:
            console.print(f"  [yellow]⚠ No businesses match criteria for template {i+1}[/yellow]")
            continue
        
        console.print(f"  [dim]Generating article {i+1}/{count}...[/dim]")
        
        article = generate_article(
            template=template,
            businesses=businesses,
            vertical=vertical,
            city=city,
            variables=variables,
        )
        
        if article:
            # Save article
            article_file = content_dir / f"{article['slug']}.md"
            with open(article_file, "w") as f:
                f.write(article["content"])
            
            articles_generated.append({
                "title": article["title"],
                "slug": article["slug"],
                "date": article["date"],
                "file": str(article_file),
            })
            
            console.print(f"  [green]✓ {article['title']}[/green]")
        
        # Rate limit between articles
        import time
        time.sleep(2)
    
    # Save article index
    index_file = content_dir / "index.json"
    
    # Load existing index if any
    existing = []
    if index_file.exists():
        with open(index_file) as f:
            existing = json.load(f)
    
    existing.extend(articles_generated)
    
    with open(index_file, "w") as f:
        json.dump(existing, f, indent=2)
    
    console.print(f"\n[bold green]✅ Generated {len(articles_generated)} articles![/bold green]")
    console.print(f"   Saved to: {content_dir}")


def main():
    parser = argparse.ArgumentParser(description="Generate blog content from business data")
    parser.add_argument("--vertical", required=True, help="Vertical name")
    parser.add_argument("--city", required=True, help="City name (e.g., miami)")
    parser.add_argument("--count", type=int, default=5, help="Number of articles to generate")
    
    args = parser.parse_args()
    generate_content(args.vertical, args.city, args.count)


if __name__ == "__main__":
    main()
