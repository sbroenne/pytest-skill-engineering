---
description: "Compare LLM models, skills, custom agent versions, and server configurations side-by-side. Find the most cost-effective setup with automated leaderboards."
---

# Comparing Configurations

The power of pytest-skill-engineering is comparing different configurations to find what works best — whether that's models, skill versions, or custom agent files.

## Pattern 1: Explicit Configurations

Define agents with meaningful names when testing distinct approaches:

```python
from pytest_skill_engineering.copilot import CopilotEval

# Compare: no skill vs with skill
agent_baseline = CopilotEval(
    name="baseline",
    instructions="You are a banking assistant.",
)

agent_with_skill = CopilotEval(
    name="with-skill",
    instructions="You are a banking assistant.",
    skill_directories=["skills/financial-advisor"],
)

# Compare: two versions of a custom agent file
from pytest_skill_engineering.core.evals import load_custom_agent

agent_v1 = CopilotEval(
    name="advisor-v1",
    custom_agents=[load_custom_agent(".github/agents/advisor-v1.agent.md")],
)

agent_v2 = CopilotEval(
    name="advisor-v2",
    custom_agents=[load_custom_agent(".github/agents/advisor-v2.agent.md")],
)

AGENTS = [agent_baseline, agent_with_skill, agent_v1, agent_v2]

@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_balance_query(copilot_eval, agent):
    """Which configuration handles balance queries best?"""
    result = await copilot_eval(agent, "What's my checking balance?")
    assert result.success
```

**Use explicit configurations when:**

- Testing conceptually different approaches (baseline vs skill, v1 vs v2)
- Names have meaning ("with-skill", "without-skill")
- You want full control over each configuration

## Pattern 2: Generated Configurations

Generate configurations from all permutations for systematic testing:

```python
from pathlib import Path
from pytest_skill_engineering.copilot import CopilotEval

MODELS = ["gpt-5.4-mini", "gpt-4.1"]
SKILL_VERSIONS = [path.stem for path in Path("skills").iterdir() if path.is_dir()]

# Generate all combinations: 2 models × N skill versions
AGENTS = [
    CopilotEval(
        name=f"{model}-{skill_name}",
        model=model,
        skill_directories=[f"skills/{skill_name}"],
    )
    for model in MODELS
    for skill_name in SKILL_VERSIONS
]

@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_balance_query(copilot_eval, agent):
    """Test with different model/skill combinations."""
    result = await copilot_eval(agent, "What's my checking balance?")
    assert result.success
```

**Use generated configurations when:**

- Testing all combinations systematically
- Looking for interactions (e.g., "skill v2 works with gpt-4.1 but fails with gpt-5.4-mini")
- Comparing multiple dimensions at once

## What the Report Shows

The report shows an **Eval Leaderboard** (auto-detected when multiple agents are tested):

| Eval | Pass Rate | Tokens | Cost |
|-------|-----------|--------|------|
| gpt-5.4-mini-v2 | 100% | 747 | $0.002 |
| gpt-4.1-v2 | 100% | 560 | $0.008 |
| gpt-5.4-mini-v1 | 90% | 1,203 | $0.004 |
| gpt-4.1-v1 | 90% | 892 | $0.012 |

**Winning eval:** Highest pass rate → lowest cost (tiebreaker).

This helps you answer:

- "Does skill v2 outperform v1?"
- "Can I use a cheaper model with my tools?"
- "Which custom agent instructions produce better behavior?"

## Next Steps

- [Custom Agents](custom-agents.md) — A/B test agent instruction files
- [A/B Testing Servers](ab-testing-servers.md) — Compare server implementations
- [Multi-Turn Sessions](sessions.md) — Test conversations with context

> 📁 **Real Examples:**
> - [pydantic/test_01_basic.py](https://github.com/sbroenne/pytest-skill-engineering/blob/main/tests/integration/pydantic/test_01_basic.py) — Single agent workflows
> - [pydantic/test_04_matrix.py](https://github.com/sbroenne/pytest-skill-engineering/blob/main/tests/integration/pydantic/test_04_matrix.py) — Multi-dimension comparison
