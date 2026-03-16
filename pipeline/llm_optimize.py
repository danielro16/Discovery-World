"""
llm_optimize.py — Generate the LLM optimization layer for AgentReady.

Produces 7 types of files that make the site discoverable and citable by AI:
  1. robots.txt      — Welcome AI crawlers by name
  2. llms.txt        — Machine-readable site overview (llmstxt.org standard)
  3. llms-full.txt   — Complete structured text dump of all business data
  4. sitemap.xml     — Auto-generated sitemap with all pages
  5. FAQ JSON        — Per vertical+city FAQ data with FAQPage schema
  6. knowledge-graph — Schema.org JSON-LD graph of all businesses
  7. IndexNow        — Key file + ping function for instant Bing indexing

Usage:
    python pipeline/llm_optimize.py                        # generate all (uses data/)
    python pipeline/llm_optimize.py --data-dir data_v2     # use data_v2/
    python pipeline/llm_optimize.py --only robots          # generate one type
    python pipeline/llm_optimize.py --ping                 # ping IndexNow after
    python pipeline/llm_optimize.py --output-dir dist/     # custom output
"""

import argparse
import hashlib
import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

sys.path.insert(0, str(Path(__file__).parent))
from config import DATA_DIR as DEFAULT_DATA_DIR, SITE_DOMAIN, SITE_NAME, load_vertical, list_verticals, slugify
from rich.console import Console

console = Console()

PROJECT_ROOT = Path(__file__).parent.parent

# DATA_DIR may be overridden at runtime via --data-dir argument
DATA_DIR = DEFAULT_DATA_DIR


# ── Helpers ──────────────────────────────────────────────────────────────────


def load_all_data() -> dict:
    """Load all business data across verticals and cities.

    Returns: {vertical_name: {"_config": {...}, city_slug: [places], ...}}
    """
    result = {}
    for v_name in list_verticals():
        v_config = load_vertical(v_name)
        v_data = {"_config": v_config}

        v_dir = DATA_DIR / v_name
        if not v_dir.exists():
            continue

        for city_dir in sorted(v_dir.iterdir()):
            if not city_dir.is_dir():
                continue
            places_file = city_dir / "places.json"
            if not places_file.exists():
                continue
            with open(places_file) as f:
                places = json.load(f)
            if places:
                v_data[city_dir.name] = places

        if len(v_data) > 1:  # has at least one city besides _config
            result[v_name] = v_data

    return result


def format_city_name(city_slug: str) -> str:
    """Convert city slug to display name: miami_fl -> Miami Fl."""
    return city_slug.replace("_", " ").replace("-", " ").title()


def city_url_slug(city_slug: str) -> str:
    """Convert data directory slug to URL slug: miami_fl -> miami-fl."""
    return city_slug.replace("_", "-")


def get_enriched_field(place: dict, field: str):
    """Get enriched field from top-level or enriched_data."""
    val = place.get(field)
    if val is not None:
        return val
    ed = place.get("enriched_data", {})
    if isinstance(ed, dict):
        return ed.get(field)
    return None


def count_businesses(all_data: dict) -> int:
    """Count total businesses across all data."""
    total = 0
    for v_name, v_data in all_data.items():
        for key, places in v_data.items():
            if key == "_config":
                continue
            total += len(places)
    return total


# ── 1. robots.txt ────────────────────────────────────────────────────────────


AI_CRAWLERS = [
    "GPTBot",
    "OAI-SearchBot",
    "ClaudeBot",
    "PerplexityBot",
    "Google-Extended",
    "CopilotBot",
    "Amazonbot",
    "FacebookBot",
    "anthropic-ai",
    "Bytespider",
    "CCBot",
    "ChatGPT-User",
    "cohere-ai",
    "Applebot-Extended",
]


