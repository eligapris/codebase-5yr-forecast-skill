# Codebase 5-Year Forecast

**Repository:** [github.com/eligapris/codebase-5yr-forecast-skill](https://github.com/eligapris/codebase-5yr-forecast-skill)

A Cursor Agent Skill that produces a reproducible, evidence-backed **5-year survival and moat forecast** for any codebase, app, or product idea.

The LLM gathers evidence and writes the narrative; **deterministic Python scripts do the scoring.** Same inputs → same scores → same verdict.

**Verdicts:** Durable · Eroding · At Risk · Terminal

---

## Install

### Option A — Skills CLI (agent instructions only)

```bash
npx skills add eligapris/codebase-5yr-forecast-skill -g -y
```

| Flag | Purpose |
|------|---------|
| `-g` | Global install (all projects) |
| `-y` | Skip prompts |

Updates: `npx skills check` · `npx skills update`

### Option B — Full clone (scripts + references + PDF generator)

Required if you want the scoring engine and report generator on disk.

**Cursor (personal):**

```bash
git clone https://github.com/eligapris/codebase-5yr-forecast-skill.git ~/.cursor/skills/codebase-5yr-forecast
```

**Codex:**

```bash
git clone https://github.com/eligapris/codebase-5yr-forecast-skill.git ~/.codex/skills/codebase-5yr-forecast
```

**Project-level (team shared):**

```bash
git clone https://github.com/eligapris/codebase-5yr-forecast-skill.git .cursor/skills/codebase-5yr-forecast
```

**Python deps** (for `scripts/` only):

```bash
pip install matplotlib numpy reportlab
```

> `npx skills add` installs `SKILL.md` for chat. Clone the repo when you need `scripts/`, `references/`, and `assets/`.

---

## Use

1. Install (above).
2. In Cursor (or any agent with the skill loaded), ask for a forecast:

```
Run a 5-year forecast on ~/my-app
```

```
What's the moat of https://github.com/org/repo?
```

```
Should I pivot? Here's my product idea: …
```

3. The agent runs the 6-phase workflow and returns the **headline verdict**, plus paths to the **PDF** and **JSON** bundle.

### Inputs (auto-detected)

| Input | Example |
|-------|---------|
| Local path | `~/projects/my-app` |
| GitHub URL | `https://github.com/org/repo` |
| Pitch only | Prose description (lower confidence on technical moat) |

### Trigger phrases

`forecast` · `moat analysis` · `5-year projection` · `AI disruption risk` · `should I pivot` · `is my project still relevant` · `tech stack longevity`

**Not for:** bug triage, code review, short-term roadmaps, or general architecture advice.

### Outputs

- `<project>_5yr_forecast.pdf` — verdict, scorecard, Y0–Y5 decay curve, bull/base/bear scenarios, pivot or defend plan
- `<project>_5yr_forecast.json` — machine-readable bundle (scores, evidence, calculation trace, input hash)
- `forecast_work/` — intermediate artifacts (`scan.json`, `evidence.json`, `scoring_input.json`, `scores.json`) for audit

---

## How it works (short)

```
Agent (LLM)  →  gather evidence, fill scoring_input.json
       ↓
codebase_scanner.py  →  scan.json
moat_calculator.py   →  scores.json   ← canonical numbers; LLM never overrides
generate_report.py   →  PDF + JSON
```

Details: [`SKILL.md`](SKILL.md) (agent workflow) · [`references/scoring-methodology.md`](references/scoring-methodology.md) (formulas) · [`references/data-sources.md`](references/data-sources.md) (evidence sources)

---

## Layout

```
codebase-5yr-forecast/
├── SKILL.md                 # Agent instructions
├── scripts/                 # Scanner, scorer, report generator
├── references/              # Methodology, data sources, pivot playbook
└── assets/report_schema.json
```

---

## License

Part of the eligapris Cursor skills collection.
