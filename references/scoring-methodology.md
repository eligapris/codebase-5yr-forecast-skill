# Scoring Methodology

This document defines the **exact arithmetic** behind every score the skill produces. The `scripts/moat_calculator.py` script is the canonical implementation of this document; if the two ever disagree, the script wins (and a bug should be filed against this doc).

The reason for being this precise: the user wants the skill to produce **similar conclusions across different tools**. That is only possible if the scoring is a deterministic function of the inputs, not an LLM judgment call.

---

## 1. The four axes

The composite Moat Durability Score is a weighted sum of four axes. Each axis is a 0–100 number (higher = better for the project, except AI Disruption Exposure which is reported raw but inverted in the composite).

| Axis | Weight in composite | Direction |
|------|---------------------|-----------|
| Technical Moat | 30% | higher is better |
| Trend Alignment | 20% | higher is better |
| Market & Demand | 25% | higher is better |
| AI Disruption Exposure | 25% (inverted) | lower is better for the project |

```
M₀ = 0.30 · TechnicalMoat
   + 0.20 · TrendAlignment
   + 0.25 · MarketDemand
   + 0.25 · (100 − AIDisruptionExposure)
```

The weights were chosen to reflect the user's stated priorities: technical defensibility matters most, but AI disruption is given equal weight to market demand because the user explicitly framed AI commoditization as the central risk to a 5-year horizon.

---

## 2. Axis 1 — Technical Moat (0–100)

A weighted average of five sub-scores. Each sub-score is 0–100, set by the LLM based on evidence and codebase scan, per the rubrics below.

| Sub-score | Weight | What it measures |
|-----------|--------|------------------|
| `code_complexity_score` | 20% | How hard is this to rebuild from scratch? |
| `ip_score` | 15% | Patentable / trade-secret / novel-algorithm content |
| `switching_cost_score` | 25% | Cost (time + money + risk) for a user to leave |
| `network_effects_score` | 20% | Does each new user make the product more valuable? |
| `scale_advantage_score` | 20% | Does unit cost fall with volume in a way competitors can't easily match? |

### Rubrics

**code_complexity_score** — derived from scan metrics:
- LOC < 1,000 → 10
- 1,000–10,000 → 30
- 10,000–100,000 → 55
- 100,000–500,000 → 75
- > 500,000 → 85
- Adjust +5 if `test_to_source_ratio > 0.4` (quality complexity)
- Adjust -10 if `todo_count / file_count > 5` (debt masks real complexity)
- Adjust +5 per unique non-trivial external integration beyond the third (max +20)

**ip_score** — LLM-judged on 0–10 scale based on README/source inspection, then ×10:
- 0–2: standard CRUD / boilerplate
- 3–4: domain-specific business logic, no novel algorithms
- 5–6: custom algorithms, proprietary data structures, or non-obvious optimizations
- 7–8: patentable novelty or trade-secret-grade processing pipeline
- 9–10: foundational research-grade innovation (rare)