def generate_robots_txt(output_dir: Path, all_data: dict = None) -> None:
    lines = [
        f"# {SITE_NAME} — AI-Native Local Business Directory",
        "# We welcome AI crawlers. Our data is structured for LLM consumption.",
        "#",
        f"# LLM-readable site overview: {SITE_DOMAIN}/llms.txt",
        f"# Full data dump: {SITE_DOMAIN}/llms-full.txt",
        f"# Knowledge graph: {SITE_DOMAIN}/knowledge-graph.jsonld",
        "",
        "User-agent: *",
        "Allow: /",
        "",
    ]

    for bot in AI_CRAWLERS:
        lines.append(f"User-agent: {bot}")
        lines.append("Allow: /")
        lines.append("")

    lines.append(f"Sitemap: {SITE_DOMAIN}/sitemap.xml")
    lines.append("")

    (output_dir / "robots.txt").write_text("\n".join(lines))
    console.print("  [green]robots.txt[/green] — welcoming {0} AI crawlers".format(len(AI_CRAWLERS)))


# ── 2. llms.txt ──────────────────────────────────────────────────────────────


def generate_llms_txt(output_dir: Path, all_data: dict) -> None:
    total = count_businesses(all_data)

    # Collect city stats
    all_cities = set()
    for v_name, v_data in all_data.items():
        for key in v_data:
            if key != "_config":
                all_cities.add(key)

    lines = [
        f"# {SITE_NAME}",
        "",
        f"> {SITE_NAME} is an AI-native local business directory covering"
        f" {len(all_data)} categories across {len(all_cities)} US cities."
        f" {total} businesses with ratings, reviews, hours, specialties,"
        " insurance, languages, and more. All data is structured for LLM consumption.",
        "",
        "## Documentation",
        "",
        f"- [Full Data Dump]({SITE_DOMAIN}/llms-full.txt): Complete structured text of all {total} businesses",
        f"- [Knowledge Graph]({SITE_DOMAIN}/knowledge-graph.jsonld): Schema.org JSON-LD graph of all businesses",
        f"- [Sitemap]({SITE_DOMAIN}/sitemap.xml): Complete URL index",
        f"- [FAQ Pages]({SITE_DOMAIN}/dentists/miami-fl/faq/): Structured Q&A per city (example)",
        "",
        "## Categories",
        "",
    ]

    for v_name, v_data in sorted(all_data.items()):
        config = v_data["_config"]
        city_count = len([k for k in v_data if k != "_config"])
        biz_count = sum(len(v_data[k]) for k in v_data if k != "_config")
        lines.append(
            f"- [{config['display_name']}]({SITE_DOMAIN}/{v_name}/): "
            f"{biz_count} businesses across {city_count} cities"
        )

    lines.append("")
    lines.append("## Cities")
    lines.append("")

    # Group cities with their verticals
    city_verticals = defaultdict(list)
    for v_name, v_data in all_data.items():
        config = v_data["_config"]
        for key in v_data:
            if key != "_config":
                city_verticals[key].append(config["display_name"])

    for city_slug in sorted(city_verticals.keys()):
        verticals_str = ", ".join(sorted(city_verticals[city_slug]))
        city_display = format_city_name(city_slug)
        city_url = city_url_slug(city_slug)
        lines.append(f"- [{city_display}]({SITE_DOMAIN}/dentists/{city_url}/): {verticals_str}")

    lines.append("")

    (output_dir / "llms.txt").write_text("\n".join(lines))
    console.print(f"  [green]llms.txt[/green] — {len(all_data)} verticals, {len(all_cities)} cities")


# ── 3. llms-full.txt ─────────────────────────────────────────────────────────


