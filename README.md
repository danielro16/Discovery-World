# 🦷 AgentReady — AI-Optimized Local Business Directory

## Vision
The bridge between local businesses and AI discovery. Today: get businesses found by LLMs. Tomorrow: become the MCP infrastructure agents use to operate in the real world.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  AgentReady                       │
├─────────────────────────────────────────────────┤
│                                                   │
│  PIPELINE (automated, runs weekly)               │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ Google   │→ │ Enrich   │→ │ Generate     │  │
│  │ Places   │  │ (Claude  │  │ Blog Content │  │
│  │ API      │  │  API)    │  │ (Claude API) │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
│       ↓              ↓              ↓            │
│  ┌──────────────────────────────────────────┐   │
│  │         Structured JSON Database          │   │
│  └──────────────────────────────────────────┘   │
│       ↓                                          │
│  OUTPUTS                                         │
│  ┌──────────────┐  ┌───────────┐  ┌──────────┐ │
│  │ Directory    │  │ Blog      │  │ MCP      │ │
│  │ Website     │  │ Posts     │  │ Server   │ │
│  │ (per biz)   │  │ (weekly)  │  │ (future) │ │
│  └──────────────┘  └───────────┘  └──────────┘ │
└─────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up API keys
```bash
cp .env.example .env
# Edit .env with your keys:
# GOOGLE_PLACES_API_KEY=your_key
# ANTHROPIC_API_KEY=your_key
```

### 3. Fetch businesses
```bash
# Fetch dentists in Miami
python pipeline/fetch_places.py --vertical dentists --city "Miami, FL" --radius 30000

# Fetch restaurants in Miami  
python pipeline/fetch_places.py --vertical restaurants --city "Miami, FL" --radius 30000
```

### 4. Enrich data from business websites
```bash
python pipeline/enrich_data.py --vertical dentists --city miami
```

### 5. Generate blog content
```bash
python pipeline/generate_content.py --vertical dentists --city miami --count 5
```

### 6. Build the directory site
```bash
python pipeline/build_site.py --vertical dentists --city miami
```

## Vertical Configs

Each vertical has a config in `verticals/`. To add a new vertical:
1. Copy `verticals/dentists.json` 
2. Modify fields, categories, and content prompts
3. Run the pipeline with `--vertical your_new_vertical`

## Costs (estimated monthly)
- Google Places API: $0-50 (free tier covers initial launch)
- Claude API: $10-30 
- Hosting: $6-12 (DigitalOcean/Vercel)
- **Total: ~$20-100/month**

## Roadmap
- [x] Phase 1: Data pipeline + directory (Week 1-2)
- [ ] Phase 2: Blog content generator (Week 3)
- [ ] Phase 3: Launch Miami dentists (Week 4)
- [ ] Phase 4: Add more cities (Month 2-3)
- [ ] Phase 5: Add more verticals (Month 3-6)
- [ ] Phase 6: MCP Server layer (Month 6+)
