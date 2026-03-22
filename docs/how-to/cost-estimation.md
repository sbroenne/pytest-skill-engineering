---
description: "Configure cost estimation for accurate spending analysis. Use pricing.toml to define model costs."
---

# Cost Estimation

pytest-skill-engineering estimates the USD cost of each LLM call based on token counts and model pricing data. Costs appear in reports, eval leaderboards, and AI insights analysis.

## How It Works

Cost estimation uses `pricing.toml` files. If no pricing is found, the cost is `$0.00` and the model is flagged as missing. AI insights are automatically warned when any model lacks pricing, so cost-based recommendations are skipped.

## pricing.toml Configuration

Create a `pricing.toml` file in your project root (or any parent directory) to add pricing for your models:

```toml
# Per-million-token pricing.
[models]
"gpt-5-mini" = { input = 0.15, output = 0.60 }
"gpt-4.1-mini" = { input = 0.30, output = 1.20 }
"claude-sonnet-4" = { input = 3.00, output = 15.00 }
```

### Format

| Field | Type | Description |
|-------|------|-------------|
| `input` | float | Cost per **1 million** input tokens (USD) |
| `output` | float | Cost per **1 million** output tokens (USD) |

### Lookup Behavior

- `pricing.toml` is searched upward from the working directory
- The first file found is used
- The file is loaded once and cached for the test session

## Missing Pricing

When a model has no pricing:

- Cost is reported as `$0.00`
- The model is tracked internally
- AI insights receive a warning: *"Incomplete Pricing Data — do not use cost as a ranking factor"*
- The AI analysis focuses on pass rate, tool usage, and response quality instead

## Pricing Lookup Summary

```text
CopilotEval(model="gpt-5-mini")
         │
         ▼
┌─────────────────┐
│  pricing.toml   │──→ found? use it (per-million-token rates)
└─────────────────┘
         │ not found
         ▼
    cost = $0.00
    (model flagged, AI warned)
```
