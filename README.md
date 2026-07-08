# Codebase 5-Year Forecast

A **Cursor Agent Skill** that produces a reproducible, evidence-backed **5-year survival and moat forecast** for any codebase, app, or product idea.

The skill is deliberately **brutal and quantitative**. It does not write flattering essays — it runs fixed formulas on gathered evidence and delivers a clinical verdict: *Durable*, *Eroding*, *At Risk*, or *Terminal*.

---

## What it does

Given a local codebase path, a GitHub URL, or a project pitch, the skill:

1. **Scans** the codebase for factual metrics (languages, LOC, dependencies, test coverage proxies, tech-debt signals).
2. **Gathers external evidence** from tech trend indexes, adoption signals, and market/competitor data.
3. **Scores** the project on four axes using a deterministic Python engine — not LLM judgment.
4. **Projects** moat durability year-by-year (Y0–Y5) with bull/base/bear scenarios.
5. **Delivers** a PDF report + machine-readable JSON bundle, plus a pivot roadmap if the verdict is negative.

### Core principle

> **The LLM gathers data and writes the narrative; deterministic Python scripts do the scoring.**

Same inputs → same scores → same verdict, every time — even across different models or tools.

---

## When to use it

Invoke this skill when you want:

- A long-horizon outlook on a codebase, app, product, or technical idea
- A **moat / defensibility** analysis with quantified scoring
- An **AI-disruption risk** assessment for a software product
- A **pivot recommendation** backed by data
- Answers to questions like *"Will my project still be relevant in 5 years?"* or *"Should I keep building this?"*

**Trigger phrases:** forecast, project, predict the future of, assess longevity, evaluate durability, is my project still relevant, should I pivot, what's the moat of, 5-year projection, moat analysis, AI disruption risk, tech stack longevity.

**Do not use for:** short-term roadmap planning, bug triage, code review, single-feature cost estimates, or general architecture advice.

---

## Inputs accepted

The skill auto-detects which inputs are present. Multiple inputs can be combined.

| Input | How it's detected | What it yields |
|-------|-------------------|----------------|
| **Local code path** | Directory exists on disk | File counts, languages, dependencies, complexity proxies, test-coverage proxy, tech-debt indicators |
| **GitHub URL** | `github.com/...` URL | Shallow clone + local scan; stars, last commit, contributors via GitHub API when accessible |
| **Project pitch** | Prose description without code | Problem-domain analysis only; technical-moat scores are degraded and flagged as lower confidence |

---

## How it works

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Cursor Agent (LLM)                       │
│  Intake → Evidence gathering → Fill scoring_input.json → Narrative│
└────────────┬───────────────────────────────┬────────────────────┘
             │                               │
             ▼                               ▼
   codebase_scanner.py              moat_calculator.py
   (factual metrics)                (deterministic scoring)
             │                               │
             └───────────────┬───────────────┘
                             ▼
                    generate_report.py
                    (PDF + JSON bundle)
```

The LLM **never overrides** numerical output from `moat_calculator.py`. If the script says Y5 = 34, the report says Y5 = 34. The LLM explains *why* 34, not whether 34 is "fair."

### Six-phase workflow

| Phase | Name | Actor | Output |
|-------|------|-------|--------|
| 1 | Intake & Scoping | LLM | Problem statement, scoped project understanding |
| 2 | Codebase Scan | `codebase_scanner.py` | `scan.json` |
| 3 | External Evidence | LLM + web search | `evidence.json` |
| 4 | Deterministic Scoring | `moat_calculator.py` | `scores.json` |
| 5 | Pivot Roadmap | LLM (if negative verdict) | Pivot directions or defend-and-extend plan |
| 6 | Report Generation | `generate_report.py` | PDF + JSON bundle |

Intermediate artifacts are persisted to a `forecast_work/` directory so the full chain is auditable.

---

## Scoring model

### Four axes

The composite **Moat Durability Score (M₀)** is a weighted sum of four axes:

| Axis | Weight | Direction |
|------|--------|-----------|
| Technical Moat | 30% | Higher is better |
| Trend Alignment | 20% | Higher is better |
| Market & Demand | 25% | Higher is better |
| AI Disruption Exposure | 25% (inverted) | Lower exposure is better |

```
M₀ = 0.30 × TechnicalMoat
   + 0.20 × TrendAlignment
   + 0.25 × MarketDemand
   + 0.25 × (100 − AIDisruptionExposure)
