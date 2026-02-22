---
description: "AI-powered test analysis that tells you what to fix. Get deployment recommendations, tool feedback, prompt improvements, and cost optimizations."
---

# AI Analysis

Every pytest-skill-engineering report includes AI-generated analysis. An LLM reads your test results and produces actionable feedback — not just metrics.

## Why It's Mandatory

Traditional test reports tell you *what* failed:

```
Tests: 47 passed, 3 failed
```

For AI tool testing, this is useless. A test might fail because your tool description is ambiguous, your parameter name is confusing, or your system prompt contradicts itself. Metrics can't diagnose these problems.

pytest-skill-engineering **requires** an AI model to generate reports:

```bash
pytest tests/ --aitest-html=report.html --aitest-summary-model=azure/gpt-5.2-chat
```

Without `--aitest-summary-model`, report generation will error. See [How to Generate Reports](../how-to/generate-reports.md) for full configuration options.

## What the AI Produces

The analysis model receives your complete test results — tool calls, responses, timing, costs — and produces structured markdown covering these areas:

| Section | What It Tells You |
|---------|-------------------|
| **🎯 Recommendation** | Which agent to deploy and why |
| **❌ Failure Analysis** | Root cause + fix for each failed test |
| **🔧 MCP Tool Feedback** | Specific tool description improvements |
| **📝 System Prompt Feedback** | Instruction conflicts and rewrites |
| **📚 Skill Feedback** | Domain knowledge gaps |
| **� Optimizations** | Ways to reduce turns, tokens, and cost |
| **📦 Tool Response Optimization** | Reduce token waste in tool return values |

Not every section appears in every report — the AI only produces sections relevant to your test data.

## Quality Rules

The analysis prompt enforces strict rules for consistent, useful output:

- **No speculation** — Only analyze what's in the test results
- **No generic advice** — Every suggestion references specific test data
- **Exact rewrites** — Don't say "make it clearer", provide the exact new text
- **Cite test IDs** — Reference specific tests when discussing failures
- **Concise** — 3 good insights beat 10 vague ones

## Cost

The summary model analyzes your test results, which are relatively small:

| Tests | Approx. Input Tokens | Cost (gpt-5.2-chat) |
|-------|----------------------|---------------------|
| 10    | ~2,000               | $0.01               |
| 50    | ~8,000               | $0.04               |
| 200   | ~30,000              | $0.15               |

## Sample Reports

See these example reports to understand what pytest-skill-engineering generates:

| Report | Scenario | What It Shows |
|--------|----------|---------------|
| [Single Agent](../reports/01_single_agent.html) | One agent, multiple tests | Basic report structure, AI analysis |
| [Multi-Agent Comparison](../reports/02_multi_agent.html) | Two agents compared | Agent leaderboard, side-by-side results |
| [Sessions](../reports/03_multi_agent_sessions.html) | Multi-turn conversations | Session grouping, context flow |
| [Agent Selector](../reports/04_agent_selector.html) | 3+ agents | Agent selector UI, pick any 2 to compare |