**switching_cost_score** — LLM-judged 0–100 based on:
- Data lock-in (does the product store user data that's hard to export?)
- Integration depth (how many third-party systems are wired in?)
- Workflow embeddedness (is the product in the user's daily critical path?)
- Re-training cost (would switching require re-training a team?)
Each factor 0–25, summed.

**network_effects_score** — LLM-judged 0–100:
- 0: single-user product, no network effects
- 25: weak indirect effects (e.g., community forum)
- 50: marketplace two-sided (but small)
- 75: strong two-sided with liquidity moat
- 100: dominant platform with winner-take-most dynamics

**scale_advantage_score** — LLM-judged 0–100:
- 0: linear cost curve, no scale advantage
- 25: minor infra economies (bulk discounts)
- 50: meaningful cost curve (own data centers, specialized infra)
- 75: strong data flywheel (more usage → better model → more usage)
- 100: regulatory + capital + data moat combined (e.g., exchanges, credit bureaus)

### Confidence interval

Each sub-score carries a ± confidence range derived from evidence quality:
- high-confidence evidence (≥3 independent sources, numeric data) → ±5
- medium (1–2 sources or qualitative) → ±15
- low (LLM judgment only, no external evidence) → ±30

Axis confidence = max of sub-score confidences (conservative).

---

## 3. Axis 2 — Trend Alignment (0–100)

A weighted average of four sub-scores. Unlike Technical Moat, these are signed (-100 to +100) at the input stage and then mapped to 0–100 by the formula `score = (input + 100) / 2`.

| Sub-score (input range -100 to +100) | Weight | Source |
|--------------------------------------|--------|--------|
| `language_trajectory` | 30% | TIOBE 5-year rank delta + RedMonk 5-year rank delta (average) |
| `framework_trajectory` | 30% | GitHub star velocity (linear regression slope) + npm/PyPI/etc download growth (CAGR over 3 years) |
| `architecture_pattern_adoption` | 20% | ThoughtWorks Tech Radar ring + StackOverflow Survey adoption % |
| `skill_demand_trend` | 20% | StackOverflow Survey "most wanted" + job posting trend (web search) |

### Rubrics

**language_trajectory** — signed:
- +100: top-3 language and rising
- +50: top-10 and rising or stable
- 0: top-20 and stable
- -50: top-20 and falling, or top-30 and rising
- -100: falling and outside top-30

**framework_trajectory**:
- +100: >50% YoY star/download growth
- +50: 20–50% YoY growth
- 0: ±20% (stable)
- -50: -20% to -50% YoY
- -100: >-50% YoY

**architecture_pattern_adoption**:
- +100: Adopt ring + top-quartile adoption in survey
- +50: Trial ring + above-median adoption
- 0: Assess ring or median adoption
- -50: Hold ring or below-median adoption
- -100: explicitly deprecated or bottom-quartile adoption

**skill_demand_trend**:
- +100: top-10 "most wanted" + >50% YoY job posting growth
- +50: top-25 "most wanted" + positive job posting trend
- 0: stable demand
- -50: declining demand
- -100: bottom-quartile demand and falling

### Final axis score

```
TrendAlignment = 0.30 · ((lang + 100) / 2)
              + 0.30 · ((fwk + 100) / 2)
              + 0.20 · ((arch + 100) / 2)
              + 0.20 · ((skill + 100) / 2)
```

---

## 4. Axis 3 — Market & Demand (0–100)

| Sub-score | Weight | Range |
|-----------|--------|-------|
| `tam_cagr_pct` | 30% | number (percentage), mapped via piecewise function below |
| `buyer_alignment_score` | 25% | 0–100 |
| `regulatory_score` | 20% | -100 to +100, mapped via `(x+100)/2` |
| `competitive_density_score` | 25% | 0–100 (inverted: more competitors = lower score) |

### tam_cagr_pct mapping (piecewise)

```
if cagr >= 25:  tam_score = 100
if 15 <= cagr < 25: tam_score = 80 + (cagr - 15) * 2
if 5  <= cagr < 15: tam_score = 60 + (cagr - 5) * 2
if 0  <= cagr < 5:  tam_score = 50 + cagr * 2
if -5 < cagr < 0:   tam_score = 50 + cagr * 2     (e.g., -3 → 44)
if cagr <= -5:      tam_score = max(0, 40 + cagr)
```

### Rubrics

**buyer_alignment_score** — LLM-judged 0–100 based on:
- Is the buyer the same as the user? (yes → +20)
- Is the buyer's budget growing? (web-search evidence → ±20)
- Is the problem a top-3 priority for the buyer's role? (LLM judgment → ±20)
- Is the buyer's industry growing or shrinking? (±20)
- Sales cycle length (shorter = better, ±20)

**regulatory_score** — signed -100 to +100:
- +100: strong regulatory tailwind (e.g., compliance mandates that the product satisfies)
- 0: neutral
- -100: regulatory headwind (e.g., product is in a category being restricted)

**competitive_density_score**:
- 0: 100+ direct competitors, multiple well-funded ($100M+)
- 25: 20–100 competitors, several funded
- 50: 5–20 competitors, 1–2 well-funded
- 75: 1–5 competitors, none well-funded
- 100: no direct competitors (but subtract 20 if "no competitors because no market" — distinguish from genuine whitespace)

### Final axis score

```
MarketDemand = 0.30 · tam_score
             + 0.25 · buyer_alignment_score
             + 0.20 · ((regulatory + 100) / 2)
             + 0.25 · competitive_density_score
```

---

## 5. Axis 4 — AI Disruption Exposure (0–100, higher = worse for the project)

This is the axis the user cares most about. It is reported raw (higher = more exposed) but inverted in the composite formula.

| Sub-score | Weight | Range |
|-----------|--------|-------|
| `feature_automatability_pct` | 40% | 0–100 (% of features an LLM/agent could replicate by Y5) |
| `proprietary_data_dependency_score` | 20% | 0–100 (higher = MORE dependent on proprietary data = LESS disruptable) |
| `ux_commoditization_score` | 20% | 0–100 (higher = more commoditized = more disruptable) |
| `workflow_complexity_score` | 20% | 0–100 (higher = more complex = more disruptable by agents) |

### Rubrics

**feature_automatability_pct** — per-feature analysis:
For each major feature, score 0 (not automatable), 50 (partially), 100 (fully) along:
- Can an LLM do this from a natural-language instruction today? (yes=100, partial=50, no=0)
- Will an LLM + tool-use agent do this by Y3? (extrapolate current capability curve)
- Does the feature depend on physical-world interaction, regulatory licensing, or proprietary data the LLM can't access? (if yes → cap at 20)

Average across features. The per-feature table is included in the PDF as the "AI Disruption Deep-Dive" section.

**proprietary_data_dependency_score** — LLM-judged 0–100:
- 100: product is essentially a proprietary dataset (e.g., credit bureau, Bloomberg terminal)
- 75: product depends on data accumulated over years that an LLM can't trivially scrape
- 50: data is partially proprietary, partially public
- 25: data is mostly public, but curation adds value
- 0: no proprietary data; LLM has everything it needs

(Note: this score is used directly in the AI Exposure axis. Higher = less disruptable. The composite formula already handles the inversion via `100 - AIDisruptionExposure`, so the script does NOT re-invert this sub-score internally. The sub-score's "higher = better for the project" direction is preserved by being part of an axis where it is the only sub-score that points the "good" way. To avoid confusion, the script applies this sub-score as `(100 - proprietary_data_dependency_score)` when computing the axis average. See the script for the canonical arithmetic.)

**ux_commoditization_score**:
- 100: standard CRUD UI, tables + forms + buttons
- 75: standard UI with some domain-specific widgets
- 50: novel interaction model but already widely imitated
- 25: novel interaction model that requires user training
- 0: physical / sensory interaction LLMs can't replicate

**workflow_complexity_score**:
- 100: linear single-step workflow, LLM-trivial
- 75: multi-step workflow but well-documented
- 50: multi-step with conditional branches
- 25: multi-step with stateful dependencies across tools
- 0: requires real-time human judgment / negotiation / physical action

### Final axis score

```
AIDisruptionExposure = 0.40 · feature_automatability_pct
                     + 0.20 · (100 − proprietary_data_dependency_score)
                     + 0.20 · ux_commoditization_score
                     + 0.20 · workflow_complexity_score
```

---

## 6. The composite score and decay math

```
M₀ = 0.30 · TechnicalMoat
   + 0.20 · TrendAlignment
   + 0.25 · MarketDemand
   + 0.25 · (100 − AIDisruptionExposure)
```

### Decay constant

The moat decays exponentially. The decay constant λ is derived from AI exposure (the dominant erosion force over a 5-year horizon):

```
λ = (AIDisruptionExposure / 100) · 0.40
```

Rationale: at 100% AI exposure, the moat loses ~33% of its value per year (e^(-0.4) ≈ 0.67). At 0% exposure, no AI-driven decay (other axes' drift is captured by scenario adjustments, not λ).

### Projection

```
M(t) = M₀ · e^(−λ · t)            for t = 0, 1, 2, 3, 4, 5
```

The Year-5 score `M(5)` is the headline number used for the verdict.

### Scenario adjustments

The same projection is run three times:

- **Base** (50% weight): uses median evidence values, no adjustments.
- **Bull** (25% weight): `λ_bull = λ · 0.6` (AI disruption slower), `MarketDemand_bull = MarketDemand + 10` (capped at 100), `TrendAlignment_bull = TrendAlignment + 5`.
- **Bear** (25% weight): `λ_bear = λ · 1.5` (AI disruption faster), `MarketDemand_bear = MarketDemand − 15` (floored at 0), `TrendAlignment_bear = TrendAlignment − 10`.

The expected Y5 score is the probability-weighted average:
```
E[M(5)] = 0.25 · M_bull(5) + 0.50 · M_base(5) + 0.25 · M_bear(5)
```

The reported "Y5 score" in the executive summary is `E[M(5)]`. The PDF shows all three curves overlaid.

---

## 7. Verdict thresholds

Based on `E[M(5)]`:

| E[M(5)] | Verdict | Action |
|---------|---------|--------|
| ≥ 70 | **Durable — Defend & Extend** | Generate a 3-5 move reinforcement plan |
| 50 – 69 | **Eroding — Reinforce or Niche** | Generate a reinforcement plan + niche-down options |
| 30 – 49 | **At Risk — Pivot Required** | Generate full pivot roadmap |
| < 30 | **Terminal — Sunset or Radical Pivot** | Generate radical pivot roadmap + sunset timeline |

The thresholds are calibrated so that a project with strong technical moat but high AI exposure (e.g., a sophisticated rules engine that LLMs can now replicate) lands in "At Risk" rather than "Eroding" — the user's framing is that AI disruption is the dominant risk and the thresholds reflect that.

---

## 8. Confidence reporting

Every axis score in the JSON output includes:
```json
{
  "point_estimate": 47.3,
  "confidence_interval": [32.1, 62.5],
  "confidence_level": "medium",
  "evidence_citations": ["evidence_id_3", "evidence_id_7"],
  "override_applied": false
}
```

The composite score's confidence interval is computed by Monte Carlo: 1,000 samples, each axis sampled uniformly from its confidence interval, recomposite, take 5th and 95th percentiles. This is implemented in `moat_calculator.py --monte-carlo`.

---

## 9. Override protocol

If the LLM believes a script-produced score is wrong (e.g., the rubric misfired on an edge case), it may apply an override per `references/reproducibility-protocol.md`. The override:

1. Must be recorded in `scoring_input.json` under `overrides: [...]`.
2. Must include the original value, the new value, and a justification with at least one evidence citation.
3. Is flagged in the PDF ("⚠️ Score overridden — see appendix").
4. Is included in the JSON output's `calculation_trace` array.

Overrides are a last resort. The default behavior is to trust the script.

---

## 10. Worked example (for calibration)

A CLI tool that converts CSV to Parquet, written in Python (500 LOC, no tests, 3 dependencies). Hypothetical scores:

- Technical Moat: code_complexity=20, ip=10, switching_cost=15, network_effects=0, scale_advantage=0 → axis = 0.20·20 + 0.15·10 + 0.25·15 + 0.20·0 + 0.20·0 = **9.25**
- Trend Alignment: Python=+50, pandas=+30, CLI pattern=0, Python demand=+50 → mapped to (75, 65, 50, 75) → axis = 0.30·75 + 0.30·65 + 0.20·50 + 0.20·75 = **67.0**
- Market Demand: TAM CAGR 8% → tam_score = 60 + (8-5)·2 = 66; buyer_alignment=40; regulatory=0 → 50; competitive_density=10 → axis = 0.30·66 + 0.25·40 + 0.20·50 + 0.25·10 = **42.3**
- AI Exposure: feature_automatability=95, proprietary_data=0 (inverted=100), ux_commoditization=100, workflow_complexity=100 → axis = 0.40·95 + 0.20·100 + 0.20·100 + 0.20·100 = **98.0**

Composite (base scenario):
- M₀ = 0.30·9.25 + 0.20·67.0 + 0.25·42.3 + 0.25·(100-98) = 2.78 + 13.40 + 10.58 + 0.50 = **27.26**
- λ = (98/100) · 0.40 = 0.392
- M(5) under base = 27.26 · e^(-0.392·5) = 27.26 · 0.140 = **3.83**

Scenario-adjusted Y5:
- Bull (λ × 0.6 = 0.235, market +10 → 52.3, trend +5 → 72): M₀ = 0.30·9.25 + 0.20·72 + 0.25·52.3 + 0.25·2 = 2.78 + 14.40 + 13.08 + 0.50 = 30.76; M(5) = 30.76 · e^(-0.235·5) = 30.76 · 0.308 = **9.49**
- Base: **3.83** (computed above)
- Bear (λ × 1.5 = 0.588, market -15 → 27.3, trend -10 → 57): M₀ = 0.30·9.25 + 0.20·57 + 0.25·27.3 + 0.25·2 = 2.78 + 11.40 + 6.83 + 0.50 = 21.51; M(5) = 21.51 · e^(-0.588·5) = 21.51 · 0.0524 = **1.13**

Expected Y5 = 0.25·9.49 + 0.50·3.83 + 0.25·1.13 = 2.37 + 1.92 + 0.28 = **4.57**

Verdict: **Terminal — Sunset or Radical Pivot.** (E[M(5)] = 4.57 < 30.)

This is the kind of "dead truth" the user wants. A small CLI utility with no moat and total AI automatability is forecast to be effectively dead in 5 years. The script says so. The LLM does not soften it.

These numbers are reproducible: run `python scripts/moat_calculator.py` on the matching `scoring_input.json` (saved as `scripts/sample_scoring_input.json` in the skill's dev workspace) and you will get the same values.
