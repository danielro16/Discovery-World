"""
build_site.py — Generates the static directory website with LLM-optimized pages.

Usage:
    python pipeline/build_site.py --vertical dentists --city miami
    python pipeline/build_site.py --all

This script:
1. Loads business data and blog content
2. Generates individual business pages with Schema.org markup
3. Generates category/list pages
4. Generates the blog index
5. Outputs a complete static site ready for deployment
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from jinja2 import Template
from rich.console import Console

from config import (
    SITE_NAME,
    SITE_DOMAIN,
    DATA_DIR,
    SITE_DIR,
    load_vertical,
    get_data_path,
    slugify,
    list_verticals,
)

console = Console()


# ── HTML Templates ──────────────────────────────────────────────────────────

BASE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} | {{ site_name }}</title>
    <meta name="description" content="{{ description }}">
    
    <!-- Open Graph -->
    <meta property="og:title" content="{{ title }}">
    <meta property="og:description" content="{{ description }}">
    <meta property="og:type" content="{{ og_type | default('website') }}">
    <meta property="og:url" content="{{ canonical_url }}">
    
    <!-- Schema.org JSON-LD -->
    <script type="application/ld+json">
    {{ schema_json }}
    </script>
    
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --bg: #ffffff;
            --bg-alt: #f8fafc;
            --text: #1e293b;
            --text-light: #64748b;
            --border: #e2e8f0;
            --success: #10b981;
            --warning: #f59e0b;
            --radius: 12px;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            color: var(--text);
            line-height: 1.6;
            background: var(--bg);
        }
        
        .container { max-width: 1100px; margin: 0 auto; padding: 0 24px; }
        
        header {
            border-bottom: 1px solid var(--border);
            padding: 16px 0;
        }
        header .container {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logo { font-size: 1.5rem; font-weight: 700; color: var(--primary); text-decoration: none; }
        nav a { margin-left: 24px; color: var(--text-light); text-decoration: none; font-size: 0.95rem; }
        nav a:hover { color: var(--primary); }
        
        main { padding: 40px 0; }
        
        h1 { font-size: 2rem; margin-bottom: 8px; }
        h2 { font-size: 1.5rem; margin: 32px 0 16px; }
        h3 { font-size: 1.2rem; margin: 24px 0 8px; }
        
        .subtitle { color: var(--text-light); font-size: 1.1rem; margin-bottom: 32px; }
        
        .business-card {
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 24px;
            margin-bottom: 20px;
            transition: box-shadow 0.2s;
        }
        .business-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
        
        .business-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
        }
        .business-name { font-size: 1.25rem; font-weight: 600; }
        .business-name a { color: var(--text); text-decoration: none; }
        .business-name a:hover { color: var(--primary); }
        
        .rating {
            display: flex;
            align-items: center;
            gap: 6px;
            font-weight: 600;
        }
        .stars { color: #f59e0b; }
        .review-count { color: var(--text-light); font-weight: 400; font-size: 0.9rem; }
        
        .business-address { color: var(--text-light); margin-bottom: 8px; }
        
        .business-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 12px;
        }
        .tag {
            background: var(--bg-alt);
            border: 1px solid var(--border);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            color: var(--text-light);
        }
        .tag.premium { background: #eff6ff; border-color: var(--primary); color: var(--primary); }
        
        .business-contact {
            display: flex;
            gap: 16px;
            margin-top: 12px;
            font-size: 0.9rem;
        }
        .business-contact a { color: var(--primary); text-decoration: none; }
        
        .completeness-bar {
            height: 4px;
            background: var(--border);
            border-radius: 2px;
            margin-top: 16px;
        }
        .completeness-fill {
            height: 100%;
            background: var(--success);
            border-radius: 2px;
            transition: width 0.3s;
        }
        
        .claim-banner {
            background: linear-gradient(135deg, #eff6ff, #e0f2fe);
            border: 1px solid #bfdbfe;
            border-radius: var(--radius);
            padding: 20px 24px;
            margin-top: 24px;
            text-align: center;
        }
        .claim-banner h3 { color: var(--primary-dark); margin: 0 0 8px; }
        .claim-banner p { color: var(--text-light); margin-bottom: 12px; }
        .claim-btn {
            display: inline-block;
            background: var(--primary);
            color: white;
            padding: 10px 24px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
        }
        
        .blog-card {
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 20px 24px;
            margin-bottom: 16px;
        }
        .blog-card h3 a { color: var(--text); text-decoration: none; }
        .blog-card h3 a:hover { color: var(--primary); }
        .blog-date { color: var(--text-light); font-size: 0.85rem; }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }
        .stat-card {
            background: var(--bg-alt);
            border-radius: var(--radius);
            padding: 20px;
            text-align: center;
        }
        .stat-number { font-size: 2rem; font-weight: 700; color: var(--primary); }
        .stat-label { color: var(--text-light); font-size: 0.9rem; }
        
        footer {
            border-top: 1px solid var(--border);
            padding: 32px 0;
            margin-top: 60px;
            color: var(--text-light);
            font-size: 0.9rem;
            text-align: center;
        }
        
        @media (max-width: 640px) {
            h1 { font-size: 1.5rem; }
            .business-header { flex-direction: column; gap: 8px; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <a href="/" class="logo">{{ site_name }}</a>
            <nav>
                {% for v in verticals %}
                <a href="/{{ v.name }}/">{{ v.display_name }}</a>
                {% endfor %}
                <a href="/blog/">Blog</a>
            </nav>
        </div>
    </header>
    
    <main>
        <div class="container">
            {{ content }}
        </div>
    </main>
    
    <footer>
        <div class="container">
            <p>&copy; {{ year }} {{ site_name }}. AI-optimized local business directory.</p>
            <p style="margin-top:8px;">Are you a business owner? <a href="/claim/" style="color:var(--primary)">Claim your profile</a></p>
        </div>
    </footer>
</body>
</html>"""


