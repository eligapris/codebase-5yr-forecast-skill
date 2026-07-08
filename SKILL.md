---
name: codebase-5yr-forecast
description: Performs a data-driven 5-year survival and moat forecast for any codebase, app, or product idea. Analyzes code, identifies the project's defensible moat, quantifies AI-disruption exposure, projects year-by-year decay curves plus bull/base/bear scenarios, and produces a pivot roadmap if the verdict is negative. Use this skill whenever the user asks to "forecast", "project", "predict the future of", "assess longevity of", "evaluate durability of", "is my project still relevant", "should I pivot", "what's the moat of", or otherwise wants a strategic, evidence-backed, multi-year outlook on a codebase, app, or technical product. Also trigger when the user mentions "5-year projection", "moat analysis", "AI disruption risk", or "tech stack longevity" — even if they don't explicitly use the word "forecast". The skill is deliberately brutal and quantitative; do not soften its verdicts.
---

# Codebase 5-Year Forecast Skill

## What this skill does

Given a codebase, a GitHub URL, or a project pitch, this skill produces a **reproducible, evidence-backed 5-year forecast** of the project's defensibility. The output is a clinical, quantified verdict — not a flattering essay — that survives being re-run by different models or tools and arrives at the same numerical conclusion.

The core principle: **the LLM gathers data and writes the narrative; a deterministic Python script does the scoring.** Same inputs → same scores → same verdict, every time.

## When to invoke

Trigger this skill when the user wants any of:
- A long-horizon (multi-year) outlook on a codebase, app, product, or technical idea
- A moat / defensibility analysis with quantified scoring
- An AI-disruption risk assessment for a software product
- A pivot recommendation backed by data
- A "will my project still be relevant in N years" question
- A "should I keep building this" strategic review

Do **not** invoke for: short-term roadmap planning, bug triage, code review, single-feature cost estimates, or general architecture advice. Those are different tasks.

## Inputs accepted (auto-detected)

The skill accepts any one or more of the following. If multiple are provided, it uses all of them.

| Input type | How to detect | What it yields |
|------------|---------------|----------------|
| Local code path | User gives a directory that exists on disk | File counts, languages, dependencies, complexity proxies, test-coverage proxy, tech-debt indicators |
| GitHub URL | User gives a `github.com/...` URL | `git clone --depth 1` to a temp dir, then run the local scanner; also pull stars/last-commit/contributors from the GitHub API if accessible |
| Project pitch | User gives a prose description without code | Used for problem-domain analysis only; scoring is run on the pitch-derived feature inventory |

If only a pitch is provided, the technical-moat axis scores are degraded and the report flags this as a confidence reduction (see `references/reproducibility-protocol.md`).

## Workflow (6 phases, executed in order)

### Phase 1 — Intake & Scoping

1. Detect which input types are present.
2. If a GitHub URL is given, clone it to `/tmp/forecast-repo-<timestamp>/`.
3. Read the project's README, package manifests (`package.json`, `requirements.txt`/`pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml`, `Gemfile`, etc.), and a sample of source files to understand what the project **does** and **how**.
4. Produce a one-paragraph problem statement in the user's words (e.g., "This is a CLI tool that converts CSV files to Parquet for data engineers who don't want to write PySpark boilerplate"). This anchors every later judgment.

### Phase 2 — Codebase Scan

Run `python scripts/codebase_scanner.py <path>` (see `scripts/codebase_scanner.py`). It outputs a JSON object with:

- `languages` — map of language → % of codebase
- `primary_language`, `secondary_languages`
- `frameworks` — list of detected frameworks with versions
- `loc` — total lines of non-comment, non-blank code
- `file_count` — by type
- `dependency_count`, `dependencies` — list with pinned versions
- `test_file_count`, `test_to_source_ratio`
- `todo_count`, `fixme_count` — tech-debt proxies
- `last_commit_date` (if `.git` present)
- `avg_file_size`, `largest_file_loc` — complexity proxies
- `readme_present`, `license_present`, `ci_present`

This is **factual** data; no LLM judgment here. Save to `scan.json`.

### Phase 3 — External Evidence Gathering

Use `web-search` and `web-reader` skills to gather evidence across three buckets. See `references/data-sources.md` for the full source list and the exact data points to extract from each.

**Bucket A — Tech Trend Indexes:**
- StackOverflow Developer Survey (current year + 5-year trend for the primary language/framework)
- ThoughtWorks Tech Radar (current adoption ring: Adopt/Trial/Assess/Hold)
- GitHub Octoverse (language ranking + growth)
- JetBrains State of Developer Ecosystem
- TIOBE Index (current rank + 5-year delta)
- RedMonk Programming Language Rankings