def generate_llms_full_txt(output_dir: Path, all_data: dict) -> None:
    total = count_businesses(all_data)
    today = datetime.now().strftime("%Y-%m-%d")

    lines = [
        f"# {SITE_NAME} — Complete Business Directory",
        f"# Generated: {today}",
        f"# Total businesses: {total}",
        f"# Source: {SITE_DOMAIN}",
        "",
    ]

    for v_name, v_data in sorted(all_data.items()):
        config = v_data["_config"]
        fields = config.get("fields_to_extract", [])

        lines.append("=" * 70)
        lines.append(f"## {config['display_name'].upper()}")
        lines.append("=" * 70)
        lines.append("")

        for city_slug in sorted(k for k in v_data if k != "_config"):
            places = v_data[city_slug]
            city_display = format_city_name(city_slug)
            city_url = city_url_slug(city_slug)

            lines.append(f"### {city_display} ({len(places)} businesses)")
            lines.append("-" * 50)
            lines.append("")

            # Sort by rating descending
            sorted_places = sorted(
                places,
                key=lambda p: (p.get("rating") or 0, p.get("review_count") or 0),
                reverse=True,
            )

            for i, place in enumerate(sorted_places, 1):
                slug = slugify(place["name"])
                url = f"{SITE_DOMAIN}/{v_name}/{city_url}/{slug}/"

                lines.append(f"{i}. {place['name']}")
                lines.append(f"   Address: {place.get('address', 'N/A')}")

                if place.get("phone"):
                    lines.append(f"   Phone: {place['phone']}")
                if place.get("website"):
                    lines.append(f"   Website: {place['website']}")

                rating = place.get("rating")
                reviews = place.get("review_count", 0)
                if rating:
                    lines.append(f"   Rating: {rating}/5 ({reviews} reviews)")

                # Enriched fields
                specialties = get_enriched_field(place, "specialties")
                if specialties and isinstance(specialties, list):
                    lines.append(f"   Specialties: {', '.join(specialties)}")

                insurance = get_enriched_field(place, "insurance_accepted")
                if insurance and isinstance(insurance, list):
                    lines.append(f"   Insurance: {', '.join(insurance)}")

                languages = get_enriched_field(place, "languages_spoken") or get_enriched_field(place, "languages")
                if languages and isinstance(languages, list):
                    lines.append(f"   Languages: {', '.join(languages)}")

                # Vertical-specific fields
                for field in fields:
                    if field in ("specialties", "insurance_accepted", "languages_spoken", "procedures_offered"):
                        continue  # already handled
                    val = get_enriched_field(place, field)
                    if val is not None and val != "" and val != []:
                        field_display = field.replace("_", " ").title()
                        if isinstance(val, list):
                            lines.append(f"   {field_display}: {', '.join(str(v) for v in val)}")
                        elif isinstance(val, bool):
                            lines.append(f"   {field_display}: {'Yes' if val else 'No'}")
                        else:
                            lines.append(f"   {field_display}: {val}")

                # Hours
                hours = place.get("hours")
                if hours and isinstance(hours, dict):
                    hours_str = "; ".join(f"{d}: {t}" for d, t in hours.items())
                    lines.append(f"   Hours: {hours_str}")

                # AI description
                desc = get_enriched_field(place, "ai_description")
                if desc:
                    lines.append(f"   Description: {desc}")

                # Review summary
                ra = place.get("review_analysis", {})
                if ra and ra.get("summary"):
                    lines.append(f"   What customers say: {ra['summary']}")

                lines.append(f"   Profile: {url}")
                lines.append("")

    (output_dir / "llms-full.txt").write_text("\n".join(lines))
    size_mb = round(len("\n".join(lines)) / 1024 / 1024, 1)
    console.print(f"  [green]llms-full.txt[/green] — {total} businesses, {size_mb}MB")


# ── 4. sitemap.xml ───────────────────────────────────────────────────────────


def generate_sitemap_xml(output_dir: Path, all_data: dict) -> None:
    today = datetime.now().strftime("%Y-%m-%d")

    urlset = Element("urlset")
    urlset.set("xmlns", "http://www.sitemaps.org/schemas/sitemap/0.9")

    def add_url(loc: str, priority: str, changefreq: str = "weekly"):
        url_el = SubElement(urlset, "url")
        SubElement(url_el, "loc").text = loc
        SubElement(url_el, "lastmod").text = today
        SubElement(url_el, "changefreq").text = changefreq
        SubElement(url_el, "priority").text = priority

    # Homepage
    add_url(f"{SITE_DOMAIN}/", "1.0", "daily")

    url_count = 1

    for v_name, v_data in sorted(all_data.items()):
        # Vertical index
        add_url(f"{SITE_DOMAIN}/{v_name}/", "0.8")
        url_count += 1

        for city_slug in sorted(k for k in v_data if k != "_config"):
            city_url = city_url_slug(city_slug)
            places = v_data[city_slug]

            # City listing page
            add_url(f"{SITE_DOMAIN}/{v_name}/{city_url}/", "0.8")
            url_count += 1

            # FAQ page
            add_url(f"{SITE_DOMAIN}/{v_name}/{city_url}/faq/", "0.7")
            url_count += 1

            # Individual business pages
            for place in places:
                slug = slugify(place["name"])
                add_url(f"{SITE_DOMAIN}/{v_name}/{city_url}/{slug}/", "0.7")
                url_count += 1

    # Static pages
    for page in ["claim", "compare", "blog"]:
        add_url(f"{SITE_DOMAIN}/{page}/", "0.5")
        url_count += 1

    # LLM files
    add_url(f"{SITE_DOMAIN}/llms.txt", "0.6")
    add_url(f"{SITE_DOMAIN}/llms-full.txt", "0.6")
    add_url(f"{SITE_DOMAIN}/knowledge-graph.jsonld", "0.6")
    url_count += 3

    xml_str = parseString(tostring(urlset, encoding="unicode")).toprettyxml(indent="  ")
    # Remove extra xml declaration line
    xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + "\n".join(xml_str.split("\n")[1:])

    (output_dir / "sitemap.xml").write_text(xml_str)
    console.print(f"  [green]sitemap.xml[/green] — {url_count} URLs")


