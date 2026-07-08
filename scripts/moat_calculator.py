#!/usr/bin/env python3
"""
moat_calculator.py — Deterministic scoring engine for the codebase-5yr-forecast skill.

This script is the canonical implementation of references/scoring-methodology.md.
Same input → same output, byte-for-byte (modulo timestamps).

Usage:
    python moat_calculator.py scoring_input.json [--monte-carlo] > scores.json
    python moat_calculator.py --version
    python moat_calculator.py --validate scoring_input.json

Input: scoring_input.json (schema documented in SKILL.md)
Output: scores.json written to stdout
"""

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from typing import Any


SCRIPT_VERSION = "1.0.0"
SCORING_METHODOLOGY_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Fixed weights (must match references/scoring-methodology.md exactly)
# ---------------------------------------------------------------------------

COMPOSITE_WEIGHTS = {
    "technical_moat": 0.30,
    "trend_alignment": 0.20,
    "market_demand": 0.25,
    "ai_disruption_exposure_inverted": 0.25,  # uses (100 - axis_score)
}

TECHNICAL_MOAT_WEIGHTS = {
    "code_complexity_score": 0.20,
    "ip_score": 0.15,
    "switching_cost_score": 0.25,
    "network_effects_score": 0.20,
    "scale_advantage_score": 0.20,
}

TREND_ALIGNMENT_WEIGHTS = {
    "language_trajectory": 0.30,
    "framework_trajectory": 0.30,
    "architecture_pattern_adoption": 0.20,
    "skill_demand_trend": 0.20,
}

MARKET_DEMAND_WEIGHTS = {
    "tam_cagr_pct": 0.30,
    "buyer_alignment_score": 0.25,
    "regulatory_score": 0.20,
    "competitive_density_score": 0.25,
}

AI_EXPOSURE_WEIGHTS = {
    "feature_automatability_pct": 0.40,
    "proprietary_data_dependency_score": 0.20,  # inverted inside the axis
    "ux_commoditization_score": 0.20,
    "workflow_complexity_score": 0.20,
}

# Decay constant scaling: lambda = (ai_exposure / 100) * LAMBDA_SCALE
LAMBDA_SCALE = 0.40

# Scenario multipliers (must match scoring-methodology.md § 6)
SCENARIO_ADJUSTMENTS = {
    "bull": {
        "lambda_multiplier": 0.6,
        "market_demand_delta": +10,
        "trend_alignment_delta": +5,
        "probability": 0.25,
    },
    "base": {
        "lambda_multiplier": 1.0,
        "market_demand_delta": 0,
        "trend_alignment_delta": 0,
        "probability": 0.50,
    },
    "bear": {
        "lambda_multiplier": 1.5,
        "market_demand_delta": -15,
        "trend_alignment_delta": -10,
        "probability": 0.25,
    },
}

# Verdict thresholds (must match scoring-methodology.md § 7)
VERDICT_THRESHOLDS = [
    (70, "Durable — Defend & Extend"),
    (50, "Eroding — Reinforce or Niche"),
    (30, "At Risk — Pivot Required"),
    (0,  "Terminal — Sunset or Radical Pivot"),
]

# Confidence interval half-widths by level
CONFIDENCE_HALF_WIDTHS = {"high": 5.0, "medium": 15.0, "low": 30.0, "none": 50.0}

# Override budget
MAX_OVERRIDES = 3
MAX_OVERRIDE_DELTA = 30.0
MAX_OVERRIDE_COMPOSITE_IMPACT = 10.0

# Monte Carlo sample count (deterministic seed for reproducibility)
MONTE_CARLO_SAMPLES = 1000
MONTE_CARLO_SEED = 20260619  # fixed seed — same input → same CI


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def map_signed_to_0_100(signed_value: float) -> float:
    """Map a -100..+100 value to 0..100."""
    return clamp((signed_value + 100.0) / 2.0)