BUSINESS_PAGE_CONTENT = """
<h1>{{ business.name }}</h1>
<p class="subtitle">{{ business.address }}</p>

<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-number">{{ business.rating or 'N/A' }}</div>
        <div class="stat-label">Rating ({{ business.review_count }} reviews)</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">{{ business.profile_completeness }}%</div>
        <div class="stat-label">Profile Completeness</div>
    </div>
    {% if enriched.get('free_consultation') %}
    <div class="stat-card">
        <div class="stat-number">✓</div>
        <div class="stat-label">Free Consultation</div>
    </div>
    {% endif %}
</div>

{% if enriched %}
<h2>Services & Specialties</h2>
{% if enriched.get('specialties') %}
<div class="business-tags">
    {% for s in enriched.specialties %}
    <span class="tag">{{ s }}</span>
    {% endfor %}
</div>
{% endif %}

{% if enriched.get('insurance_accepted') %}
<h2>Insurance Accepted</h2>
<div class="business-tags">
    {% for ins in enriched.insurance_accepted %}
    <span class="tag">{{ ins }}</span>
    {% endfor %}
</div>
{% endif %}

{% if enriched.get('languages') %}
<h2>Languages</h2>
<div class="business-tags">
    {% for lang in enriched.languages %}
    <span class="tag">{{ lang }}</span>
    {% endfor %}
</div>
{% endif %}
{% endif %}

<h2>Contact Information</h2>
<div class="business-contact" style="flex-direction:column; gap:8px;">
    {% if business.phone %}<div>📞 {{ business.phone }}</div>{% endif %}
    {% if business.website %}<div>🌐 <a href="{{ business.website }}" rel="nofollow">Website</a></div>{% endif %}
    {% if business.google_maps_url %}<div>📍 <a href="{{ business.google_maps_url }}" rel="nofollow">View on Google Maps</a></div>{% endif %}
</div>

{% if business.hours %}
<h2>Hours</h2>
<div style="display:grid; gap:4px; font-size:0.95rem;">
    {% for day, time in business.hours.items() %}
    <div><strong>{{ day }}:</strong> {{ time }}</div>
    {% endfor %}
</div>
{% endif %}

{% if business.review_analysis and business.review_analysis.summary %}
<h2>What Patients Say</h2>
<p>{{ business.review_analysis.summary }}</p>
{% if business.review_analysis.themes_positive %}
<div class="business-tags" style="margin-top:8px;">
    {% for theme in business.review_analysis.themes_positive %}
    <span class="tag premium">{{ theme }}</span>
    {% endfor %}
</div>
{% endif %}
{% endif %}

{% if not business.claimed %}
<div class="claim-banner">
    <h3>Is this your business?</h3>
    <p>Claim your profile to add complete information, respond to reviews, and appear more prominently in AI recommendations.</p>
    <a href="/claim/?id={{ business.id }}" class="claim-btn">Claim This Profile</a>
</div>
{% endif %}
"""


