---
description: "Understand Evals in pytest-skill-engineering: CopilotEval combines the GitHub Copilot coding agent with skills, custom agents, and working directory configuration."
---

# Evals

The core concept in pytest-skill-engineering.

## What is an Eval?

An **Eval** (specifically `CopilotEval`) is a test configuration that bundles everything needed to run a test using the **real GitHub Copilot coding agent**.

```
CopilotEval = Copilot Agent + Skills + Custom Agents + Instructions
```

```python
from pytest_skill_engineering.copilot import CopilotEval

agent = CopilotEval(
    name="banking-test",
    instructions="You are a banking assistant.",
    skill_directories=["skills/banking-advisor"],  # Optional
    max_turns=10,
)
```

## The Eval is NOT What You Test

**You don't test evals. You USE evals to test:**

| Target | Question |
|--------|----------|
| **MCP Server** | Can Copilot understand and use my tools? |
| **Agent Skill** | Does this domain knowledge improve performance? |
| **Custom Agent** | Do these `.agent.md` instructions trigger proper subagent dispatch? |
| **Tool Descriptions** | Can Copilot discover and use tools correctly? |

The Eval is the **test harness** that bundles the GitHub Copilot coding agent with the configuration you want to evaluate.

## CopilotEval Components

| Component | Required | Example |
|-----------|----------|---------|
| Name | ✓ | `"banking-test"` |
| Instructions | Optional | `"You are a helpful assistant."` |
| Skills | Optional | `skill_directories=["skills/banking"]` |
| Custom Agents | Optional | `custom_agents=[load_custom_agent("agents/reviewer.agent.md")]` |
| Model | Optional | `model="gpt-5.2"` (defaults to Copilot's active model) |
| Working Directory | Optional | `working_directory=str(tmp_path)` |

## Eval Leaderboard

**When you test multiple evals, the report shows an Eval Leaderboard.**

This happens automatically — no configuration needed. Just parametrize your tests:

```python
from pathlib import Path
import pytest
from pytest_skill_engineering import Eval, Provider, MCPServer, Skill

banking_server = MCPServer(command=["python", "banking_mcp.py"])

SKILLS = {
    "v1": Skill.from_path("skills/financial-advisor-v1"),
    "v2": Skill.from_path("skills/financial-advisor-v2"),
}

@pytest.mark.parametrize("skill_name,skill", SKILLS.items())
async def test_banking(eval_run, skill_name, skill):
    agent = Eval(
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[banking_server],
        skill=skill,
    )
    result = await eval_run(agent, "What's my checking balance?")
    assert result.success
```

The report shows:

| Eval | Pass Rate | Cost |
|-------|-----------|------|
| gpt-5-mini (v1) | 100% | $0.002 |
| gpt-5-mini (v2) | 100% | $0.004 |

## Winning Criteria

**Winning Eval = Highest pass rate → Lowest cost (tiebreaker)**

1. **Pass rate** (primary) — 100% beats 95%, always
2. **Cost** (tiebreaker) — Among equal pass rates, cheaper wins

## Dimension Detection

The AI analysis detects *what varies* between evals to provide targeted feedback:

| What Varies | AI Feedback Focuses On |
|-------------|------------------------|
| Model | Which model works best with your tools |
| Skill | Whether domain knowledge helps |
| Custom Agent | Which `.agent.md` instructions produce better behavior |
| Server | Which implementation is more reliable |

This is for **AI analysis only** — the leaderboard always appears when multiple evals are tested.

## Examples

### Compare Models

```python
MODELS = ["azure/gpt-5-mini", "azure/gpt-4.1"]
banking_server = MCPServer(command=["python", "banking_mcp.py"])

@pytest.mark.parametrize("model", MODELS)
async def test_with_model(eval_run, model):
    agent = Eval(
        provider=Provider(model=model),
        mcp_servers=[banking_server],
    )
    result = await eval_run(agent, "What's my checking balance?")
    assert result.success
```

### Compare Custom Agent Versions

A/B test two versions of a `.agent.md` file to find which instructions work better:

```python
from pathlib import Path
from pytest_skill_engineering import Eval, Provider

AGENT_VERSIONS = {
    path.stem: path
    for path in Path(".github/agents").glob("reviewer-*.agent.md")
}

@pytest.mark.parametrize("name,path", AGENT_VERSIONS.items())
async def test_reviewer(eval_run, name, path):
    agent = Eval.from_agent_file(
        path,
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[code_server],
    )
    result = await eval_run(agent, "Review src/auth.py for security issues")
    assert result.success
```

### Compare Multiple Dimensions

```python
MODELS = ["gpt-5-mini", "gpt-4.1"]
SKILLS = {
    "v1": Skill.from_path("skills/advisor-v1"),
    "v2": Skill.from_path("skills/advisor-v2"),
}

@pytest.mark.parametrize("model", MODELS)
@pytest.mark.parametrize("skill_name,skill", SKILLS.items())
async def test_combinations(eval_run, model, skill_name, skill):
    agent = Eval(
        provider=Provider(model=f"azure/{model}"),
        mcp_servers=[banking_server],
        skill=skill,
    )
    result = await eval_run(agent, "What's my checking balance?")
    assert result.success
```

## Custom Agents

A **custom agent** is a specialized sub-agent defined in a `.agent.md` or `.md` file with YAML frontmatter (`name`, `description`, `tools`) and a markdown prompt body.

```python
from pytest_skill_engineering import Eval, Provider

# Load and test a custom agent's instructions synthetically
agent = Eval.from_agent_file(
    ".github/agents/reviewer.agent.md",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[code_server],
)
```

The `tools` frontmatter field maps to `allowed_tools` — restricting which tools the agent can call. See [Custom Agents](../getting-started/custom-agents.md) for a full guide.

## Next Steps

- [Choosing a Test Harness](choosing-a-harness.md) — `Eval` vs `CopilotEval`: full trade-off guide
- [Comparing Configurations](../getting-started/comparing.md) — More comparison patterns
- [A/B Testing Servers](../getting-started/ab-testing-servers.md) — Test server versions
- [AI Analysis](ai-analysis.md) — What the AI evaluation produces