# ── 5. FAQ data ──────────────────────────────────────────────────────────────


def generate_faq_data(output_dir: Path, all_data: dict) -> None:
    """Generate FAQ JSON files per vertical+city in data/ for Astro consumption."""
    faq_count = 0

    for v_name, v_data in all_data.items():
        config = v_data["_config"]
        display = config["display_name"].lower()
        display_cap = config["display_name"]

        for city_slug in sorted(k for k in v_data if k != "_config"):
            places = v_data[city_slug]
            city_display = format_city_name(city_slug)
            questions = []

            # ── Q1: Best overall ──
            top = sorted(
                [p for p in places if (p.get("rating") or 0) > 0 and (p.get("review_count") or 0) >= 5],
                key=lambda p: (p["rating"], p["review_count"]),
                reverse=True,
            )[:5]
            if top:
                answer_parts = [
                    f"{p['name']} ({p['rating']}/5, {p['review_count']} reviews)"
                    for p in top
                ]
                questions.append({
                    "question": f"What are the best {display} in {city_display}?",
                    "answer": (
                        f"The highest-rated {display} in {city_display} based on customer reviews are: "
                        + ", ".join(answer_parts)
                        + f". Based on {len(places)} {display} listed on {SITE_NAME}."
                    ),
                })

            # ── Q2: Most reviewed ──
            most_reviewed = sorted(
                places, key=lambda p: p.get("review_count") or 0, reverse=True
            )[:5]
            if most_reviewed and (most_reviewed[0].get("review_count") or 0) > 0:
                answer_parts = [
                    f"{p['name']} ({p.get('review_count', 0)} reviews, {p.get('rating', 'N/A')}/5)"
                    for p in most_reviewed
                ]
                questions.append({
                    "question": f"Which {display} in {city_display} have the most reviews?",
                    "answer": (
                        f"The most reviewed {display} in {city_display} are: "
                        + ", ".join(answer_parts) + "."
                    ),
                })

            # ── Q3: Insurance questions ──
            insurance_map = defaultdict(list)
            for p in places:
                ins = get_enriched_field(p, "insurance_accepted")
                if ins and isinstance(ins, list):
                    for name in ins:
                        if name and isinstance(name, str):
                            insurance_map[name].append(p["name"])

            for ins_name in sorted(insurance_map.keys()):
                bizs = insurance_map[ins_name]
                if len(bizs) >= 2:
                    listed = ", ".join(bizs[:8])
                    more = f" and {len(bizs) - 8} more" if len(bizs) > 8 else ""
                    questions.append({
                        "question": f"Which {display} in {city_display} accept {ins_name}?",
                        "answer": (
                            f"{display_cap} in {city_display} that accept {ins_name} include: "
                            + listed + more + f". {len(bizs)} total found."
                        ),
                    })

            # ── Q4: Weekend hours ──
            weekend = []
            for p in places:
                hours = p.get("hours", {})
                if not isinstance(hours, dict):
                    continue
                sat = hours.get("Saturday", "")
                sun = hours.get("Sunday", "")
                if sat and "closed" not in sat.lower():
                    weekend.append(f"{p['name']} (Sat: {sat})")
                elif sun and "closed" not in sun.lower():
                    weekend.append(f"{p['name']} (Sun: {sun})")
            if weekend:
                listed = ", ".join(weekend[:8])
                more = f" and {len(weekend) - 8} more" if len(weekend) > 8 else ""
                questions.append({
                    "question": f"Which {display} in {city_display} are open on weekends?",
                    "answer": (
                        f"{display_cap} in {city_display} with weekend hours include: "
                        + listed + more + f". {len(weekend)} total with weekend availability."
                    ),
                })

            # ── Q5: Language questions ──
            lang_map = defaultdict(list)
            for p in places:
                langs = get_enriched_field(p, "languages_spoken") or get_enriched_field(p, "languages")
                if langs and isinstance(langs, list):
                    for lang in langs:
                        if lang and isinstance(lang, str) and lang.lower() != "english":
                            lang_map[lang].append(p["name"])

            for lang_name in sorted(lang_map.keys()):
                bizs = lang_map[lang_name]
                if len(bizs) >= 2:
                    listed = ", ".join(bizs[:8])
                    more = f" and {len(bizs) - 8} more" if len(bizs) > 8 else ""
                    questions.append({
                        "question": f"Which {display} in {city_display} speak {lang_name}?",
                        "answer": (
                            f"{lang_name}-speaking {display} in {city_display} include: "
                            + listed + more + f". {len(bizs)} total found."
                        ),
                    })

            # ── Q6: Free consultation (dentists, attorneys, therapists) ──
            free_consult = [
                p["name"] for p in places
                if get_enriched_field(p, "free_consultation") is True
            ]
            if free_consult:
                listed = ", ".join(free_consult[:8])
                more = f" and {len(free_consult) - 8} more" if len(free_consult) > 8 else ""
                questions.append({
                    "question": f"Which {display} in {city_display} offer free consultations?",
                    "answer": (
                        f"{display_cap} in {city_display} offering free consultations include: "
                        + listed + more + "."
                    ),
                })

            # ── Q7: Emergency (dentists) ──
            if v_name == "dentists":
                emergency = [
                    p["name"] for p in places
                    if get_enriched_field(p, "emergency_dentistry") is True
                ]
                if emergency:
                    listed = ", ".join(emergency[:8])
                    questions.append({
                        "question": f"Which emergency dentists are available in {city_display}?",
                        "answer": (
                            f"Emergency dentists in {city_display} include: "
                            + listed + f". {len(emergency)} dentists offer emergency services."
                        ),
                    })

            # ── Q8: Payment plans ──
            payment = [
                p["name"] for p in places
                if get_enriched_field(p, "payment_plans") is True
            ]
            if payment:
                listed = ", ".join(payment[:8])
                more = f" and {len(payment) - 8} more" if len(payment) > 8 else ""
                questions.append({
                    "question": f"Which {display} in {city_display} offer payment plans?",
                    "answer": (
                        f"{display_cap} in {city_display} that offer payment plans include: "
                        + listed + more + "."
                    ),
                })

            # ── Build FAQPage schema ──
            schema = {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": q["question"],
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text": q["answer"],
                        },
                    }
                    for q in questions
                ],
            }

            faq_obj = {
                "vertical": v_name,
                "vertical_display": config["display_name"],
                "city": city_slug,
                "city_display": city_display,
                "generated": datetime.now().strftime("%Y-%m-%d"),
                "total_businesses": len(places),
                "questions": questions,
                "schema": schema,
            }

            # Write to data directory so Astro can read at build time
            faq_path = DATA_DIR / v_name / city_slug / "faq.json"
            faq_path.parent.mkdir(parents=True, exist_ok=True)
            with open(faq_path, "w") as f:
                json.dump(faq_obj, f, indent=2)

            faq_count += 1

    console.print(f"  [green]faq.json[/green] — {faq_count} FAQ pages generated in data/")