**Bucket B — Adoption Signals:**
- npm download trends (if JS/TS), PyPI stats (if Python), Docker Hub pulls (if containerized), Maven Central (if JVM), crates.io (if Rust)
- GitHub star velocity for the primary frameworks (linear regression on stars over time)
- HackerNews mention frequency (proxy for developer mindshare)

**Bucket C — Market & Competitor:**
- Web search for the problem domain + "market size", "TAM", "CAGR"
- Competitor funding rounds (Crunchbase-style searches)
- M&A activity in the space
- AI-disruption news (search "<problem domain> AI automation" / "<problem domain> LLM replace")
- Regulatory shifts (search "<problem domain> regulation 2026")

For every data point collected, record:
```json
{
  "metric": "string describing what was measured",
  "value": number or string,
  "source": "URL or publication name",
  "retrieved_at": "ISO 8601 timestamp",
  "confidence": "high|medium|low",
  "notes": "any caveats"
}
```

Save all evidence to `evidence.json`. **Every score in the final report must trace back to at least one evidence entry.** Unsourced assertions are forbidden.

### Phase 4 — Deterministic Scoring (THE REPRODUCIBILITY CORE)

Construct the scoring input dict per `references/scoring-methodology.md`. The dict has this shape:

```json
{
  "project_name": "...",
  "scan": { ... from Phase 2 ... },
  "evidence": { ... from Phase 3 ... },
  "axis_inputs": {
    "technical_moat": {
      "code_complexity_score": 0-100,
      "ip_score": 0-100,
      "switching_cost_score": 0-100,
      "network_effects_score": 0-100,
      "scale_advantage_score": 0-100
    },
    "trend_alignment": {
      "language_trajectory": -100 to +100,
      "framework_trajectory": -100 to +100,
      "architecture_pattern_adoption": 0-100,
      "skill_demand_trend": -100 to +100
    },
    "market_demand": {
      "tam_cagr_pct": number,
      "buyer_alignment_score": 0-100,
      "regulatory_score": -100 to +100,
      "competitive_density_score": 0-100
    },
    "ai_disruption_exposure": {
      "feature_automatability_pct": 0-100,
      "proprietary_data_dependency_score": 0-100,
      "ux_commoditization_score": 0-100,
      "workflow_complexity_score": 0-100
    }
  },
  "scenario_adjustments": {
    "bull": { ...overrides... },
    "base": {},
    "bear": { ...overrides... }
  }
}
```

The LLM fills in each 0-100 sub-score based on the evidence (and **must cite** which evidence entries drove each score — see `references/scoring-methodology.md` for rubrics). Once the dict is complete, run:

```bash
python scripts/moat_calculator.py scoring_input.json > scores.json
```

The script:
- Computes each axis score using fixed weights (documented in `references/scoring-methodology.md`)
- Computes the composite Moat Durability Score (M₀)
- Computes the decay constant λ from AI exposure
- Projects M(t) = M₀ · e^(-λt) for t = 0, 1, 2, 3, 4, 5
- Runs the same projection under bull / base / bear scenario adjustments
- Assigns the verdict using fixed thresholds

**Critical rule: the LLM NEVER overrides or hand-edits the script's numerical output.** If the script says Y5 = 34, the report says Y5 = 34. The LLM's job is to explain *why* 34, not to argue with it.

### Phase 5 — Pivot Roadmap (only if verdict is negative)

If the verdict is "At Risk — Pivot Required" (Y5 < 50) or "Terminal" (Y5 < 30), generate a full pivot roadmap per `references/pivot-roadmap.md`. The roadmap includes:

- 2-3 ranked pivot directions (each with a target segment, tech migration path, and 18-month milestones)
- Resource cost estimate (engineer-months, infra cost, opportunity cost)
- Success metrics with explicit thresholds
- A "kill switch" criterion — what measured outcome triggers abandonment of the pivot

If the verdict is "Durable" or "Eroding", skip the roadmap and produce a "defend & extend" plan instead (3-5 specific moat-reinforcement moves with priorities).

### Phase 6 — Report Generation

Run `python scripts/generate_report.py scores.json scan.json evidence.json --output-dir /home/z/my-project/download/`. This produces:

1. `<project>_5yr_forecast.pdf` — the human-facing report (multi-section, with charts)
2. `<project>_5yr_forecast.json` — the machine-readable bundle (all scores, all evidence, all calculations, all citations) for downstream tooling

