#!/usr/bin/env python3
"""Deterministic 5-year forecast for a product in a world where agents are the main users.

    python3 forecast.py --template > scoring_input.json   # blank input to fill in
    python3 forecast.py scoring_input.json --validate      # check ranges and citations
    python3 forecast.py scoring_input.json > scores.json   # score it
    python3 forecast.py scoring_input.json --md            # same, as Markdown tables

The agent gathers evidence and fills in the inputs. This script does all the math,
so the same inputs always give the same numbers. Formulas and weights are in
references/scoring-methodology.md and must stay in sync with this file.

Python 3.8+, standard library only.
"""
import argparse
import json
import math
import sys

VERSION = "0.0.1"

# The 10 agent-readiness questions from the agent-led-product scorecard (0, 0.5 or 1).
QUESTIONS = {
    "q1_actions_via_api_or_mcp": "Can an agent do every core action through an API or MCP tool?",
    "q2_cli": "Is there a CLI with machine-readable output?",
    "q3_agent_docs": "Are the docs agent-readable (llms.txt, OpenAPI, /.well-known/mcp, SKILL.md)?",
    "q4_headless_auth": "Can an agent authenticate without a browser, with scoped access?",
    "q5_per_action_pricing": "Is pricing per action or outcome, not per seat?",
    "q6_data_moat": "Does it own data a model can't recreate?",
    "q7_sells_outcome": "Does it sell a finished outcome, not just a tool?",
    "q8_audit_and_approval": "Are agent actions audited and risky ones human-approved?",
    "q9_ui_inside_agents": "Can its UI render inside the agents people use (MCP Apps, A2UI)?",
    "q10_model_resilience": "Does a better model make it stronger, not obsolete?",
}

# Forecast-only inputs, 0-100 unless noted. "higher_is_better" drives the sensitivity check.
SIGNALS = {
    "agent_native_overlap": ("How much of the product's value a frontier agent already delivers without it (0-100)", False),
    "distribution": ("Strength of distribution: audience, channels, directory listings, partners (0-100)", True),
    "switching_cost": ("Cost for a customer to leave, including data and workflow lock-in (0-100)", True),
    "demand_trend": ("Direction of demand for the problem over 5 years (-100 to +100)", True),
    "competitive_density": ("How crowded the space is, including agent-native entrants (0-100)", False),
}

# agent-led-product scan.py "provisional.questions" keys, mapped to ours.
SCAN_KEYS = {
    "Q1_api_mcp": "q1_actions_via_api_or_mcp", "Q2_cli": "q2_cli", "Q3_agent_docs": "q3_agent_docs",
    "Q4_scoped_keys": "q4_headless_auth", "Q5_action_pricing": "q5_per_action_pricing",
    "Q6_proprietary_data": "q6_data_moat", "Q7_sells_outcome": "q7_sells_outcome",
    "Q8_audit_approval": "q8_audit_and_approval", "Q9_ui_in_agents": "q9_ui_inside_agents",
    "Q10_model_resilient": "q10_model_resilience",
}

CONFIDENCE_SPREAD = {"high": 3.0, "medium": 8.0, "low": 15.0}

WEIGHTS = {"moat": 0.30, "model_resilience": 0.25, "agent_readiness": 0.25, "market": 0.20}
SCENARIOS = {  # name: (probability, decay multiplier, overlap shift, demand shift)
    "bull": (0.25, 0.6, -15.0, 20.0),
    "base": (0.50, 1.0, 0.0, 0.0),
    "bear": (0.25, 1.5, 20.0, -20.0),
}
VERDICTS = [(55, "Durable"), (40, "Eroding"), (20, "At risk: pivot required"), (-1, "Terminal")]


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def axes(q, s):
    """Axis scores 0-100 from question values (0-1) and signal values."""
    readiness = 100 * (q["q1_actions_via_api_or_mcp"] * 0.25 + q["q2_cli"] * 0.10 + q["q3_agent_docs"] * 0.15
                       + q["q4_headless_auth"] * 0.20 + q["q8_audit_and_approval"] * 0.20 + q["q9_ui_inside_agents"] * 0.10)
    moat = 0.35 * 100 * q["q6_data_moat"] + 0.25 * 100 * q["q7_sells_outcome"] + 0.20 * s["distribution"] + 0.20 * s["switching_cost"]
    resilience = 0.5 * 100 * q["q10_model_resilience"] + 0.5 * (100 - s["agent_native_overlap"])
    market = 0.5 * (s["demand_trend"] + 100) / 2 + 0.25 * 100 * q["q5_per_action_pricing"] + 0.25 * (100 - s["competitive_density"])
    return {"agent_readiness": readiness, "moat": moat, "model_resilience": resilience, "market": market}