# ── 6. Knowledge Graph ───────────────────────────────────────────────────────


def build_business_node(place: dict, v_name: str, schema_type: str, city_slug: str) -> dict:
    """Build a Schema.org node for a single business."""
    city_url = city_url_slug(city_slug)
    slug = slugify(place["name"])
    canonical = f"{SITE_DOMAIN}/{v_name}/{city_url}/{slug}/"

    node = {
        "@type": schema_type,
        "@id": canonical,
        "name": place["name"],
        "url": canonical,
        "address": {
            "@type": "PostalAddress",
            "streetAddress": place.get("address", ""),
        },
    }

    # Parse city/state from address
    addr = place.get("address", "")
    parts = addr.split(",")
    if len(parts) >= 3:
        node["address"]["addressLocality"] = parts[-3].strip() if len(parts) > 3 else parts[-2].strip()
        state_zip = parts[-2].strip() if len(parts) > 3 else parts[-1].strip()
        state = state_zip.split()[0] if state_zip else ""
        node["address"]["addressRegion"] = state

    loc = place.get("location", {})
    if loc.get("lat") and loc.get("lng"):
        node["geo"] = {
            "@type": "GeoCoordinates",
            "latitude": loc["lat"],
            "longitude": loc["lng"],
        }

    if place.get("phone"):
        node["telephone"] = place["phone"]
    if place.get("website"):
        node["sameAs"] = place["website"]

    rating = place.get("rating")
    if rating:
        node["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": rating,
            "reviewCount": place.get("review_count", 0),
        }

    hours = place.get("hours")
    if hours and isinstance(hours, dict):
        specs = []
        for day, time_range in hours.items():
            if not time_range or "closed" in time_range.lower():
                continue
            spec = {"@type": "OpeningHoursSpecification", "dayOfWeek": day}
            if " - " in time_range:
                opens, closes = time_range.split(" - ", 1)
                spec["opens"] = opens.strip()
                spec["closes"] = closes.strip()
            specs.append(spec)
        if specs:
            node["openingHoursSpecification"] = specs

    langs = get_enriched_field(place, "languages_spoken") or get_enriched_field(place, "languages")
    if langs and isinstance(langs, list):
        node["knowsLanguage"] = langs

    node["areaServed"] = {
        "@type": "City",
        "name": format_city_name(city_slug),
    }

    return node


