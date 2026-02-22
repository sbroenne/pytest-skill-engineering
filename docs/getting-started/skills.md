---
description: "Add domain knowledge to AI agents with Agent Skills following the agentskills.io specification. Test whether skills improve agent performance."
---

# Agent Skills

An **Agent Skill** is a domain knowledge module following the [agentskills.io](https://agentskills.io/specification) specification. Skills provide:

- **Instructions** — Domain knowledge and behavioral guidelines for the agent
- **References** — On-demand documents the agent can look up

## Creating a Skill

A skill is a directory with a `SKILL.md` file:

```
financial-advisor/
├── SKILL.md           # Instructions (required)
└── references/        # On-demand lookup docs (optional)
    └── budgeting-guide.md
```

### SKILL.md Format

```markdown
---
name: financial-advisor
description: Guidelines for personal finance management
---

# Financial Advisor Guidelines

## Budget Analysis
- Follow the 50/30/20 rule: 50% needs, 30% wants, 20% savings
- Emergency fund should cover 3-6 months of expenses
- Track spending categories: housing, food, transport, entertainment

## Red Flags
- Savings below 10% of income
- No emergency fund
- High-interest debt accumulating

For detailed budgeting advice, use the reference document.
```

## Skill References

References are documents the agent can look up **on demand** rather than having them always in context. When a skill has a `references/` directory, two virtual tools are automatically injected:

| Tool | Description |
|------|-------------|
| `list_skill_references` | Lists available reference documents |
| `read_skill_reference` | Reads a specific document by filename |

### Example Reference Document

```markdown title="references/budgeting-guide.md"
# Budgeting Guide

## The 50/30/20 Rule
- 50% Needs: rent, utilities, groceries, insurance
- 30% Wants: dining out, entertainment, shopping
- 20% Savings: emergency fund, investments, debt payoff

## Building an Emergency Fund
- Start with $1,000 mini-fund
- Build to 3 months of expenses
- Keep in high-yield savings account
- Don't invest emergency fund
...
```

### How the Agent Uses References

When you tell the skill to "use the reference document for budgeting advice", the agent will:

1. Call `list_skill_references()` → sees `budgeting-guide.md`
2. Call `read_skill_reference(filename="budgeting-guide.md")` → gets the content
3. Use that content to formulate a detailed response

This keeps your base prompt lean while providing detailed information when needed.

### When to Use References vs Instructions

| Use Instructions (SKILL.md) | Use References |
|-----------------------------|----------------|
| Core decision logic | Detailed lookup tables |
| Always-needed context | Supplementary details |
| Short, critical rules | Long documentation |
| < 500 tokens | > 500 tokens per doc |

**Example**: Put budget analysis rules in SKILL.md, but detailed budgeting breakdowns in `references/budgeting-guide.md`.

## Using a Skill

```python
from pytest_skill_engineering import Agent, Provider, MCPServer, Skill

skill = Skill.from_path("skills/financial-advisor")

agent = Agent(
    name="with-skill",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[banking_server],
    skill=skill,
)
```

## Testing Skill Effectiveness

Compare agents with and without skills:

```python
skill = Skill.from_path("skills/financial-advisor")

agent_without_skill = Agent(
    name="without-skill",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[banking_server],
)

agent_with_skill = Agent(
    name="with-skill",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[banking_server],
    skill=skill,
)

AGENTS = [agent_without_skill, agent_with_skill]

@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_financial_advice(aitest_run, agent):
    """Does the skill improve financial recommendations?"""
    result = await aitest_run(
        agent, 
        "I have $5,000 to allocate. How should I split it between needs, savings, and wants?"
    )
    assert result.success
```

The report shows whether the skill improves performance.

## Next Steps

- [Comparing Configurations](comparing.md) — Systematic testing patterns
- [Multi-Turn Sessions](sessions.md) — Conversations with context

> 📁 **Real Examples:**
> - [test_skills.py](https://github.com/sbroenne/pytest-skill-engineering/blob/main/tests/integration/test_skills.py) — Skill loading and metadata
> - [test_skill_improvement.py](https://github.com/sbroenne/pytest-skill-engineering/blob/main/tests/integration/test_skill_improvement.py) — Skill before/after comparisons

## Copilot Skills

> **Are you testing a skill for GitHub Copilot?** Use `CopilotAgent` with `skill_directories` instead — **not** `Agent` + `Skill.from_path()`.

The `Agent` + `Skill` approach above tests whether a *generic LLM* can leverage skill content via injected tools. It does **not** test how GitHub Copilot itself loads and uses the skill.

When your skill is built for Copilot (e.g. distributed via `npx skills add`), you want the real Copilot agent to load it — exactly as end users will experience it:

```python
from pytest_skill_engineering.copilot import CopilotAgent

async def test_skill_presents_scenarios(copilot_run):
    agent = CopilotAgent(
        name="with-skill",
        skill_directories=["skills/my-skill"],  # loads SKILL.md + references/
        max_turns=10,
    )
    result = await copilot_run(agent, "What can you help me with?")
    assert result.success
    assert "baseline" in result.final_response.lower()
```

Copilot loads the skill natively — no synthetic tool injection. MCP servers configured in `~/.copilot/mcp-config.json` (or via the session's `mcp_servers`) are available automatically.

See [Test Coding Agents](../how-to/test-coding-agents.md#testing-skills) for a full example.
