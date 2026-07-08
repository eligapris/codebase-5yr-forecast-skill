# Data Sources Reference

This document defines the **canonical sources** the skill queries during Phase 3 (External Evidence Gathering), the **exact data points** to extract from each, and the **citation format** required for every entry in `evidence.json`.

The goal: any tool re-running this skill should be able to find the same data points from the same sources and arrive at the same scores.

---

## Citation format (mandatory)

Every entry in `evidence.json` follows this exact schema:

```json
{
  "evidence_id": "ev_001",
  "metric": "Python TIOBE rank, 5-year delta",
  "value": "rank 1, +2 positions since 2020",
  "numeric_value": 1,
  "unit": "rank",
  "source_name": "TIOBE Index",
  "source_url": "https://www.tiobe.com/tiobe-index/",
  "source_type": "tech_trend_index | adoption_signal | market_data | competitor_intel | ai_disruption_news",
  "retrieved_at": "2026-06-19T08:30:00Z",
  "retrieved_via": "web_search | web_reader | api | manual",
  "confidence": "high | medium | low",
  "confidence_rationale": "why this confidence level",
  "applies_to": ["trend_alignment.language_trajectory"],
  "notes": "any caveats, e.g., 'TIOBE weighting favors search engine mentions'"
}
```

The `applies_to` field is critical — it links the evidence to the specific sub-score it informs. The scoring script uses this to attach citations to each sub-score in the final report.

---

## Source priority

When multiple sources cover the same metric, prefer in this order:
1. Official reports (TIOBE, StackOverflow Survey, ThoughtWorks Tech Radar, GitHub Octoverse)
2. Registry statistics (npm, PyPI, Docker Hub, Maven Central, crates.io)
3. GitHub API (stars, commits, contributors)
4. Reputable analyst reports (Gartner, Forrester, IDC, Statista)
5. Established tech publications (InfoQ, The New Stack, TechCrunch for funding)
6. General web search (lowest confidence)

If only general web search results are available, mark confidence as `low`.

---

## Bucket A — Tech Trend Indexes