def generate_knowledge_graph(output_dir: Path, all_data: dict) -> None:
    all_nodes = [
        {
            "@type": "Organization",
            "@id": f"{SITE_DOMAIN}/#organization",
            "name": SITE_NAME,
            "url": SITE_DOMAIN,
            "description": "AI-native local business directory with structured data for LLM consumption",
        }
    ]

    per_file_count = 0

    for v_name, v_data in sorted(all_data.items()):
        config = v_data["_config"]
        schema_type = config.get("schema_type", "LocalBusiness")

        for city_slug in sorted(k for k in v_data if k != "_config"):
            places = v_data[city_slug]
            city_nodes = []

            for place in places:
                node = build_business_node(place, v_name, schema_type, city_slug)
                all_nodes.append(node)
                city_nodes.append(node)

            # Per vertical+city file
            city_url = city_url_slug(city_slug)
            kg_dir = output_dir / "knowledge-graph" / v_name
            kg_dir.mkdir(parents=True, exist_ok=True)
            city_graph = {
                "@context": "https://schema.org",
                "@graph": city_nodes,
            }
            with open(kg_dir / f"{city_url}.jsonld", "w") as f:
                json.dump(city_graph, f, indent=2)
            per_file_count += 1

    # Master file
    master = {
        "@context": "https://schema.org",
        "@graph": all_nodes,
    }
    with open(output_dir / "knowledge-graph.jsonld", "w") as f:
        json.dump(master, f, indent=2)

    biz_count = len(all_nodes) - 1  # minus the Organization node
    console.print(
        f"  [green]knowledge-graph.jsonld[/green] — {biz_count} businesses, "
        f"1 master + {per_file_count} city files"
    )


# ── 7. IndexNow ──────────────────────────────────────────────────────────────


def generate_indexnow(output_dir: Path, all_data: dict) -> None:
    key = os.getenv("INDEXNOW_KEY", hashlib.md5(SITE_DOMAIN.encode()).hexdigest())

    # Write key verification file
    (output_dir / f"{key}.txt").write_text(key)

    # Collect all URLs
    urls = [f"{SITE_DOMAIN}/"]

    for v_name, v_data in sorted(all_data.items()):
        urls.append(f"{SITE_DOMAIN}/{v_name}/")
        for city_slug in sorted(k for k in v_data if k != "_config"):
            city_url = city_url_slug(city_slug)
            urls.append(f"{SITE_DOMAIN}/{v_name}/{city_url}/")
            urls.append(f"{SITE_DOMAIN}/{v_name}/{city_url}/faq/")
            for place in v_data[city_slug]:
                slug = slugify(place["name"])
                urls.append(f"{SITE_DOMAIN}/{v_name}/{city_url}/{slug}/")

    # Save URL list for reference
    (output_dir / ".indexnow-urls.txt").write_text("\n".join(urls))
    (output_dir / ".indexnow-key").write_text(key)

    console.print(f"  [green]IndexNow[/green] — key file + {len(urls)} URLs ready to submit")