LISTING_PAGE_CONTENT = """
<h1>{{ vertical.display_name }} in {{ city }}</h1>
<p class="subtitle">{{ total }} {{ vertical.display_name.lower() }} found · Updated {{ today }}</p>

<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-number">{{ total }}</div>
        <div class="stat-label">Total Listed</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">{{ avg_rating }}</div>
        <div class="stat-label">Avg Rating</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">{{ with_website }}</div>
        <div class="stat-label">With Website</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">{{ enriched_count }}</div>
        <div class="stat-label">Verified Profiles</div>
    </div>
</div>

{% for biz in businesses %}
<div class="business-card" itemscope itemtype="https://schema.org/{{ vertical.schema_type }}">
    <div class="business-header">
        <div>
            <div class="business-name" itemprop="name">
                <a href="/{{ vertical.name }}/{{ city_slug }}/{{ biz.slug }}/">{{ biz.name }}</a>
            </div>
            <div class="business-address" itemprop="address">{{ biz.address }}</div>
        </div>
        <div class="rating">
            <span class="stars">★</span>
            <span itemprop="ratingValue">{{ biz.rating or 'N/A' }}</span>
            <span class="review-count">({{ biz.review_count }} reviews)</span>
        </div>
    </div>
    
    <div class="business-tags">
        {% for tag in biz.tags %}
        <span class="tag">{{ tag }}</span>
        {% endfor %}
        {% if biz.profile_completeness < 50 %}
        <span class="tag" style="color:var(--warning);">Profile Incomplete</span>
        {% endif %}
    </div>
    
    <div class="business-contact">
        {% if biz.phone %}<span>📞 {{ biz.phone }}</span>{% endif %}
        {% if biz.website %}<a href="{{ biz.website }}" rel="nofollow">🌐 Website</a>{% endif %}
    </div>
    
    <div class="completeness-bar">
        <div class="completeness-fill" style="width: {{ biz.profile_completeness }}%"></div>
    </div>
</div>
{% endfor %}
"""


def generate_schema_business(business: dict, vertical: dict) -> str:
    """Generate Schema.org JSON-LD for a business."""
    schema = {
        "@context": "https://schema.org",
        "@type": vertical["schema_type"],
        "name": business["name"],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": business["address"],
        },
        "geo": {
            "@type": "GeoCoordinates",
            "latitude": business.get("location", {}).get("lat"),
            "longitude": business.get("location", {}).get("lng"),
        },
        "telephone": business.get("phone", ""),
        "url": business.get("website", ""),
    }
    
    if business.get("rating"):
        schema["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": business["rating"],
            "reviewCount": business.get("review_count", 0),
        }
    
    if business.get("hours"):
        schema["openingHoursSpecification"] = []
        for day, time_range in business["hours"].items():
            schema["openingHoursSpecification"].append({
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": day,
                "opens": time_range.split(" - ")[0] if " - " in time_range else "",
                "closes": time_range.split(" - ")[1] if " - " in time_range else "",
            })
    
    return json.dumps(schema, indent=2)


def generate_schema_listing(businesses: list, vertical: dict, city: str) -> str:
    """Generate Schema.org JSON-LD for a listing page."""
    schema = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"{vertical['display_name']} in {city}",
        "numberOfItems": len(businesses),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "item": {
                    "@type": vertical["schema_type"],
                    "name": biz["name"],
                    "address": biz["address"],
                }
            }
            for i, biz in enumerate(businesses[:20])
        ],
    }
    return json.dumps(schema, indent=2)


