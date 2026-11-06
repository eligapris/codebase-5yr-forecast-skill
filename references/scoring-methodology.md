# Scoring methodology

This is what `scripts/forecast.py` computes. If you change a number here, change it in
the script too; the script is the source of truth when they disagree.

## Why these inputs

Agents are becoming the main users of software (evidence in
`agent-led-product/references/evidence.md`). A product survives five years if agents
can use it, if it keeps something a model can't recreate, and if better models make it
stronger instead of redundant. Language rankings and framework stars don't predict
that, so they aren't inputs.

## Inputs

### The 10 agent-readiness questions (0, 0.5 or 1)

The same questions as the agent-led-product scorecard
(`agent-led-product/references/scorecard.md` has the full rubric and how to detect
each one). Score them with a file path as evidence, or a dated source for Q5 to Q7.

| Key | Question |
|---|---|
| q1_actions_via_api_or_mcp | Can an agent do every core action through an API or MCP tool? |
| q2_cli | Is there a CLI with machine-readable output? |
| q3_agent_docs | Are the docs agent-readable (llms.txt, OpenAPI, /.well-known/mcp, SKILL.md)? |
| q4_headless_auth | Can an agent authenticate without a browser, with scoped access? |
| q5_per_action_pricing | Is pricing per action or outcome, not per seat? |
| q6_data_moat | Does it own data a model can't recreate? |
| q7_sells_outcome | Does it sell a finished outcome, not just a tool? |
| q8_audit_and_approval | Are agent actions audited and risky ones human-approved? |
| q9_ui_inside_agents | Can its UI render inside the agents people use (MCP Apps, A2UI)? |
| q10_model_resilience | Does a better model make it stronger, not obsolete? |

### The 5 forecast signals

| Key | Range | What it measures | How to score it |
|---|---|---|---|
| agent_native_overlap | 0 to 100 | Share of the product's value a frontier agent (Claude, ChatGPT, Gemini with tools) already delivers with no product at all | Try the top 3 user jobs in a plain agent with web search. 0 = it can't start; 50 = it does half; 90 = it does the job |
| distribution | 0 to 100 | Reach: audience, channels, partners, listings in agent and MCP directories | 0 = none; 50 = a working channel; 90 = a channel competitors can't copy |
| switching_cost | 0 to 100 | What a customer loses by leaving: data, history, integrations, workflow | 0 = export and go; 50 = a week of migration; 90 = regulated records or years of history |
| demand_trend | -100 to +100 | Direction of demand for the problem itself over five years, whoever solves it | Cite market data; 0 = flat |
| competitive_density | 0 to 100 | How crowded the space is, counting agent-native entrants and the model vendors | 0 = empty; 50 = a few strong players; 90 = a model vendor ships it |

Each input carries `confidence` (high, medium, low) and `evidence` (ids from the
evidence list). An input with no evidence must be `low`.

## Axes (0 to 100)

- **Agent readiness** = 100 × (0.25·q1 + 0.10·q2 + 0.15·q3 + 0.20·q4 + 0.20·q8 + 0.10·q9)
- **Moat** = 0.35·(100·q6) + 0.25·(100·q7) + 0.20·distribution + 0.20·switching_cost
- **Model resilience** = 0.5·(100·q10) + 0.5·(100 − agent_native_overlap)
- **Market** = 0.5·((demand_trend + 100) / 2) + 0.25·(100·q5) + 0.25·(100 − competitive_density)

## Starting score and decay

- **Starting score** M₀ = 0.30·moat + 0.25·model resilience + 0.25·agent readiness + 0.20·market
- **Decay per year** λ = 0.02 + 0.20·exposure + 0.06·(1 − readiness/100),
  where exposure = (agent_native_overlap/100) × (1 − q10)
- **Projection** M(t) = M₀ · e^(−λt) for t = 0 to 5

The two decay terms are the two ways a product dies in the agent era: agents do the job
without it (exposure), or agents can't use it, so their users route around it
(unreadiness). The projection assumes nothing changes; the top-moves list shows what
changing one thing is worth.

## Scenarios

| Scenario | Probability | Decay | agent_native_overlap | demand_trend |
|---|---|---|---|---|
| bull | 25% | × 0.6 | −15 | +20 |
| base | 50% | × 1.0 | 0 | 0 |
| bear | 25% | × 1.5 | +20 | −20 |

Expected Year 5 is the probability-weighted average of the three.

## Confidence range

Every input is moved by its confidence spread (high 3, medium 8, low 15 points, or
0.03 / 0.08 / 0.15 for questions) in the bad direction, then in the good direction.
The two Year 5 results are the range.

## Verdict (base Year 5)

| Year 5 | Verdict |
|---|---|
| 55 and up | Durable |
| 40 to 54 | Eroding |
| 20 to 39 | At risk: pivot required |
| below 20 | Terminal |

## Top moves

For each input not already at its best value, the script sets it to its best on its
own and records the Year 5 gain. The list is ranked by gain. The first item is the
single move to recommend first, unless it's impossible for this product; then say why
and take the next one.

## Overrides

You may think a score is wrong. Don't edit the output. Change the input that's wrong,
cite why, and rerun, so the chain from evidence to number stays visible.
