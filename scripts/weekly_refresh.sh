#!/bin/bash
# ─────────────────────────────────────────────────────────
# weekly_refresh.sh — Weekly content refresh for all verticals
#
# Add to crontab for automation:
#   0 6 * * 1 /path/to/scripts/weekly_refresh.sh >> /var/log/agentready.log 2>&1
#
# This runs every Monday at 6 AM
# ─────────────────────────────────────────────────────────

set -e

cd "$(dirname "$0")/.."

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AgentReady Weekly Refresh"
echo "  $(date)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Define active verticals and cities
declare -A VERTICALS
VERTICALS[dentists]="miami_fl"
# Uncomment as you expand:
# VERTICALS[restaurants]="miami_fl"
# VERTICALS[gyms]="miami_fl"
# VERTICALS[attorneys]="miami_fl"
# VERTICALS[therapists]="miami_fl"

for VERTICAL in "${!VERTICALS[@]}"; do
    CITY="${VERTICALS[$VERTICAL]}"
    
    echo ""
    echo "── Refreshing: $VERTICAL / $CITY ──"
    
    # Generate 5 new blog posts per vertical per week
    python pipeline/generate_content.py --vertical "$VERTICAL" --city "$CITY" --count 5
    
    # Rebuild the site
    python pipeline/build_site.py --vertical "$VERTICAL" --city "$CITY"
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Weekly refresh complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