def build_site(vertical_name: str = None, city: str = None):
    """Build the static site for one or all verticals."""
    
    output_dir = SITE_DIR / "public"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_verticals = []
    for v_name in list_verticals():
        v = load_vertical(v_name)
        all_verticals.append({"name": v["name"], "display_name": v["display_name"]})
    
    base_tpl = Template(BASE_TEMPLATE)
    listing_tpl = Template(LISTING_PAGE_CONTENT)
    business_tpl = Template(BUSINESS_PAGE_CONTENT)
    
    verticals_to_build = [vertical_name] if vertical_name else list_verticals()
    
    total_pages = 0
    
    for v_name in verticals_to_build:
        vertical = load_vertical(v_name)
        
        # Find all cities with data for this vertical
        vertical_data_dir = DATA_DIR / v_name
        if not vertical_data_dir.exists():
            console.print(f"[yellow]No data for {v_name}, skipping[/yellow]")
            continue
        
        cities = [d.name for d in vertical_data_dir.iterdir() if d.is_dir()]
        
        if city:
            city_slug = city.lower().replace(" ", "_").replace(",", "")
            cities = [c for c in cities if c == city_slug]
        
        for city_dir_name in cities:
            data_path = vertical_data_dir / city_dir_name
            places_file = data_path / "places.json"
            
            if not places_file.exists():
                continue
            
            with open(places_file) as f:
                places = json.load(f)
            
            city_display = city_dir_name.replace("_", " ").title()
            
            console.print(f"[cyan]Building {vertical['display_name']} in {city_display}...[/cyan]")
            
            # Prepare business data for templates
            for place in places:
                place["slug"] = slugify(place["name"])
                enriched = place.get("enriched_data", {})
                tags = []
                if enriched.get("specialties"):
                    tags.extend(enriched["specialties"][:3])
                if enriched.get("insurance_accepted"):
                    tags.append(f"{len(enriched['insurance_accepted'])} insurances")
                if enriched.get("languages"):
                    tags.extend(enriched["languages"][:2])
                place["tags"] = tags
            
            # ── Build listing page ──
            listing_dir = output_dir / v_name / city_dir_name
            listing_dir.mkdir(parents=True, exist_ok=True)
            
            enriched_count = len([p for p in places if p.get("enriched")])
            avg_rating = round(
                sum(p.get("rating") or 0 for p in places) / max(len(places), 1), 1
            )
            
            listing_content = listing_tpl.render(
                vertical=vertical,
                city=city_display,
                city_slug=city_dir_name,
                businesses=places[:50],
                total=len(places),
                avg_rating=avg_rating,
                with_website=len([p for p in places if p.get("website")]),
                enriched_count=enriched_count,
                today=datetime.now().strftime("%B %d, %Y"),
            )
            
            listing_html = base_tpl.render(
                title=f"{vertical['display_name']} in {city_display}",
                description=f"Find the best {vertical['display_name'].lower()} in {city_display}. Ratings, reviews, and detailed profiles.",
                canonical_url=f"{SITE_DOMAIN}/{v_name}/{city_dir_name}/",
                schema_json=generate_schema_listing(places, vertical, city_display),
                site_name=SITE_NAME,
                verticals=all_verticals,
                content=listing_content,
                year=datetime.now().year,
            )
            
            with open(listing_dir / "index.html", "w") as f:
                f.write(listing_html)
            total_pages += 1
            
            # ── Build individual business pages ──
            for place in places:
                biz_dir = listing_dir / place["slug"]
                biz_dir.mkdir(parents=True, exist_ok=True)
                
                enriched = place.get("enriched_data", {})
                
                biz_content = business_tpl.render(
                    business=place,
                    enriched=enriched,
                    vertical=vertical,
                )
                
                biz_html = base_tpl.render(
                    title=f"{place['name']} - {vertical['display_name_singular']} in {city_display}",
                    description=f"{place['name']} in {city_display}. Rating: {place.get('rating', 'N/A')}/5 from {place.get('review_count', 0)} reviews. Contact, hours, and services.",
                    canonical_url=f"{SITE_DOMAIN}/{v_name}/{city_dir_name}/{place['slug']}/",
                    og_type="business.business",
                    schema_json=generate_schema_business(place, vertical),
                    site_name=SITE_NAME,
                    verticals=all_verticals,
                    content=biz_content,
                    year=datetime.now().year,
                )
                
                with open(biz_dir / "index.html", "w") as f:
                    f.write(biz_html)
                total_pages += 1
            
            # ── Build blog pages ──
            content_dir = data_path / "content"
            if content_dir.exists():
                blog_dir = output_dir / "blog" / v_name / city_dir_name
                blog_dir.mkdir(parents=True, exist_ok=True)
                
                for md_file in content_dir.glob("*.md"):
                    content = md_file.read_text()
                    
                    # Simple markdown to HTML (for production, use a proper renderer)
                    import re
                    html_content = content
                    html_content = re.sub(r'^---[\s\S]*?---\n', '', html_content)
                    html_content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)
                    html_content = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
                    html_content = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
                    html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content)
                    html_content = re.sub(r'\n\n', '</p><p>', html_content)
                    html_content = f'<p>{html_content}</p>'
                    
                    # Extract title from filename
                    title = md_file.stem.replace("-", " ").title()
                    
                    blog_post_html = base_tpl.render(
                        title=title,
                        description=f"{title} - {SITE_NAME}",
                        canonical_url=f"{SITE_DOMAIN}/blog/{v_name}/{city_dir_name}/{md_file.stem}/",
                        schema_json=json.dumps({
                            "@context": "https://schema.org",
                            "@type": "Article",
                            "headline": title,
                            "datePublished": datetime.now().isoformat(),
                            "publisher": {"@type": "Organization", "name": SITE_NAME},
                        }),
                        site_name=SITE_NAME,
                        verticals=all_verticals,
                        content=html_content,
                        year=datetime.now().year,
                    )
                    
                    post_dir = blog_dir / md_file.stem
                    post_dir.mkdir(parents=True, exist_ok=True)
                    with open(post_dir / "index.html", "w") as f:
                        f.write(blog_post_html)
                    total_pages += 1
    
    console.print(f"\n[bold green]✅ Site built! {total_pages} pages generated.[/bold green]")
    console.print(f"   Output: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Build the static directory site")
    parser.add_argument("--vertical", help="Vertical name (omit for all)")
    parser.add_argument("--city", help="City slug (omit for all)")
    
    args = parser.parse_args()
    build_site(args.vertical, args.city)


if __name__ == "__main__":
    main()
