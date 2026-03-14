# LLM-Native Development Principles

AgentReady is AI-native. Every piece of content, markup, and structure is designed to be found, understood, and cited by LLMs. The primary consumer of our content is an AI agent answering a user's question like "best dentist in Miami" or "gym near Brickell that has a pool".

## Core Truth

When a user asks ChatGPT, Perplexity, or Claude a question about local businesses, the LLM needs:
1. A direct answer to the exact question asked
2. Structured data it can cite with confidence
3. A source URL it can link to

Every page we build must satisfy all three.

## Checklist: Before Any Page or Feature Ships

- [ ] **Schema.org JSON-LD** — Business pages use the vertical's schema_type. Listings use ItemList. FAQs use FAQPage.
- [ ] **FAQ coverage** — Is the content reflected in FAQ pages? Run `python pipeline/llm_optimize.py --only faq`
- [ ] **llms-full.txt** — Will the data appear in the full text dump? Run `python pipeline/llm_optimize.py --only llms-full`
- [ ] **Knowledge graph** — Is it in knowledge-graph.jsonld? Run `python pipeline/llm_optimize.py --only knowledge-graph`
- [ ] **Sitemap** — Is the URL in sitemap.xml? Run `python pipeline/llm_optimize.py --only sitemap`
- [ ] **Static HTML** — All content renders without JavaScript. No client-side rendering. Crawlers don't execute JS.
- [ ] **Q&A structure** — Content is structured as questions and answers where possible. Headings are phrased as questions users would ask.
- [ ] **IndexNow** — After deploy, ping: `python pipeline/llm_optimize.py --ping`

## Content Patterns

### 1. Answer First
The first paragraph of every page and section answers the question directly. LLMs extract the first relevant sentence.

**Do:** "The best-rated dentist in Miami is Dental Design Smile with a 4.9/5 rating from 5,452 reviews."
**Don't:** "Miami is a vibrant city with many dental practitioners serving the community..."

### 2. Natural Query Phrasing
Write headings using the exact words a user types into ChatGPT.

**Do:** "Best dentist in Miami", "Dentists that accept Delta Dental in Miami"
**Don't:** "Top dental practitioners in the Miami metropolitan area"

### 3. One Page = One Primary Question
Every page has one primary question it answers. URL, title, H1, and first paragraph all align:
- Business page: "Tell me about {business} in {city}"
- Listing page: "What are the best {vertical} in {city}?"
- FAQ page: Multiple questions, each self-contained with its own answer

### 4. Data Completeness = Visibility
An LLM cannot cite what is not there. Every missing field (phone, hours, insurance, languages) is a missed citation opportunity. Profile completeness directly correlates with how often a business gets recommended by AI.

### 5. Structured Data Mirrors Natural Language
Every Schema.org property maps to a question:
- `aggregateRating` → "What is the rating of X?"
- `telephone` → "What is the phone number of X?"
- `openingHoursSpecification` → "What are the hours of X?"
- `knowsLanguage` → "Does X speak Spanish?"
- `acceptedPaymentMethod` → "Does X accept insurance?"

## LLM Optimization Layer

Run `python pipeline/llm_optimize.py` to regenerate all 7 file types:

| File | Purpose |
|------|---------|
| `robots.txt` | Welcomes AI crawlers by name (GPTBot, ClaudeBot, PerplexityBot, etc.) |
| `llms.txt` | Machine-readable site overview following llmstxt.org standard |
| `llms-full.txt` | Complete text dump of all businesses — one file an LLM can read entirely |
| `sitemap.xml` | URL index with priorities and last-modified dates |
| `faq.json` (per city) | Structured Q&A with FAQPage schema, rendered at `/{vertical}/{city}/faq/` |
| `knowledge-graph.jsonld` | Schema.org graph of all businesses |
| `IndexNow` | Instant Bing indexing (ChatGPT uses Bing) |

## When Adding a New Vertical

1. Create `verticals/{name}.json` with schema_type, fields_to_extract
2. Fetch and enrich data into `data/{name}/{city}/places.json`
3. Run `python pipeline/llm_optimize.py` to regenerate all LLM files
4. Verify: llms.txt, llms-full.txt, sitemap.xml, knowledge-graph.jsonld all include the new vertical

## When Adding a New City

1. Fetch data for all verticals in the new city
2. Run `python pipeline/llm_optimize.py`
3. Verify FAQ pages are generated for every vertical+city combo
4. Ping IndexNow: `python pipeline/llm_optimize.py --ping`

## Key Files

- `pipeline/llm_optimize.py` — Generates the entire LLM optimization layer
- `pipeline/config.py` — Site constants (SITE_NAME, SITE_DOMAIN, DATA_DIR)
- `web/src/utils/data.ts` — Astro data loading (includes getFaq())
- `web/src/pages/[vertical]/[city]/faq.astro` — FAQ page template
- `data/{vertical}/{city}/places.json` — Source business data
- `verticals/{name}.json` — Vertical config with schema_type and fields_to_extract
