# Where the evidence comes from

Record every data point in the `evidence` list of `scoring_input.json`:

```json
{"id": "E4", "claim": "Competitor X shipped an MCP server with 30 tools", "source": "https://...", "retrieved_at": "2026-10-19"}
```

Cite the ids on the inputs they support. Label vendor and aggregator numbers as
estimates. Never invent a source or a number; an input with nothing behind it is
scored with low confidence.

## The product itself (inputs q1 to q10)

- The agent-led-product scanner gives the action inventory and a provisional
  scorecard: `python3 -I ~/.agents/skills/agent-led-product/scripts/scan.py <path> --out scan.json --md`.
  Treat its signals as hints. Open the files it points to and score each question
  yourself, with a file path as evidence.
- README, pricing page, docs site, `llms.txt`, `/.well-known/mcp`, OpenAPI spec.
- For a pitch with no code, score q1 to q4, q8 and q9 from what the pitch commits to,
  all with low confidence.

## agent_native_overlap

The most important input, and the easiest to fake. Measure it.

1. Write down the product's top 3 user jobs in one sentence each.
2. Give each job to a frontier agent with web search and no access to the product.
3. Record how far it got, with the date and the model. That's the evidence.

Also search for the job plus "ChatGPT", "Claude", "Gemini" and "built-in" to catch
features a model vendor or OS has shipped or announced.

Then check whether the job is already an installable skill or MCP server. A free skill
with real adoption raises the overlap as much as a model doing it natively:

```bash
python3 -I ~/.agents/skills/lean-venture-analyst/scripts/skill_landscape.py "<job 1>" "<job 2>" --json > <work>/landscape.json
```

Record the best on-topic match (installs, link, date) as evidence. An on-topic skill
with 1,000+ installs, or an official vendor skill or server, means agents can already
do that job for anyone who installs it; score the overlap for that job accordingly.

## distribution and competitive_density

- Competitors' sites: do they have an API, MCP server, CLI, agent docs, per-action
  pricing? A competitor that's agent-ready raises density more than one that isn't.
- MCP and agent directories (the official MCP registry, Smithery, mcp.so, glama.ai),
  the Claude and ChatGPT app directories, Product Hunt, GitHub topics.
- Funding and acquisitions in the space (press releases, Crunchbase-style searches).

## switching_cost

The product's own data model: what accumulates per customer (history, records,
integrations), and whether there's an export. Regulated records count heavily.

## demand_trend

Market sizing and growth for the problem (not the product), regulatory changes that
create or remove demand, and search interest over time. Prefer primary sources
(government statistics, filings, standards bodies) over listicles.

## Market context for the narrative

`~/.agents/skills/agent-led-product/references/evidence.md` holds dated, verified
evidence about the shift to agents (headless products, MCP Apps, per-action pricing,
"sell the work"), the five bets ranked by evidence, what not to build, and quotes
known to be fabricated. Use it for the "why" in the report, and don't repeat the
fabricated quotes it lists.