def tam_cagr_to_score(cagr: float) -> float:
    """Piecewise mapping of TAM CAGR % to 0-100 score."""
    if cagr >= 25:
        return 100.0
    if cagr >= 15:
        return 80.0 + (cagr - 15.0) * 2.0
    if cagr >= 5:
        return 60.0 + (cagr - 5.0) * 2.0
    if cagr >= 0:
        return 50.0 + cagr * 2.0
    if cagr > -5:
        return 50.0 + cagr * 2.0  # e.g., -3 -> 44
    return max(0.0, 40.0 + cagr)


def hash_dict(d: Any) -> str:
    """Stable SHA-256 of a JSON-serializable object (sorted keys)."""
    canonical = json.dumps(d, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

REQUIRED_AXIS_INPUTS = {
    "technical_moat": set(TECHNICAL_MOAT_WEIGHTS.keys()),
    "trend_alignment": set(TREND_ALIGNMENT_WEIGHTS.keys()),
    "market_demand": set(MARKET_DEMAND_WEIGHTS.keys()),
    "ai_disruption_exposure": set(AI_EXPOSURE_WEIGHTS.keys()),
}


def validate_input(data: dict) -> list[str]:
    """Return a list of validation error strings. Empty = valid."""
    errors = []
    if "project_name" not in data:
        errors.append("Missing required field: project_name")
    if "axis_inputs" not in data:
        errors.append("Missing required field: axis_inputs")
        return errors

    axis_inputs = data["axis_inputs"]
    for axis, required_fields in REQUIRED_AXIS_INPUTS.items():
        if axis not in axis_inputs:
            errors.append(f"Missing axis: {axis}")
            continue
        for field in required_fields:
            if field not in axis_inputs[axis]:
                errors.append(f"Missing sub-score: {axis}.{field}")
            else:
                value = axis_inputs[axis][field]
                if not isinstance(value, (int, float)):
                    errors.append(f"Non-numeric value for {axis}.{field}: {value!r}")
                    continue
                # Range checks
                if axis in ("technical_moat", "market_demand"):
                    if axis == "market_demand" and field == "tam_cagr_pct":
                        continue  # any number, signed
                    if not (0.0 <= value <= 100.0):
                        errors.append(f"{axis}.{field} = {value} out of [0,100]")
                elif axis == "trend_alignment":
                    if not (-100.0 <= value <= 100.0):
                        errors.append(f"{axis}.{field} = {value} out of [-100,+100]")
                elif axis == "ai_disruption_exposure":
                    if not (0.0 <= value <= 100.0):
                        errors.append(f"{axis}.{field} = {value} out of [0,100]")

    # Validate overrides
    overrides = data.get("overrides", [])
    if len(overrides) > MAX_OVERRIDES:
        errors.append(f"Too many overrides: {len(overrides)} > {MAX_OVERRIDES}")
    for i, ov in enumerate(overrides):
        if "path" not in ov or "new_value" not in ov:
            errors.append(f"Override {i} missing 'path' or 'new_value'")
            continue
        if "original_value" in ov:
            delta = abs(ov["new_value"] - ov["original_value"])
            if delta > MAX_OVERRIDE_DELTA:
                errors.append(
                    f"Override {i} delta {delta:.1f} exceeds max {MAX_OVERRIDE_DELTA}"
                )
        if "justification" not in ov or "evidence_citations" not in ov:
            errors.append(f"Override {i} missing 'justification' or 'evidence_citations'")

    return errors


# ---------------------------------------------------------------------------
# Axis computations
# ---------------------------------------------------------------------------

def compute_technical_moat(inputs: dict) -> dict:
    sub_scores = {}
    for field, weight in TECHNICAL_MOAT_WEIGHTS.items():
        sub_scores[field] = float(inputs[field])
    axis_score = sum(sub_scores[f] * w for f, w in TECHNICAL_MOAT_WEIGHTS.items())
    return {
        "axis_score": round(clamp(axis_score), 2),
        "sub_scores": sub_scores,
        "weights": TECHNICAL_MOAT_WEIGHTS,
    }


def compute_trend_alignment(inputs: dict) -> dict:
    sub_scores_raw = {f: float(inputs[f]) for f in TREND_ALIGNMENT_WEIGHTS}
    # Map each -100..+100 sub-score to 0..100
    sub_scores_0_100 = {f: map_signed_to_0_100(v) for f, v in sub_scores_raw.items()}
    axis_score = sum(
        sub_scores_0_100[f] * w for f, w in TREND_ALIGNMENT_WEIGHTS.items()
    )
    return {
        "axis_score": round(clamp(axis_score), 2),
        "sub_scores_raw": sub_scores_raw,
        "sub_scores_0_100": {k: round(v, 2) for k, v in sub_scores_0_100.items()},
        "weights": TREND_ALIGNMENT_WEIGHTS,
    }


def compute_market_demand(inputs: dict) -> dict:
    tam_cagr = float(inputs["tam_cagr_pct"])
    tam_score = tam_cagr_to_score(tam_cagr)
    buyer = float(inputs["buyer_alignment_score"])
    regulatory = map_signed_to_0_100(float(inputs["regulatory_score"]))
    competitive = float(inputs["competitive_density_score"])
    axis_score = (
        tam_score * MARKET_DEMAND_WEIGHTS["tam_cagr_pct"]
        + buyer * MARKET_DEMAND_WEIGHTS["buyer_alignment_score"]
        + regulatory * MARKET_DEMAND_WEIGHTS["regulatory_score"]
        + competitive * MARKET_DEMAND_WEIGHTS["competitive_density_score"]
    )
    return {
        "axis_score": round(clamp(axis_score), 2),
        "sub_scores": {
            "tam_cagr_pct": tam_cagr,
            "tam_score": round(tam_score, 2),
            "buyer_alignment_score": buyer,
            "regulatory_score_raw": float(inputs["regulatory_score"]),
            "regulatory_score_0_100": round(regulatory, 2),
            "competitive_density_score": competitive,
        },
        "weights": MARKET_DEMAND_WEIGHTS,
    }


def compute_ai_disruption_exposure(inputs: dict) -> dict:
    feature = float(inputs["feature_automatability_pct"])
    proprietary = float(inputs["proprietary_data_dependency_score"])
    ux = float(inputs["ux_commoditization_score"])
    workflow = float(inputs["workflow_complexity_score"])
    # proprietary_data_dependency is INVERTED within the axis (higher = less disruptable)
    axis_score = (
        feature * AI_EXPOSURE_WEIGHTS["feature_automatability_pct"]
        + (100.0 - proprietary) * AI_EXPOSURE_WEIGHTS["proprietary_data_dependency_score"]
        + ux * AI_EXPOSURE_WEIGHTS["ux_commoditization_score"]
        + workflow * AI_EXPOSURE_WEIGHTS["workflow_complexity_score"]
    )
    return {
        "axis_score": round(clamp(axis_score), 2),
        "sub_scores": {
            "feature_automatability_pct": feature,
            "proprietary_data_dependency_score": proprietary,
            "proprietary_data_dependency_inverted": round(100.0 - proprietary, 2),
            "ux_commoditization_score": ux,
            "workflow_complexity_score": workflow,
        },
        "weights": AI_EXPOSURE_WEIGHTS,
    }


# ---------------------------------------------------------------------------
# Composite, decay, scenarios
# ---------------------------------------------------------------------------

def compute_composite(tech: float, trend: float, market: float, ai_exposure: float) -> float:
    return (
        COMPOSITE_WEIGHTS["technical_moat"] * tech
        + COMPOSITE_WEIGHTS["trend_alignment"] * trend
        + COMPOSITE_WEIGHTS["market_demand"] * market
        + COMPOSITE_WEIGHTS["ai_disruption_exposure_inverted"] * (100.0 - ai_exposure)
    )


def compute_lambda(ai_exposure: float) -> float:
    return (ai_exposure / 100.0) * LAMBDA_SCALE


def project_moat(m0: float, lam: float, horizon_years: int = 5) -> list[dict]:
    return [
        {
            "year": t,
            "moat_score": round(m0 * math.exp(-lam * t), 2),
            "decay_pct": round(100.0 * (1.0 - math.exp(-lam * t)), 2),
        }
        for t in range(0, horizon_years + 1)
    ]


def compute_scenario(
    tech: float,
    trend: float,
    market: float,
    ai_exposure: float,
    scenario: str,
) -> dict:
    adj = SCENARIO_ADJUSTMENTS[scenario]
    trend_adj = clamp(trend + adj["trend_alignment_delta"])
    market_adj = clamp(market + adj["market_demand_delta"])
    m0 = compute_composite(tech, trend_adj, market_adj, ai_exposure)
    lam = compute_lambda(ai_exposure) * adj["lambda_multiplier"]
    projection = project_moat(m0, lam, 5)
    return {
        "scenario": scenario,
        "probability": adj["probability"],
        "m0": round(m0, 2),
        "lambda": round(lam, 4),
        "y5_score": projection[-1]["moat_score"],
        "projection": projection,
        "adjustments_applied": {
            "trend_alignment_delta": adj["trend_alignment_delta"],
            "market_demand_delta": adj["market_demand_delta"],
            "lambda_multiplier": adj["lambda_multiplier"],
        },
    }


def verdict_for(y5: float) -> str:
    for threshold, label in VERDICT_THRESHOLDS:
        if y5 >= threshold:
            return label
    return VERDICT_THRESHOLDS[-1][1]


# ---------------------------------------------------------------------------
# Override application
# ---------------------------------------------------------------------------

def apply_overrides(axis_inputs: dict, overrides: list[dict]) -> dict:
    """Return a copy of axis_inputs with overrides applied. Records original values."""
    import copy
    applied = copy.deepcopy(axis_inputs)
    trace = []
    for ov in overrides:
        path = ov["path"]  # e.g., "axis_inputs.technical_moat.code_complexity_score"
        # Strip leading "axis_inputs." if present
        if path.startswith("axis_inputs."):
            path = path[len("axis_inputs."):]
        parts = path.split(".")
        target = applied
        for p in parts[:-1]:
            target = target[p]
        key = parts[-1]
        original = target.get(key)
        target[key] = ov["new_value"]
        trace.append({
            "path": ov["path"],
            "original_value": original,
            "new_value": ov["new_value"],
            "justification": ov.get("justification", ""),
            "evidence_citations": ov.get("evidence_citations", []),
        })
    return applied, trace


# ---------------------------------------------------------------------------
# Confidence intervals (Monte Carlo)
# ---------------------------------------------------------------------------

def monte_carlo_composite(
    tech_sub: dict, trend_sub: dict, market_sub: dict, ai_sub: dict,
    confidence_levels: dict,
) -> dict:
    """Sample sub-scores within their confidence intervals, recompute composite, return CI."""
    import random
    rng = random.Random(MONTE_CARLO_SEED)

    # Build list of (axis, field, point, half_width) tuples
    samples_spec = []
    for axis_name, sub_dict, weight_map in [
        ("technical_moat", tech_sub, TECHNICAL_MOAT_WEIGHTS),
        ("market_demand", market_sub, MARKET_DEMAND_WEIGHTS),
        ("ai_disruption_exposure", ai_sub, AI_EXPOSURE_WEIGHTS),
    ]:
        for field in weight_map:
            if field == "tam_cagr_pct":
                # tam is a CAGR; sample around its value too
                point = float(sub_dict.get(field, sub_dict.get("tam_cagr_pct", 0)))
                hw = CONFIDENCE_HALF_WIDTHS[confidence_levels.get(f"{axis_name}.{field}", "medium")]
                samples_spec.append((axis_name, field, point, hw, "raw"))
            else:
                point = float(sub_dict[field])
                hw = CONFIDENCE_HALF_WIDTHS[confidence_levels.get(f"{axis_name}.{field}", "medium")]
                samples_spec.append((axis_name, field, point, hw, "0_100"))

    # For trend_alignment, the sub-scores are signed; sample within ±hw of raw value
    for field in TREND_ALIGNMENT_WEIGHTS:
        point = float(trend_sub[field])
        hw = CONFIDENCE_HALF_WIDTHS[confidence_levels.get(f"trend_alignment.{field}", "medium")]
        samples_spec.append(("trend_alignment", field, point, hw, "signed"))

    composites = []
    for _ in range(MONTE_CARLO_SAMPLES):
        # Sample each sub-score
        sampled = {axis: {} for axis in ["technical_moat", "trend_alignment", "market_demand", "ai_disruption_exposure"]}
        for axis, field, point, hw, kind in samples_spec:
            s = point + rng.uniform(-hw, hw)
            if kind == "0_100":
                s = clamp(s)
            elif kind == "signed":
                s = max(-100.0, min(100.0, s))
            sampled[axis][field] = s

        # Recompute axes
        t = sum(sampled["technical_moat"][f] * w for f, w in TECHNICAL_MOAT_WEIGHTS.items())
        tr_sub_0_100 = {f: map_signed_to_0_100(sampled["trend_alignment"][f]) for f in TREND_ALIGNMENT_WEIGHTS}
        tr = sum(tr_sub_0_100[f] * w for f, w in TREND_ALIGNMENT_WEIGHTS.items())
        tam_s = tam_cagr_to_score(sampled["market_demand"]["tam_cagr_pct"])
        m = (
            tam_s * MARKET_DEMAND_WEIGHTS["tam_cagr_pct"]
            + sampled["market_demand"]["buyer_alignment_score"] * MARKET_DEMAND_WEIGHTS["buyer_alignment_score"]
            + map_signed_to_0_100(sampled["market_demand"]["regulatory_score"]) * MARKET_DEMAND_WEIGHTS["regulatory_score"]
            + sampled["market_demand"]["competitive_density_score"] * MARKET_DEMAND_WEIGHTS["competitive_density_score"]
        )
        a = (
            sampled["ai_disruption_exposure"]["feature_automatability_pct"] * AI_EXPOSURE_WEIGHTS["feature_automatability_pct"]
            + (100.0 - sampled["ai_disruption_exposure"]["proprietary_data_dependency_score"]) * AI_EXPOSURE_WEIGHTS["proprietary_data_dependency_score"]
            + sampled["ai_disruption_exposure"]["ux_commoditization_score"] * AI_EXPOSURE_WEIGHTS["ux_commoditization_score"]
            + sampled["ai_disruption_exposure"]["workflow_complexity_score"] * AI_EXPOSURE_WEIGHTS["workflow_complexity_score"]
        )
        c = compute_composite(clamp(t), clamp(tr), clamp(m), clamp(a))
        composites.append(c)

    composites.sort()
    p5 = composites[int(0.05 * len(composites))]
    p95 = composites[int(0.95 * len(composites)) - 1]
    return {
        "samples": MONTE_CARLO_SAMPLES,
        "seed": MONTE_CARLO_SEED,
        "p5": round(p5, 2),
        "p95": round(p95, 2),
        "interval": [round(p5, 2), round(p95, 2)],
    }


# ---------------------------------------------------------------------------
# Main scoring
# ---------------------------------------------------------------------------

def score(data: dict, run_monte_carlo: bool = False) -> dict:
    errors = validate_input(data)
    if errors:
        return {
            "error": "validation_failed",
            "validation_errors": errors,
            "script_version": SCRIPT_VERSION,
        }

    axis_inputs = data["axis_inputs"]
    overrides = data.get("overrides", [])
    if overrides:
        axis_inputs, override_trace = apply_overrides(axis_inputs, overrides)
    else:
        override_trace = []

    # Compute axes
    tech = compute_technical_moat(axis_inputs["technical_moat"])
    trend = compute_trend_alignment(axis_inputs["trend_alignment"])
    market = compute_market_demand(axis_inputs["market_demand"])
    ai = compute_ai_disruption_exposure(axis_inputs["ai_disruption_exposure"])

    # Composite
    m0 = compute_composite(
        tech["axis_score"], trend["axis_score"], market["axis_score"], ai["axis_score"]
    )
    lam = compute_lambda(ai["axis_score"])
    base_projection = project_moat(m0, lam, 5)

    # Scenarios
    scenarios = {
        name: compute_scenario(
            tech["axis_score"], trend["axis_score"], market["axis_score"], ai["axis_score"], name
        )
        for name in SCENARIO_ADJUSTMENTS
    }

    # Expected Y5 (probability-weighted)
    expected_y5 = sum(
        scenarios[name]["y5_score"] * SCENARIO_ADJUSTMENTS[name]["probability"]
        for name in SCENARIO_ADJUSTMENTS
    )
    expected_m0 = sum(
        scenarios[name]["m0"] * SCENARIO_ADJUSTMENTS[name]["probability"]
        for name in SCENARIO_ADJUSTMENTS
    )

    verdict = verdict_for(expected_y5)

    # Confidence intervals (Monte Carlo)
    ci = None
    if run_monte_carlo:
        # Build confidence_levels dict from data, defaulting to "medium"
        confidence_levels = data.get("confidence_levels", {})
        ci = monte_carlo_composite(
            axis_inputs["technical_moat"],
            axis_inputs["trend_alignment"],
            axis_inputs["market_demand"],
            axis_inputs["ai_disruption_exposure"],
            confidence_levels,
        )
        ci["composite_m0_point_estimate"] = round(m0, 2)
        ci["composite_m0_within_ci"] = ci["p5"] <= m0 <= ci["p95"]

    # Build output
    output = {
        "script_version": SCRIPT_VERSION,
        "scoring_methodology_version": SCORING_METHODOLOGY_VERSION,
        "computed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_hash": hash_dict({"axis_inputs": axis_inputs, "project_name": data["project_name"]}),
        "project_name": data["project_name"],
        "axes": {
            "technical_moat": tech,
            "trend_alignment": trend,
            "market_demand": market,
            "ai_disruption_exposure": ai,
        },
        "composite": {
            "m0": round(m0, 2),
            "lambda": round(lam, 4),
            "base_projection": base_projection,
            "weights": COMPOSITE_WEIGHTS,
        },
        "scenarios": scenarios,
        "expected_y5": round(expected_y5, 2),
        "expected_m0": round(expected_m0, 2),
        "verdict": verdict,
        "verdict_thresholds": VERDICT_THRESHOLDS,
        "overrides_applied": override_trace,
        "confidence_interval": ci,
        "calculation_trace": [
            {
                "step": "axis_computation",
                "description": "Each axis score = weighted sum of sub-scores per scoring-methodology.md weights",
            },
            {
                "step": "composite",
                "description": f"M0 = 0.30*Tech + 0.20*Trend + 0.25*Market + 0.25*(100-AIExp)",
                "values": {
                    "tech": tech["axis_score"],
                    "trend": trend["axis_score"],
                    "market": market["axis_score"],
                    "ai_exposure": ai["axis_score"],
                    "ai_inverted": round(100 - ai["axis_score"], 2),
                    "result": round(m0, 2),
                },
            },
            {
                "step": "lambda",
                "description": f"lambda = (AIExp/100) * {LAMBDA_SCALE}",
                "values": {"ai_exposure": ai["axis_score"], "result": round(lam, 4)},
            },
            {
                "step": "projection",
                "description": "M(t) = M0 * exp(-lambda * t) for t in 0..5",
                "values": {"m0": round(m0, 2), "lambda": round(lam, 4)},
            },
            {
                "step": "scenarios",
                "description": "Same projection under bull/base/bear scenario adjustments",
                "values": {name: scenarios[name]["y5_score"] for name in scenarios},
            },
            {
                "step": "expected_y5",
                "description": "E[Y5] = 0.25*bull + 0.50*base + 0.25*bear",
                "values": {"expected_y5": round(expected_y5, 2)},
            },
            {
                "step": "verdict",
                "description": "Verdict assigned from E[Y5] using fixed thresholds",
                "values": {"expected_y5": round(expected_y5, 2), "verdict": verdict},
            },
        ],
    }

    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Deterministic moat scoring engine")
    parser.add_argument("input", help="Path to scoring_input.json")
    parser.add_argument("--monte-carlo", action="store_true", help="Run Monte Carlo confidence intervals")
    parser.add_argument("--validate", action="store_true", help="Validate input only, do not score")
    parser.add_argument("--version", action="version", version=f"moat_calculator.py v{SCRIPT_VERSION}")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    if args.validate:
        errors = validate_input(data)
        if errors:
            for e in errors:
                print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        print("VALID", file=sys.stderr)
        return

    result = score(data, run_monte_carlo=args.monte_carlo)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if "error" in result:
        sys.exit(2)


if __name__ == "__main__":
    main()