```

### Sub-scores

Each axis breaks down into sub-scores (0–100) filled by the LLM based on evidence, per rubrics in [`references/scoring-methodology.md`](references/scoring-methodology.md):

**Technical Moat:** code complexity, IP/novelty, switching costs, network effects, scale advantage.

**Trend Alignment:** language trajectory, framework trajectory, architecture pattern adoption, skill demand trend.

**Market & Demand:** TAM CAGR, buyer alignment, regulatory environment, competitive density.

**AI Disruption Exposure:** feature automatability, proprietary data dependency, UX commoditization, workflow complexity.

Every sub-score must cite at least one evidence entry. Unsourced assertions are excluded from scoring.

### Decay projection

Moat decays exponentially over 5 years, driven primarily by AI exposure:

```
λ = (AIDisruptionExposure / 100) × 0.40
M(t) = M₀ × e^(−λ × t)    for t = 0, 1, 2, 3, 4, 5
```

Three scenarios are projected and probability-weighted:

| Scenario | Weight | Adjustments |
|----------|--------|-------------|
| Base | 50% | Median evidence values |
| Bull | 25% | Slower AI disruption (λ × 0.6), +10 market demand, +5 trend alignment |
| Bear | 25% | Faster AI disruption (λ × 1.5), −15 market demand, −10 trend alignment |

The headline **Y5 score** is the expected value: `E[M(5)] = 0.25·M_bull(5) + 0.50·M_base(5) + 0.25·M_bear(5)`.

### Verdict thresholds

| E[M(5)] | Verdict | Action |
|---------|---------|--------|
| ≥ 70 | **Durable — Defend & Extend** | 3–5 moat-reinforcement moves |
| 50–69 | **Eroding — Reinforce or Niche** | Reinforcement plan + niche-down options |
| 30–49 | **At Risk — Pivot Required** | Full pivot roadmap (2–3 ranked directions) |
| < 30 | **Terminal — Sunset or Radical Pivot** | Radical pivot roadmap + sunset timeline |

Full formulas, rubrics, and worked examples: [`references/scoring-methodology.md`](references/scoring-methodology.md).

---

## External evidence sources

Phase 3 queries three evidence buckets. Every data point is recorded with source URL, retrieval timestamp, confidence level, and which sub-score it informs.

**Bucket A — Tech Trend Indexes**
- StackOverflow Developer Survey
- ThoughtWorks Tech Radar
- GitHub Octoverse
- JetBrains State of Developer Ecosystem
- TIOBE Index
- RedMonk Programming Language Rankings

**Bucket B — Adoption Signals**
- Package registry stats (npm, PyPI, Docker Hub, Maven Central, crates.io)
- GitHub star velocity
- HackerNews mention frequency

**Bucket C — Market & Competitor**
- Market size / TAM / CAGR searches
- Competitor funding and M&A activity
- AI-disruption news in the problem domain
- Regulatory shifts

Full source list and citation schema: [`references/data-sources.md`](references/data-sources.md).

---

## Outputs

### PDF report sections

1. **Executive Verdict** — verdict, Y5 score, decay curve chart, 3-bullet rationale
2. **Moat Scorecard** — 4 axes with sub-scores, radar chart, evidence citations
3. **Year-by-Year Projection** — Y1 through Y5 with milestones and threat events
4. **Scenario Analysis** — bull / base / bear overlay chart
5. **AI Disruption Deep-Dive** — per-feature automatability table
6. **Pivot Roadmap** or **Defend & Extend Plan** (depending on verdict)
7. **Appendix A: Evidence Index** — every data point with source and retrieval date
8. **Appendix B: Calculation Trace** — exact arithmetic performed by the scripts

### JSON bundle

Machine-readable output conforming to [`assets/report_schema.json`](assets/report_schema.json). Includes all scores, evidence, calculations, citations, and an `input_hash` (SHA-256) for reproducibility verification.

Two runs with the same `scoring_input.json` produce byte-identical `scores.json` (modulo timestamps).

---

## Repository structure

```
codebase-5yr-forecast/
├── SKILL.md                          # Agent instructions (primary skill definition)
├── README.md                         # This file — human-facing overview
├── references/
│   ├── scoring-methodology.md        # 4-axis scorecard, weights, decay math, verdict thresholds
│   ├── data-sources.md               # Canonical sources, citation format, extraction rules
│   ├── pivot-roadmap.md              # Negative-verdict playbook and pivot archetypes
│   └── reproducibility-protocol.md   # Override protocol, confidence math, drift detection
├── scripts/
│   ├── codebase_scanner.py           # Factual codebase metrics (Phase 2)
│   ├── moat_calculator.py            # Deterministic scoring engine (Phase 4)
│   └── generate_report.py            # PDF + JSON bundle generator (Phase 6)
└── assets/
    └── report_schema.json            # JSON schema for the output bundle