def decay(q, s, ax):
    """Yearly decay constant. Agents doing the job natively, plus being unusable by agents, both speed it up."""
    exposure = (s["agent_native_overlap"] / 100) * (1 - q["q10_model_resilience"])
    unready = 1 - ax["agent_readiness"] / 100
    return 0.02 + 0.20 * exposure + 0.06 * unready


def project(q, s, decay_mult=1.0, overlap_shift=0.0, demand_shift=0.0):
    s = dict(s)
    s["agent_native_overlap"] = clamp(s["agent_native_overlap"] + overlap_shift, 0, 100)
    s["demand_trend"] = clamp(s["demand_trend"] + demand_shift, -100, 100)
    ax = axes(q, s)
    m0 = sum(WEIGHTS[k] * ax[k] for k in WEIGHTS)
    lam = decay(q, s, ax) * decay_mult
    curve = [m0 * math.exp(-lam * t) for t in range(6)]
    return ax, m0, lam, curve


def verdict(y5):
    return next(label for cut, label in VERDICTS if y5 >= cut)


def values(inp):
    q = {k: float(inp["agent_readiness"][k]["value"]) for k in QUESTIONS}
    s = {k: float(inp["signals"][k]["value"]) for k in SIGNALS}
    return q, s


def shifted(inp, direction):
    """Every input moved by its confidence spread, all in the good (+1) or bad (-1) direction."""
    q, s = values(inp)
    for k in QUESTIONS:
        spread = CONFIDENCE_SPREAD[inp["agent_readiness"][k].get("confidence", "low")] / 100
        q[k] = clamp(q[k] + direction * spread, 0, 1)
    for k, (_, good_up) in SIGNALS.items():
        spread = CONFIDENCE_SPREAD[inp["signals"][k].get("confidence", "low")]
        lo, hi = (-100, 100) if k == "demand_trend" else (0, 100)
        s[k] = clamp(s[k] + (direction if good_up else -direction) * spread, lo, hi)
    return q, s


def moves(q, s, base_y5):
    """Year-5 gain from fixing each input on its own: the ranked list of what to do next."""
    out = []
    for k in QUESTIONS:
        if q[k] < 1:
            q2 = dict(q, **{k: 1.0})
            out.append((k, QUESTIONS[k], project(q2, s)[3][5] - base_y5))
    for k, (label, good_up) in SIGNALS.items():
        target = 100 if good_up else 0
        if s[k] != target:
            s2 = dict(s, **{k: float(target)})
            out.append((k, label, project(q, s2)[3][5] - base_y5))
    out.sort(key=lambda m: -m[2])
    return [{"input": k, "what": label, "y5_gain": round(g, 1)} for k, label, g in out if g > 0.05]


def validate(inp):
    errors, warnings = [], []
    if not inp.get("project"):
        errors.append("project: name is missing")
    for group, keys in (("agent_readiness", QUESTIONS), ("signals", SIGNALS)):
        block = inp.get(group, {})
        for k in keys:
            item = block.get(k)
            if not isinstance(item, dict) or "value" not in item:
                errors.append(f"{group}.{k}: missing")
                continue
            v = item["value"]
            if not isinstance(v, (int, float)):
                errors.append(f"{group}.{k}: value must be a number")
                continue
            if group == "agent_readiness" and v not in (0, 0.5, 1):
                errors.append(f"{group}.{k}: must be 0, 0.5 or 1 (got {v})")
            if group == "signals":
                lo, hi = (-100, 100) if k == "demand_trend" else (0, 100)
                if not lo <= v <= hi:
                    errors.append(f"{group}.{k}: must be {lo} to {hi} (got {v})")
            conf = item.get("confidence", "low")
            if conf not in CONFIDENCE_SPREAD:
                errors.append(f"{group}.{k}: confidence must be high, medium or low")
            if not item.get("evidence"):
                if conf != "low":
                    errors.append(f"{group}.{k}: no evidence cited, so confidence must be low")
                else:
                    warnings.append(f"{group}.{k}: unsourced (scored with low confidence)")
        for k in block:
            if k not in keys:
                warnings.append(f"{group}.{k}: unknown input, ignored")
    return errors, warnings


