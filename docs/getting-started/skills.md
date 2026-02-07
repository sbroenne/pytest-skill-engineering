# Agent Skills

An **Agent Skill** is a domain knowledge module following the [agentskills.io](https://agentskills.io/specification) specification. Skills provide:

- **Instructions** — Prepended to the system prompt
- **References** — On-demand documents the agent can look up

## Creating a Skill

A skill is a directory with a `SKILL.md` file:

```
weather-expert/
├── SKILL.md           # Instructions (required)
└── references/        # On-demand lookup docs (optional)
    └── clothing-guide.md
```

### SKILL.md Format

```markdown
---
name: weather-expert
description: Guidelines for interpreting weather data
---

# Weather Expert Guidelines

## Temperature Interpretation
- Below 0°C: Freezing, warn about ice
- 0-10°C: Cold, recommend warm clothing  
- 10-20°C: Mild, light jacket sufficient
- Above 20°C: Warm, no jacket needed

For clothing recommendations, use the reference document.
```

## Skill References

References are documents the agent can look up **on demand** rather than having them always in context. When a skill has a `references/` directory, two virtual tools are automatically injected:

| Tool | Description |
|------|-------------|
| `list_skill_references` | Lists available reference documents |
| `read_skill_reference` | Reads a specific document by filename |

### Example Reference Document

```markdown title="references/clothing-guide.md"
# Clothing Guide by Temperature

## Freezing (Below 0°C)
- Heavy winter coat, insulated
- Thermal layers underneath
- Hat, gloves, scarf essential
- Waterproof boots

## Cold (0-10°C)
- Warm jacket or coat
- Sweater or fleece layer
- Light gloves optional
...
```

### How the Agent Uses References

When you tell the skill to "use the reference document for clothing recommendations", the agent will:

1. Call `list_skill_references()` → sees `clothing-guide.md`
2. Call `read_skill_reference(filename="clothing-guide.md")` → gets the content
3. Use that content to formulate a detailed response

This keeps your base prompt lean while providing detailed information when needed.

### When to Use References vs Instructions

| Use Instructions (SKILL.md) | Use References |
|-----------------------------|----------------|
| Core decision logic | Detailed lookup tables |
| Always-needed context | Supplementary details |
| Short, critical rules | Long documentation |
| < 500 tokens | > 500 tokens per doc |

**Example**: Put temperature interpretation rules in SKILL.md, but detailed clothing recommendations in `references/clothing-guide.md`.

## Using a Skill

```python
from pytest_aitest import Agent, Provider, MCPServer, Skill

skill = Skill.from_path("skills/weather-expert")

agent = Agent(
    name="with-skill",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[weather_server],
    skill=skill,
)
```

## Testing Skill Effectiveness

Compare agents with and without skills:

```python
skill = Skill.from_path("skills/weather-expert")

agent_without_skill = Agent(
    name="without-skill",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[weather_server],
)

agent_with_skill = Agent(
    name="with-skill",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[weather_server],
    skill=skill,
)

AGENTS = [agent_without_skill, agent_with_skill]

@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_clothing_recommendation(aitest_run, agent):
    """Does the skill improve clothing recommendations?"""
    result = await aitest_run(
        agent, 
        "It's 5°C in Paris. What should I wear?"
    )
    assert result.success
```

The report shows whether the skill improves performance.

## Next Steps

- [Comparing Configurations](comparing.md) — Systematic testing patterns
- [Multi-Turn Sessions](sessions.md) — Conversations with context

> 📁 **Real Examples:**
> - [test_skills.py](https://github.com/sbroenne/pytest-aitest/blob/main/tests/integration/test_skills.py) — Skill loading and metadata
> - [test_skill_improvement.py](https://github.com/sbroenne/pytest-aitest/blob/main/tests/integration/test_skill_improvement.py) — Skill before/after comparisons