def ping_indexnow(urls: list[str] = None) -> None:
    """Submit URLs to IndexNow API for instant Bing indexing."""
    output_dir = PROJECT_ROOT / "web" / "public"
    key_file = output_dir / ".indexnow-key"
    urls_file = output_dir / ".indexnow-urls.txt"

    if not key_file.exists():
        console.print("[red]No IndexNow key found. Run generate first.[/red]")
        return

    key = key_file.read_text().strip()
    if urls is None:
        if not urls_file.exists():
            console.print("[red]No URLs file found. Run generate first.[/red]")
            return
        urls = urls_file.read_text().strip().split("\n")

    host = SITE_DOMAIN.replace("https://", "").replace("http://", "")

    payload = json.dumps({
        "host": host,
        "key": key,
        "keyLocation": f"{SITE_DOMAIN}/{key}.txt",
        "urlList": urls[:10000],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.indexnow.org/indexnow",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            console.print(f"  [green]IndexNow pinged[/green] — {resp.status}, {len(urls)} URLs submitted")
    except Exception as e:
        console.print(f"  [yellow]IndexNow ping failed[/yellow] — {e}")
        console.print("  URLs saved to .indexnow-urls.txt for manual submission")


# ── Main ─────────────────────────────────────────────────────────────────────


GENERATORS = {
    "robots": generate_robots_txt,
    "llms": generate_llms_txt,
    "llms-full": generate_llms_full_txt,
    "sitemap": generate_sitemap_xml,
    "faq": generate_faq_data,
    "knowledge-graph": generate_knowledge_graph,
    "indexnow": generate_indexnow,
}


def run_all(output_dir: Path = None, only: str = None) -> None:
    """Generate all LLM optimization files."""
    if output_dir is None:
        output_dir = PROJECT_ROOT / "web" / "public"
    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[bold]{SITE_NAME} — LLM Optimization Layer[/bold]")
    console.print(f"Output: {output_dir}\n")

    all_data = load_all_data()

    if not all_data:
        console.print("[red]No data found. Run the fetch pipeline first.[/red]")
        return

    total = count_businesses(all_data)
    console.print(f"Loaded {total} businesses across {len(all_data)} verticals\n")

    if only:
        if only not in GENERATORS:
            console.print(f"[red]Unknown generator: {only}[/red]")
            console.print(f"Available: {', '.join(GENERATORS.keys())}")
            return
        GENERATORS[only](output_dir, all_data)
    else:
        for name, gen_func in GENERATORS.items():
            gen_func(output_dir, all_data)

    console.print(f"\n[bold green]LLM optimization layer complete.[/bold green]")


def main():
    parser = argparse.ArgumentParser(
        description="Generate LLM optimization files for AgentReady"
    )
    parser.add_argument("--output-dir", type=Path, help="Output directory (default: web/public)")
    parser.add_argument(
        "--data-dir", type=Path,
        help="Data directory to read from (default: data/). Accepts absolute path or relative to project root."
    )
    parser.add_argument(
        "--only",
        choices=list(GENERATORS.keys()),
        help="Generate only one file type",
    )
    parser.add_argument("--ping", action="store_true", help="Ping IndexNow after generating")

    args = parser.parse_args()

    # Override global DATA_DIR if --data-dir is specified
    if args.data_dir:
        global DATA_DIR
        data_dir_path = args.data_dir
        if not data_dir_path.is_absolute():
            data_dir_path = PROJECT_ROOT / data_dir_path
        DATA_DIR = data_dir_path
        console.print(f"[dim]Using data directory: {DATA_DIR}[/dim]")

    run_all(args.output_dir, args.only)

    if args.ping:
        console.print()
        ping_indexnow()


if __name__ == "__main__":
    main()
