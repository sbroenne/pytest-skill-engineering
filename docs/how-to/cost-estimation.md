---
description: "Configure cost estimation for accurate spending analysis. Use litellm auto-pricing, pricing.toml overrides, and understand how missing pricing affects AI insights."
---

# Cost Estimation

pytest-skill-engineering estimates the USD cost of each LLM call based on token counts and model pricing data. Costs appear in reports, agent leaderboards, and AI insights analysis.

## How It Works

Cost estimation follows a three-step lookup:

1. **User overrides** — `pricing.toml` entries checked first
2. **litellm exact match** — 2,500+ models with auto-maintained pricing
3. **Dated-version fallback** — if no exact match and the model has no date suffix, look for exactly one `{model}-YYYYMMDD` key in litellm

If no pricing is found in any source, the cost is `$0.00` and the model is flagged as missing. AI insights are automatically warned when any model lacks pricing, so cost-based recommendations are skipped.

## Default Behavior (Zero Config)

Most models work out of the box via litellm. No configuration needed:

```python
from pytest_skill_engineering import Agent, Provider

agent = Agent(
    provider=Provider(model="azure/gpt-5-mini"),  # ✅ litellm has pricing
    mcp_servers=[server],
)
```

## Dated-Version Fallback

When you use a dateless model name and litellm only has a dated variant, the fallback resolves it automatically — but only when exactly **one** dated version exists:

```python
# You write:
Provider(model="claude-sonnet-4")

# litellm has: claude-sonnet-4-20250514
# Exactly one match → uses its pricing ✅
```

If multiple dated versions exist, the fallback is skipped to avoid ambiguity. Use `pricing.toml` or the full dated key instead.

## pricing.toml Overrides

Create a `pricing.toml` file in your project root (or any parent directory) to add pricing for missing models or override existing entries:

```toml
# Per-million-token pricing.
[models]
"claude-sonnet-4" = { input = 3.00, output = 15.00 }
"azure/my-custom-deploy" = { input = 2.00, output = 8.00 }
"my-org/internal-model" = { input = 1.50, output = 6.00 }
```

### Format

| Field | Type | Description |
|-------|------|-------------|
| `input` | float | Cost per **1 million** input tokens (USD) |
| `output` | float | Cost per **1 million** output tokens (USD) |

### Lookup Behavior

- `pricing.toml` is searched upward from the working directory
- The first file found is used
- Entries override litellm — useful for correcting stale prices or private deployments
- The file is loaded once and cached for the test session

## Missing Pricing

When a model has no pricing in any source:

- Cost is reported as `$0.00`
- The model is tracked internally
- AI insights receive a warning: *"Incomplete Pricing Data — do not use cost as a ranking factor"*
- The AI analysis focuses on pass rate, tool usage, and response quality instead

### Finding the Right Model Key

Use litellm to check what keys exist for your model:

```python
from litellm import model_cost

# Search for a model
matches = [k for k in model_cost if "sonnet-4" in k]
for m in sorted(matches):
    print(m)
```

The model key in `Provider(model=...)` must match a litellm key or a `pricing.toml` entry for cost tracking to work.

## Pricing Lookup Order Summary

```text
Provider(model="azure/gpt-5-mini")
         │
         ▼
┌─────────────────┐
│  pricing.toml   │──→ found? use it (per-million-token rates)
└─────────────────┘
         │ not found
         ▼
┌─────────────────┐
│  litellm exact  │──→ found? use it (per-token rates)
└─────────────────┘
         │ not found
         ▼
┌─────────────────┐
│  dated fallback │──→ exactly one {model}-YYYYMMDD? use it
└─────────────────┘
         │ not found
         ▼
    cost = $0.00
    (model flagged, AI warned)
```