```

---

## Scripts reference

### `codebase_scanner.py`

Extracts factual metrics from a codebase. No LLM judgment.

```bash
python scripts/codebase_scanner.py /path/to/codebase > scan.json
python scripts/codebase_scanner.py /path/to/codebase --output scan.json
python scripts/codebase_scanner.py --version
```

**Outputs:** languages, LOC, frameworks, dependencies, test ratios, tech-debt proxies (TODO/FIXME counts), CI/license/README presence, last commit date.

### `moat_calculator.py`

Deterministic scoring engine. Canonical implementation of `scoring-methodology.md`.

```bash
python scripts/moat_calculator.py scoring_input.json > scores.json
python scripts/moat_calculator.py scoring_input.json --monte-carlo > scores.json
python scripts/moat_calculator.py --validate scoring_input.json
python scripts/moat_calculator.py --version
```

**Outputs:** axis scores, composite M₀, decay constant λ, Y0–Y5 projections, scenario analysis, verdict, confidence intervals, calculation trace, input hash.

### `generate_report.py`

Builds the final PDF and JSON bundle from script outputs and LLM narrative.

```bash
python scripts/generate_report.py \
  --scores scores.json \
  --scan scan.json \
  --evidence evidence.json \
  --scoring-input scoring_input.json \
  --narrative narrative.json \
  --output-dir ./output/
```

**Dependencies:** Python 3, `matplotlib`, `numpy`, `reportlab`.

---

## Reproducibility

This skill is designed so different LLMs and tools arrive at the **same numerical conclusion** when given the same evidence.

| Layer | Guarantee |
|-------|-----------|
| **Deterministic scoring** | All numbers come from `moat_calculator.py`; LLM never hand-edits scores |
| **Evidence versioning** | Every data point has `retrieved_at`, `source_url`, and confidence level |
| **Input hashing** | SHA-256 hash of `scoring_input.json` written to output for verification |
| **Override protocol** | LLM disagreements are recorded explicitly, never silent (see `reproducibility-protocol.md`) |
| **Confidence intervals** | Axis scores include ± ranges; Monte Carlo available via `--monte-carlo` |

Full protocol: [`references/reproducibility-protocol.md`](references/reproducibility-protocol.md).

---

## Tone and voice

The skill honors a "dead truth backed by statistics" mandate:

- **No hedging.** Forbidden: "it depends", "might be", "could potentially", "remains to be seen".
- **No flattery.** Y5 = 22 means *Terminal* — not "challenging but workable."
- **Every claim has a number or citation.** Unsourced claims are marked `[UNSOURCED — confidence: low]` and excluded from scoring.
- **Lead with the verdict.** Executive summary opens with the verdict, not the methodology.
- **Clinical register.** Example: *"Moat score: 23/100. Primary risk: AI commoditization (87% likelihood by Y3). Verdict: pivot required."*

---

## Edge cases

| Situation | Behavior |
|-----------|----------|
| Tiny codebase (<100 LOC) | Low confidence on technical moat; report header notes insufficient volume |
| No external evidence found | All sub-scores default to 50 (neutral); header reads **EVIDENCE-GAP MODE** |
| Pitch only (no code) | Technical moat derived from described architecture; confidence capped at medium |
| Private / unclonable GitHub repo | Falls back to pitch mode; noted in report |
| Scoring input fails validation | Script exits non-zero with clear error; fix input and re-run |

---

## Using the skill in Cursor

1. Install or place this skill in your Cursor skills directory.
2. Ask the agent to forecast a project — e.g.:
   - *"Run a 5-year forecast on ~/my-app"*
   - *"What's the moat of https://github.com/org/repo?"*
   - *"Should I pivot? Here's my product idea: …"*
3. The agent reads `SKILL.md`, runs the 6-phase workflow, and delivers the PDF + JSON paths with the headline verdict.

For agents: read `SKILL.md` first, then `references/scoring-methodology.md`, `references/data-sources.md`, and `references/reproducibility-protocol.md` before starting. Read `references/pivot-roadmap.md` only if the verdict triggers Phase 5.

---

## License

Part of the eligapris Cursor skills collection. See repository for license details.
