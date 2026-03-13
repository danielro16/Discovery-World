#!/bin/bash
# ─────────────────────────────────────────────────────────
# run_pipeline.sh — Full pipeline: fetch → enrich → content → build
#
# Usage:
#   ./scripts/run_pipeline.sh dentists "Miami, FL"
#   ./scripts/run_pipeline.sh restaurants "Miami, FL"
# ─────────────────────────────────────────────────────────

set -e

VERTICAL=${1:?"Usage: ./scripts/run_pipeline.sh <vertical> <city>"}
CITY=${2:?"Usage: ./scripts/run_pipeline.sh <vertical> <city>"}
CITY_SLUG=$(echo "$CITY" | tr '[:upper:]' '[:lower:]' | tr ' ,' '_' | tr -d ',')

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AgentReady Pipeline"
echo "  Vertical: $VERTICAL"
echo "  City: $CITY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$(dirname "$0")/.."

# Step 1: Fetch places from Google
echo "📡 Step 1/4: Fetching businesses..."
python pipeline/fetch_places.py --vertical "$VERTICAL" --city "$CITY"

# Step 2: Enrich with website data
echo ""
echo "🔬 Step 2/4: Enriching data..."
python pipeline/enrich_data.py --vertical "$VERTICAL" --city "$CITY_SLUG" --limit 100

# Step 3: Generate blog content
echo ""
echo "📝 Step 3/4: Generating content..."
python pipeline/generate_content.py --vertical "$VERTICAL" --city "$CITY_SLUG" --count 5

# Step 4: Build static site
echo ""
echo "🏗️  Step 4/4: Building site..."
python pipeline/build_site.py --vertical "$VERTICAL" --city "$CITY_SLUG"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Pipeline complete!"
echo "  Site output: site/public/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