def score(inp):
    q, s = values(inp)
    ax, m0, lam, curve = project(q, s)
    scen = {}
    for name, (p, mult, dov, ddem) in SCENARIOS.items():
        _, _, l2, c2 = project(q, s, mult, dov, ddem)
        scen[name] = {"probability": p, "decay": round(l2, 4), "curve": [round(x, 1) for x in c2]}
    expected_y5 = sum(scen[n]["probability"] * scen[n]["curve"][5] for n in scen)
    lo = project(*shifted(inp, -1))[3][5]
    hi = project(*shifted(inp, +1))[3][5]
    _, warnings = validate(inp)
    return {
        "project": inp["project"],
        "forecast_version": VERSION,
        "axes": {k: round(v, 1) for k, v in ax.items()},
        "weights": WEIGHTS,
        "m0": round(m0, 1),
        "decay_per_year": round(lam, 4),
        "curve": [round(x, 1) for x in curve],
        "y5": round(curve[5], 1),
        "y5_range": [round(lo, 1), round(hi, 1)],
        "verdict": verdict(curve[5]),
        "scenarios": scen,
        "expected_y5": round(expected_y5, 1),
        "agent_readiness_score": round(sum(q.values()), 1),
        "top_moves": moves(q, s, curve[5])[:5],
        "warnings": warnings,
    }


def markdown(r):
    lines = [f"## {r['project']}: {r['verdict']}", "",
             f"Year 5 score **{r['y5']}** (range {r['y5_range'][0]} to {r['y5_range'][1]} from input confidence), "
             f"expected across scenarios **{r['expected_y5']}**. Starting score {r['m0']}, losing "
             f"{(1 - math.exp(-r['decay_per_year'])) * 100:.0f}% a year. Agent-readiness scorecard: {r['agent_readiness_score']}/10.", "",
             "| Year | 0 | 1 | 2 | 3 | 4 | 5 |", "|---|---|---|---|---|---|---|"]
    for name in ("bull", "base", "bear"):
        c = r["scenarios"][name]["curve"]
        lines.append(f"| {name} ({int(r['scenarios'][name]['probability'] * 100)}%) | " + " | ".join(str(x) for x in c) + " |")
    lines += ["", "| Axis | Score | Weight |", "|---|---|---|"]
    for k, v in r["axes"].items():
        lines.append(f"| {k.replace('_', ' ')} | {v} | {r['weights'][k]} |")
    if r["top_moves"]:
        lines += ["", "| Move | Year 5 gain |", "|---|---|"]
        for m in r["top_moves"]:
            lines.append(f"| {m['what']} | +{m['y5_gain']} |")
    if r["warnings"]:
        lines += ["", "Warnings:"] + [f"- {w}" for w in r["warnings"]]
    return "\n".join(lines)


def template(scan=None):
    item = lambda: {"value": None, "confidence": "low", "evidence": [], "note": ""}
    t = {
        "project": "",
        "agent_readiness": {k: dict(item(), question=v) for k, v in QUESTIONS.items()},
        "signals": {k: dict(item(), question=v[0]) for k, v in SIGNALS.items()},
        "evidence": [{"id": "E1", "claim": "", "source": "", "retrieved_at": ""}],
    }
    if scan:
        # Start from the scanner's provisional answers; each still has to be confirmed by reading the code.
        t["project"] = scan.get("project", "")
        for theirs, ours in SCAN_KEYS.items():
            v = scan.get("provisional", {}).get("questions", {}).get(theirs)
            if v is not None:
                t["agent_readiness"][ours].update(value=v, note="provisional from scan.py: confirm with a file path, then raise confidence")
            else:
                t["agent_readiness"][ours]["note"] = "needs judgment (see the scorecard rubric)"
    return t


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", nargs="?", help="scoring_input.json")
    ap.add_argument("--template", action="store_true", help="print a blank scoring input")
    ap.add_argument("--from-scan", metavar="SCAN_JSON", help="with --template: pre-fill q1-q10 from agent-led-product's scan.py output")
    ap.add_argument("--validate", action="store_true", help="check the input only")
    ap.add_argument("--md", action="store_true", help="print Markdown tables instead of JSON")
    ap.add_argument("--version", action="version", version=f"forecast.py {VERSION}")
    a = ap.parse_args()
    if a.template:
        scan = None
        if a.from_scan:
            with open(a.from_scan, encoding="utf-8") as f:
                scan = json.load(f)
        print(json.dumps(template(scan), indent=2))
        return 0
    if not a.input:
        ap.error("give a scoring_input.json, or --template")
    with open(a.input, encoding="utf-8") as f:
        inp = json.load(f)
    errors, warnings = validate(inp)
    if errors or a.validate:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        if a.validate and not errors:
            print("ok")
        return 1 if errors else 0
    r = score(inp)
    print(markdown(r) if a.md else json.dumps(r, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
