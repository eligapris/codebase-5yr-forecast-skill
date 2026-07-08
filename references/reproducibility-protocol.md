# Reproducibility Protocol

This document defines what makes the skill's output reproducible across different LLMs, tools, and re-runs. It is the user's hardest requirement: "if tested with different tools still provide similar conclusion."

The protocol has five layers. Each layer is independently verifiable.

---

## Layer 1: Deterministic scoring

The single most important rule:

> **All numerical scores in the final report come from `scripts/moat_calculator.py`. The LLM never writes a number that the script didn't produce.**

This means:
- The LLM fills in `scoring_input.json` (the inputs to the script).
- The script computes every score, every confidence interval, every projection.
- The LLM reads `scores.json` (the script's output) and writes the narrative.
- If the LLM wants to mention a number, it must come from `scores.json`.

Why this matters: different LLMs will disagree on narrative phrasing, but if they fill in the same `scoring_input.json`, the script produces byte-identical `scores.json`. The user's reproducibility requirement is satisfied at the numerical level even if the prose differs.

### Verification

The script writes a SHA-256 hash of its input to its output:
```json
{
  "input_hash": "sha256:...",
  "script_version": "1.0.0",
  "computed_at": "2026-06-19T08:45:00Z",
  "scores": { ... }
}
```

Two runs with the same `input_hash` and `script_version` must produce the same `scores` object (modulo `computed_at`).

---

## Layer 2: Evidence versioning

Every evidence entry includes:
- `retrieved_at` — when the data was fetched
- `source_url` — where it came from
- `source_version` — if applicable (e.g., "2024 StackOverflow Survey", "TIOBE June 2026")

The JSON bundle's `evidence_freshness` field:
- `fresh` — all evidence retrieved within last 24 hours
- `recent` — all evidence within last 7 days
- `stale` — any evidence older than 7 days

### Drift detection

When re-running the skill on the same project:
- Compare new evidence entries to old ones by `(source_url, metric)` key
- If the value changed, record a `drift_event` in the new run's metadata
- If the drift changes a sub-score by more than its confidence interval, flag it as "significant drift" in the report

This lets a reviewer distinguish "two runs disagreed because the data changed" from "two runs disagreed because the LLMs filled in the inputs differently".

---

## Layer 3: Confidence intervals on every score

Every sub-score carries a ± range. The rule:

> **Two runs that produce point estimates within each other's confidence intervals are considered equivalent.**

This is the operational definition of "similar conclusion". It's not "identical numbers" — that's too strict given LLM variability. It's "numbers within noise of each other".

### How confidence intervals are computed

For each sub-score, the LLM provides:
- `point_estimate` — the best guess
- `confidence_level` — high / medium / low

The script converts confidence levels to intervals:
- high → ±5
- medium → ±15
- low → ±30

If the LLM provides evidence for a sub-score, confidence is at least `medium`. If evidence is missing (default-neutral = 50), confidence is `low` (±30).

For composite scores, the script runs a Monte Carlo (1,000 samples) to propagate the sub-score intervals up.

---

## Layer 4: Override protocol

The LLM may disagree with a script-produced score. This is allowed, but **never silently**.

### When overrides are permitted

- The rubric clearly misfired (e.g., a 10,000-LOC codebase with massive test coverage that the complexity rubric scored too low because it didn't account for cyclomatic complexity).
- New evidence came in after the script ran (rare — re-run the script instead).
- An edge case the rubric didn't anticipate (e.g., a hardware project where physical-world moat isn't captured by any axis).

### When overrides are NOT permitted

- "I think the score should be higher" without specific evidence
- "The user won't like this verdict"
- "This doesn't match my intuition"

### Override format

```json
{
  "overrides": [
    {
      "path": "axis_inputs.technical_moat.code_complexity_score",
      "original_value": 30,
      "new_value": 55,
      "justification": "Cyclomatic complexity is 8.2 per file (well above average) despite LOC being 8,000; the LOC-based rubric undercounts this. Evidence: ev_014 (radon scan output).",
      "evidence_citations": ["ev_014"]
    }
  ]
}
```

The override:
1. Is recorded in `scoring_input.json` before the script runs
2. The script applies it AFTER computing the original score, then recomputes
3. Both original and overridden values appear in `scores.json` under `calculation_trace`
4. The PDF flags overridden scores with a `⚠️` marker and an appendix entry

### Override budget

To prevent override abuse, the script enforces a budget:
- Maximum 3 overrides per run
- Each override must change the score by less than 30 points
- Total composite-score impact of all overrides combined cannot exceed 10 points

If the LLM hits the budget and still disagrees, the verdict stands as the script produced it. The LLM's disagreement is noted in the report's "Analyst Notes" section.

---

## Layer 5: Cross-tool verification protocol

For users who want to verify the skill's reproducibility, the recommended protocol:

1. Run the skill with Tool A (e.g., GLM).
2. Save `scoring_input_A.json`, `scores_A.json`, `evidence_A.json`, and the final PDF + JSON bundle.
3. Wait at least 24 hours (to avoid fresh-cache effects) but no more than 7 days (to avoid data drift).
4. Run the skill with Tool B (e.g., a different LLM, or a human analyst following the same protocol).
5. Compare:

| Comparison | Pass criterion |
|------------|----------------|
| `scoring_input_A.json` vs `scoring_input_B.json` | Sub-score point estimates within ±15 of each other for ≥80% of sub-scores |
| `scores_A.json` vs `scores_B.json` (composite M₀) | Within ±10 of each other |
| `scores_A.json` vs `scores_B.json` (Y5 expected) | Within ±10 of each other |
| Verdict category | Same verdict category (Durable / Eroding / At Risk / Terminal) |
| Pivot recommendation (if triggered) | Same pivot archetype recommended as #1 |

If all five pass, the runs are "equivalent" — the reproducibility requirement is satisfied.

If any fail, the report includes a "Cross-Tool Discrepancy" appendix detailing which sub-scores diverged and the likely cause (usually evidence drift, occasionally LLM interpretation differences on a judgment sub-score).

---

## What this protocol does NOT guarantee

Be honest about the limits:

1. **The LLM still fills in `scoring_input.json`.** Two different LLMs will read the same evidence and may score a subjective sub-score (e.g., `network_effects_score`) differently. The confidence intervals absorb most of this, but not all.
2. **Evidence can drift between runs.** A 7-day-old run and a today-run may use different TIOBE ranks. The drift detection layer flags this.
3. **The rubrics are judgment calls.** The thresholds (e.g., "LOC > 100,000 → 75") are calibrated, not derived from first principles. They can be tuned; that's a versioned change to `references/scoring-methodology.md` and `moat_calculator.py` together.

The protocol's claim is narrower than "any two runs produce identical output". It's:

> **Given the same evidence, the same scoring input, and the same script version, the output is byte-identical. Given different evidence gathered within a 7-day window by different tools, the output is equivalent within stated confidence bounds.**

That is the strongest defensible claim, and it's what the user asked for.

---

## Audit trail

Every run produces a `manifest.json`:

```json
{
  "skill_version": "1.0.0",
  "script_version": "1.0.0",
  "scoring_methodology_version": "1.0.0",
  "input_hash": "sha256:...",
  "output_hash": "sha256:...",
  "evidence_count": 47,
  "evidence_freshness": "fresh",
  "overrides_applied": 0,
  "computed_at": "2026-06-19T08:50:00Z",
  "model_used": "glm-4.6",
  "tool_used": "super-z-cli"
}
```

This is saved alongside the PDF and JSON bundle. A reviewer can verify:
- The same skill/script/methodology versions were used
- The input hash matches `scoring_input.json`
- The output hash matches `scores.json`
- No undisclosed overrides were applied

This is the audit trail that makes the skill trustworthy for high-stakes decisions.
