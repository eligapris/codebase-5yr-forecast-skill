---
name: codebase-5yr-forecast
description: >-
  Forecasts whether a product, codebase or idea survives the next five years now
  that AI agents are becoming the main users of software. Scores whether agents can
  use it (API/MCP, CLI, agent docs, headless auth, approvals), whether agents or
  better models make it unnecessary, and what moat is left, then projects Year 0 to
  Year 5 with bull, base and bear cases and ranks the moves that raise Year 5 most.
  The math is a deterministic script, so the same evidence gives the same numbers.
  Use when the user asks "will my app survive", "5-year forecast", "is my product
  future-proof", "will AI kill my product", "moat analysis", "should I keep building
  this", "pivot or persevere", "headless", "agentic future", or wants a long-horizon
  outlook on a repo, GitHub URL or pitch.
metadata:
  version: 0.0.1
---

# Five-year forecast for the agent era

Software is going headless. More and more work reaches a product through an agent
(Claude, ChatGPT, Gemini, Cursor, a CLI) instead of a person clicking through
screens. So the five-year question for any product has two halves:

1. **Can agents use it?** If they can't, their users route around it.
2. **Do agents need it?** If a better model does the job alone, nobody does.

This skill answers both with evidence, turns the answers into a Year 0 to 5 curve,
and ends with the one move worth making first. The agent gathers the evidence and
writes the story; `scripts/forecast.py` does every calculation, so two runs on the
same evidence give the same numbers.

Read `references/scoring-methodology.md` before scoring, and
`references/data-sources.md` before gathering evidence.

## Works with agent-led-product

The agent-readiness half uses the 10-question scorecard from the `agent-led-product`
skill. If it's installed (`~/.agents/skills/agent-led-product`), use its scanner and
its rubric. If the project already has `docs/agent-led/AUDIT.md`, reuse those scores
and their citations instead of redoing them. If the skill isn't installed, the
methodology reference has the 10 questions; score them by reading the code.

## Workflow

### 1. Intake

Take whatever the user gave you: a local path, a GitHub URL (clone it with
`git clone --depth 1` into a temporary folder), or a pitch with no code. Read the
README, manifests and enough source to write two things:

- One sentence on what the product does and for whom.
- The **top 3 user jobs**, one sentence each. The overlap test in step 3 uses them.

### 2. Agent readiness (q1 to q10)

```bash
python3 -I ~/.agents/skills/agent-led-product/scripts/scan.py <project> --out <work>/scan.json --md
```

The scan finds MCP servers, CLIs, API routes, keys, agent docs, billing, audit logs
and approvals, plus an inventory of every action. Its scores are hints. Open the files
it points to and give each question 0, 0.5 or 1 with a file path as evidence. Q6, Q7
and Q10 need judgment; use the tests in the scorecard rubric.

### 3. Evidence for the five signals

Follow `references/data-sources.md`. The one input not to guess is
`agent_native_overlap`: give each of the top 3 jobs to a frontier agent with no
access to the product and record how far it gets. Record every data point with a
source and date in the `evidence` list.

### 4. Score

```bash
S=~/.agents/skills/codebase-5yr-forecast/scripts/forecast.py
python3 -I $S --template --from-scan <work>/scan.json > <work>/scoring_input.json
# q1-q10 arrive pre-filled from the scan (low confidence); confirm or correct each,
# fill q6, q7, q10 and the five signals, cite evidence ids
python3 -I $S <work>/scoring_input.json --validate
python3 -I $S <work>/scoring_input.json > <work>/scores.json
python3 -I $S <work>/scoring_input.json --md            # tables for the report
```

Never hand-edit `scores.json`. If a number looks wrong, the input behind it is wrong:
fix the input, cite why, rerun.

### 5. The plan

`scores.json` lists `top_moves`, ranked by how much each one raises Year 5.

- Durable or Eroding: a defend-and-extend plan of 3 moves from the top of that
  list, each with the files or product areas it touches and a rough effort.
- At risk or Terminal: 2 or 3 pivot directions. Use agent-led-product's STRATEGY
  mode and the five bets in its `references/evidence.md`. For each: who it serves,
  what an agent does with it, how it gets paid per action or outcome, what makes it
  hard to copy when code is free, an 18-month milestone, and a kill switch (the
  measured result that means stop).

When a top move is an agent-readiness gap, say which agent-led-product conversion
layer fixes it (L1 to L9), so the user can go straight to building.

### 6. Report

Write `docs/forecast/FORECAST.md` in the project (or wherever it keeps docs), and
keep `scoring_input.json` and `scores.json` next to it so the numbers can be
checked. Structure:

1. Verdict first: the label, Year 5 score and range, expected Year 5, the loss
   per year, and three sentences on why.
2. Can agents use it? The 10 questions with scores and citations.
3. Do agents need it? The overlap test results, job by job, dated.
4. The curve: the bull, base and bear table from `--md`, and what drives the decay.
5. Moat and market: the axis table, with the evidence behind each signal.
6. What to do: the plan from step 5, the first move on top.
7. Evidence index: every source with its retrieval date.

In chat, give only the verdict, the Year 5 score, the single first move and the path
to the report.

## Tone

The user wants the truth with numbers behind it.

- Lead with the verdict. Don't soften it: if Year 5 is 18, the word is Terminal.
- Every claim has a number, a file path or a dated source. Mark anything else
  `[unsourced]` and keep it out of the scoring.
- Skip "it depends" and "remains to be seen". The range from input confidence is
  how uncertainty gets said here.
- Be as clear about what's good as about what's bad. A Durable verdict deserves the
  same evidence as a Terminal one.

## Files

- `scripts/forecast.py`: template, validation, scoring, Markdown tables. Python 3.8+, no dependencies.
- `references/scoring-methodology.md`: inputs, formulas, weights, scenarios, thresholds.
- `references/data-sources.md`: where each input's evidence comes from and how to record it.