The PDF sections (in order):
1. **Executive Verdict** — one page, the verdict, the Y5 score, the decay curve chart, and a 3-bullet "why"
2. **Moat Scorecard** — the 4 axes with sub-scores, radar chart, and evidence citations
3. **Year-by-Year Projection** — Y1 through Y5 with milestones and threat events
4. **Scenario Analysis** — bull / base / bear overlay chart with probability weights
5. **AI Disruption Deep-Dive** — per-feature automatability table
6. **Pivot Roadmap** (or "Defend & Extend Plan" if positive verdict)
7. **Appendix A: Evidence Index** — every data point, source, retrieval date
8. **Appendix B: Calculation Trace** — the exact arithmetic the script performed

## Tone rules (non-negotiable)

The user explicitly asked for "the dead truth" backed by statistics. Honor that:

- **No hedging language.** Forbidden phrases: "it depends", "might be", "could potentially", "remains to be seen", "is hard to say". Replace with quantified confidence intervals.
- **No flattery.** Do not soften verdicts. If Y5 = 22, the verdict is "Terminal" — do not say "challenging but workable".
- **Every claim has a number or a citation.** If you can't cite a source, mark the claim as `[UNSOURCED — confidence: low]` and exclude it from scoring.
- **Lead with the verdict.** The executive summary opens with the verdict, not the methodology.
- **Use the clinical voice.** "Moat score: 23/100. Primary risk: AI commoditization (87% likelihood by Y3). Verdict: pivot required." — this is the target register.

## Reproducibility contract

This is the user's hard requirement. To honor "if tested with different tools still provide similar conclusion":

1. **All numerical scores come from `moat_calculator.py`.** The script's weights and formulas are fixed in `references/scoring-methodology.md` and encoded literally in the script. Different LLMs running the same skill must produce the same numbers.
2. **The LLM may disagree with a score, but only via the override protocol** documented in `references/reproducibility-protocol.md`. Overrides are recorded in the JSON output and flagged in the PDF — never silent.
3. **Evidence is versioned.** The JSON bundle includes `retrieved_at` timestamps for every data point, so a future re-run can detect drift.
4. **The scoring input dict is the single source of truth.** If two runs produce the same `scoring_input.json`, they produce identical `scores.json` byte-for-byte (modulo timestamps).
5. **Confidence intervals are explicit.** Every axis score includes a ± range derived from evidence confidence. Two runs that disagree on the point estimate but agree within confidence intervals are considered equivalent.

## File map

```
codebase-5yr-forecast/
├── SKILL.md                              (this file)
├── references/
│   ├── scoring-methodology.md            (4-axis scorecard, weights, decay math, verdict thresholds)
│   ├── data-sources.md                   (which sources, what to extract, how to cite)
│   ├── pivot-roadmap.md                  (negative-verdict playbook)
│   └── reproducibility-protocol.md       (override protocol, confidence math, drift detection)
├── scripts/
│   ├── codebase_scanner.py               (factual codebase metrics — Phase 2)
│   ├── moat_calculator.py                (deterministic scoring engine — Phase 4, the core)
│   └── generate_report.py                (PDF + JSON bundle generator — Phase 6)
├── assets/
│   └── report_schema.json                (JSON schema for the output bundle)
└── evals/
    └── evals.json                        (test prompts)
```

## How to use this skill (quick reference for the LLM)

1. Read this SKILL.md in full (you are here).
2. Read `references/scoring-methodology.md` — this is the algorithmic core. You MUST internalize the weights and verdict thresholds before scoring.
3. Read `references/data-sources.md` — know which sources to query before you start gathering evidence.
4. Read `references/reproducibility-protocol.md` — this is what makes the skill testable across tools.
5. Read `references/pivot-roadmap.md` only if Phase 5 is triggered.
6. Run the workflow. Persist intermediate artifacts (`scan.json`, `evidence.json`, `scoring_input.json`, `scores.json`) to `/home/z/my-project/download/forecast_work/` so the user can audit the chain.
7. Produce the final PDF + JSON bundle in `/home/z/my-project/download/`.
8. Report the file paths and the headline verdict to the user in your final message.

## Edge cases

- **Tiny codebase (<100 LOC):** Flag low confidence on technical moat. The script will still run, but the report header notes "Insufficient codebase volume for high-confidence technical assessment."
- **No external evidence found:** The script runs with all sub-scores set to 50 (neutral) and the report header reads "EVIDENCE-GAP MODE — treat all scores as low-confidence." This is a feature, not a bug — it forces the user to know they're flying blind.
- **Project pitch only (no code):** Technical moat is derived from the pitch's described architecture. Confidence is capped at "medium" for the technical axis.
- **Private GitHub repo / URL not clonable:** Fall back to pitch mode. Note this in the report.
- **Scoring input fails validation:** The script exits non-zero with a clear error. Fix the input and re-run — do not improvise scores.