### A1. StackOverflow Developer Survey
- URL: `https://survey.stackoverflow.co/<year>/`
- Extract:
  - Primary language adoption % (current year + 5-year trend)
  - "Most Loved" / "Most Dreaded" rank for primary language
  - "Most Wanted" rank for primary language
  - Top frameworks used (for the project's primary framework)
  - Median salary for the primary language (proxy for demand)
- Confidence: high
- Cite as: `source_url` with the specific section anchor

### A2. ThoughtWorks Tech Radar
- URL: `https://www.thoughtworks.com/radar`
- Extract:
  - Current ring for each tech in the project's stack: Adopt / Trial / Assess / Hold
  - Whether the tech moved rings in the last 2 radars (rising/falling signal)
  - Any "Hold" ring entries — these are explicit deprecation signals
- Confidence: high (curated by senior engineers)
- Cite as: `https://www.thoughtworks.com/radar/technologies/<tech-name>`

### A3. GitHub Octoverse
- URL: `https://github.blog/news-insights/octoverse/`
- Extract:
  - Language ranking (top 25)
  - 5-year language growth rates
  - Top framework / library growth (relevant to the project)
  - Region-specific data if the project targets a specific geography
- Confidence: high

### A4. JetBrains State of Developer Ecosystem
- URL: `https://www.jetbrains.com/lp/devecosystem-<year>/`
- Extract:
  - Primary language adoption %
  - Framework adoption (specific to the project's stack)
  - Migration patterns (are developers moving toward or away from this stack?)
- Confidence: high
- Note: less frequent updates than StackOverflow; check publication year

### A5. TIOBE Index
- URL: `https://www.tiobe.com/tiobe-index/`
- Extract:
  - Current rank for primary language
  - 5-year rank delta
  - "Language of the Year" awards (proxy for momentum)
- Confidence: medium (TIOBE uses search engine mention weighting; not a pure adoption metric)

### A6. RedMonk Programming Language Rankings
- URL: `https://redmonk.com/sogrady/category/programming-languages/`
- Extract:
  - Current rank for primary language
  - 5-year rank delta
  - Top-20 trend commentary
- Confidence: medium (combines GitHub + StackOverflow data, but rankings are quarterly snapshots)

### A7. Google Trends (auxiliary)
- URL: `https://trends.google.com/`
- Extract:
  - 5-year interest-over-time curve for the project's primary tech
  - Regional interest (if geography matters)
- Confidence: low (interest ≠ adoption; useful as directional signal only)

---

## Bucket B — Adoption Signals

### B1. npm statistics (JavaScript / TypeScript projects)
- URL: `https://api.npmjs.org/downloads/point/last-week/<package>` for weekly downloads
- URL: `https://npm-stat.com/charts.html?package=<package>` for historical
- Extract:
  - Weekly download count
  - 3-year download CAGR (compute from monthly snapshots if available)
  - Dependent count (how many other packages depend on this)
- Confidence: high (registry ground truth)

### B2. PyPI statistics (Python projects)
- URL: `https://pypistats.org/api/packages/<package>/recent` for recent downloads
- URL: `https://pypistats.org/api/packages/<package>/overall` for historical
- Extract:
  - 30-day download total
  - 3-year download CAGR
  - Python version compatibility (legacy Python 2 = negative signal)
- Confidence: high

### B3. Docker Hub pulls (containerized projects)
- URL: `https://hub.docker.com/v2/repositories/<image>/`
- Extract:
  - Total pull count
  - Pull velocity (last 30 days vs prior 30 days)
- Confidence: medium (pulls include CI/CD; not pure user adoption)

### B4. Maven Central (JVM projects)
- URL: `https://search.maven.org/solrsearch/select?q=g:<group>&core=gav&rows=200`
- Extract:
  - Version count (proxy for maintenance activity)
  - Latest version release date
  - Popular version usage % (if available via mvncentral.io)
- Confidence: high

### B5. crates.io (Rust projects)
- URL: `https://crates.io/api/v1/crates/<crate>`
- Extract:
  - Recent downloads
  - 90-day download trend
  - Dependent crate count
- Confidence: high

### B6. GitHub star velocity
- Method: Use GitHub API to fetch star timestamps (`GET /repos/{owner}/{repo}/stargazers` with `Accept: application/vnd.github.v3.star+json`), then linear regression on cumulative stars vs time.
- Extract:
  - Current star count
  - Stars gained in last 12 months
  - Linear regression slope (stars/day)
  - 5-year projection (slope × 365 × 5)
- Confidence: high (direct GitHub API)
- Note: For popular repos, the API may paginate heavily; cap at 400 pages (10,000 stars) for the regression.

### B7. HackerNews mention frequency (auxiliary)
- URL: `https://hn.algolia.com/api/v1/search?query=<tech>&tags=story`
- Extract:
  - Total stories mentioning the tech in the last 12 months
  - Year-over-year delta
- Confidence: low (HN is a developer-mindshare proxy, not adoption)

---

## Bucket C — Market & Competitor

### C1. Market size reports
- Search queries:
  - `"<problem domain>" market size CAGR 2026`
  - `"<problem domain>" TAM forecast 2030`
  - `"<problem domain>" market report Gartner OR Forrester OR IDC`
- Sources to prioritize: Statista, Grand View Research, Markets and Markets, Gartner Magic Quadrants, Forrester Wave reports
- Extract:
  - Current TAM (in USD)
  - Projected TAM in 5 years
  - CAGR %
  - Segment breakdown if relevant
- Confidence: medium (analyst projections are notoriously optimistic — apply a 0.7 discount factor when noting them; do NOT apply the discount in the number itself, but record it in `notes`)

### C2. Competitor funding
- Search queries:
  - `"<problem domain>" startup funding Series A OR Series B 2024 OR 2025 OR 2026`
  - `"<competitor name>" funding round crunchbase`
- Sources: Crunchbase, PitchBook (if accessible), TechCrunch funding roundups
- Extract:
  - List of direct competitors (name, funding total, last round date, last round size)
  - Total funding in the space (last 24 months)
  - Number of new entrants (last 12 months)
- Confidence: high for funding totals; medium for "direct competitor" classification

### C3. M&A activity
- Search queries:
  - `"<problem domain>" acquisition 2024 OR 2025 OR 2026`
  - `"<problem domain>" merger consolidation`
- Extract:
  - Recent acquisitions (acquirer, target, deal size if disclosed)
  - Acquirer profile (strategic buyer vs PE vs aquihire)
- Confidence: high
- Note: Heavy M&A activity is a double signal — it can mean the space is heating up (good) OR consolidating with incumbents winning (bad for new entrants). Capture both interpretations in `notes`.

### C4. AI-disruption news (critical)
- Search queries:
  - `"<problem domain>" AI automation replace`
  - `"<problem domain>" LLM GPT Claude`
  - `"<problem domain>" generative AI workflow`
  - `"<problem domain>" "no longer needed" AI`
- Extract:
  - Number of articles in last 12 months about AI disrupting this space
  - Specific AI tools mentioned as replacements
  - Any case studies of companies replacing the category with AI
- Confidence: high (this is the dominant risk axis — over-invest in gathering this)
- Note: This evidence directly drives the `feature_automatability_pct` sub-score. Be thorough.

### C5. Regulatory shifts
- Search queries:
  - `"<problem domain>" regulation 2026`
  - `"<problem domain>" compliance mandate`
  - `"<problem domain>" GDPR OR CCPA OR HIPAA OR "AI Act"`
- Extract:
  - Upcoming regulations (effective date, scope, who's affected)
  - Pending legislation
  - Recent enforcement actions
- Confidence: high for enacted regulations; medium for pending

### C6. Buyer behavior shifts
- Search queries:
  - `"<problem domain>" buyer trend survey`
  - `"<problem domain>" procurement`
  - `"<problem domain>" budget 2026`
- Extract:
  - Survey data on buyer priorities
  - Budget trends
  - Procurement cycle changes
- Confidence: medium

---

## Cross-source validation

For high-stakes scores (the `feature_automatability_pct` and `tam_cagr_pct` sub-scores), require at least 2 independent sources. If only 1 source is available:

- Mark confidence as `medium` (not `high`)
- Note the single-source dependency in `confidence_rationale`
- The scoring script will widen the confidence interval automatically (see `references/scoring-methodology.md` § 8)

For the AI-disruption axis, also do a "negative search" — search for evidence that AI *cannot* disrupt this space (e.g., regulatory barriers, physical-world dependencies). If found, record it as evidence with `applies_to: ["ai_disruption_exposure.feature_automatability_pct"]` and a note explaining the negative direction.

---

## Handling missing data

If a critical source is unreachable or returns no data:

1. Record the attempt in `evidence.json` with `value: null`, `confidence: "none"`, and `notes: "Source unreachable on <date>; retry recommended"`.
2. Use the next-best source from the same bucket.
3. If no alternative exists, set the corresponding sub-score to 50 (neutral) and mark it `[NEUTRAL-DEFAULT — evidence gap]` in the report.
4. The script's confidence interval for that sub-score becomes ±50 (maximum uncertainty).

This explicit gap handling is what lets the skill produce *honest* output even when the internet is uncooperative.

---

## Caching and re-runs

To support reproducibility across tools:

- All `evidence.json` entries include `retrieved_at` timestamps.
- A re-run within 24 hours may reuse the same evidence (note the reuse in the new run's metadata).
- A re-run after 7 days should re-fetch all sources (data drifts).
- The JSON bundle includes a `evidence_freshness` field: `fresh` (<24h), `recent` (1–7 days), `stale` (>7 days).

This lets a reviewer compare two runs and identify whether score differences are due to genuine model disagreement or simply newer data.
