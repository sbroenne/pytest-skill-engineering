---
description: "Add domain knowledge to AI agents with Eval Skills following the agentskills.io specification. Test whether skills improve agent performance."
---

# Eval Skills

An **Eval Skill** is a domain knowledge module following the [agentskills.io](https://agentskills.io/specification) specification. Skills provide:

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

References are documents the agent can look up **on demand** rather than having
them always in context. Copilot loads skills natively and can read their
`references/` files using its file tools. The supplied personas also expose
`list_skill_references` and `read_skill_reference` for validated enabled
references. `client_mode="empty"` does not inject persona tools.

Reference documents may be organized in subdirectories, for example
`references/commands/read.md`. Link to them directly from `SKILL.md` using paths
relative to the skill root. The specification's advice to keep reference chains
one level deep is not a ban on nested folders.

The package validates all reference files recursively as nonempty UTF-8 Markdown.
`Skill.references` uses paths relative to `references/`, with `/` separators on
every platform: `commands/read.md`. Flat names such as `budgeting-guide.md` are
unchanged, and equal basenames in different folders remain distinct.
Reference tools use these same relative paths. Disabled skills are not
advertised or readable through the reference tools. This does not block ordinary
filesystem access by other tools. Duplicate relative reference paths across
enabled skills are rejected rather than silently replacing a document.
Links are accepted only when their resolved targets stay within `references/`;
the `references/` directory itself must resolve within the skill directory.
Broken links, directory cycles, unreadable entries, and non-file entries are
explicit errors. These checks also apply to Windows directory junctions.

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

### How the Eval Uses References

When you tell the skill to "use the reference document for budgeting advice", the agent will:

1. Read the skill's guidance about when to consult references
2. Read `references/budgeting-guide.md` with its available file tools
3. Use that content to formulate a detailed response

This keeps the skill's main instructions lean while providing detail when needed.

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
from pytest_skill_engineering.copilot import CopilotEval

agent = CopilotEval(
    name="with-skill",
    client_mode="empty",
    skill_directories=["skills/financial-advisor"],
)
```

Supply either a directory containing `SKILL.md` or its parent containing multiple
immediate skill directories. Relative paths are resolved from the Python process's
current directory, not `working_directory`.

Explicit `skill_directories` enable native SDK skill loading automatically,
including in `client_mode="empty"`. This does **not** enable ambient configuration
discovery. Empty mode still excludes personal/project skills and custom instructions,
file hooks, managed settings, and persona-provided instructions/tools. Supply the
tools needed by your task explicitly; empty mode's default tool list is empty.

Before sending the task, the runner validates every requested skill using the
existing skill format checks, then checks availability through the public SDK
`session.rpc.skills.ensure_loaded()`, `reload()`, and `list()` APIs. Missing,
unreadable, invalid, duplicate-name, or undiscovered skills return
`success=False`, `stop_reason="execution_error"`, and a setup error without
sending a model message. A parent with no immediate `SKILL.md` files is an error;
unrelated child directories without `SKILL.md` are not skill packages.
SDK loading warnings are logged and saved; loading errors stop execution.
There is still only one execution attempt.

`extra_config={"enable_skills": False}` conflicts with nonempty explicit
directories and raises `ValueError` from `build_session_config()`. For a
no-skill baseline, remove the directories instead. To deliberately disable
particular discovered skills, use `disabled_skills=["skill-name"]`; these skills
remain in discovery evidence with `enabled=False`. Passthrough directories follow
the same enable/check rules and cannot replace a nonempty `skill_directories` field.

`result.skill_discovery` records actual SDK metadata and loading diagnostics,
not a claim that the agent read or followed a skill. Observed reads remain
ordinary tool-call evidence. No setup check tells the agent to read a skill.

### Preflight Without Model Execution

Use the existing public `load_skill()` function (or `Skill.from_path()`) before
an SDK discovery probe:

```python
from pytest_skill_engineering import load_skill

# Each path must identify an individual skill, not a parent collection.
skill = load_skill(r"skills\financial-advisor")
assert skill.name == "financial-advisor"
print(sorted(skill.references))
```

This uses the same local format, reference, and readability validation as the
evaluation runner. It starts no client and sends no model message; invalid input
raises `SkillError`. For a parent collection, call it for each immediate child
containing `SKILL.md`; a collection with no such children is not a valid input.

Then use `CopilotEval.build_session_config()` and the public SDK
`session.rpc.skills.ensure_loaded()`, `reload()`, and `list()` APIs to check
discovered paths, names, enabled state, and loading errors, without calling
`send()` or `send_and_wait()`. Local validation and SDK discovery are separate
checks: SDK discovery alone does not exercise the package's local validation,
and `load_skill()` alone does not prove runtime availability or detect duplicate
names across multiple skill directories.

## Testing Skill Effectiveness

Compare agents with and without skills:

```python
from pytest_skill_engineering.copilot import CopilotEval

agent_without_skill = CopilotEval(
    name="without-skill",
    instructions="You are a banking assistant.",
)

agent_with_skill = CopilotEval(
    name="with-skill",
    instructions="You are a banking assistant.",
    skill_directories=["skills/financial-advisor"],
)

AGENTS = [agent_without_skill, agent_with_skill]


@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_financial_advice(copilot_eval, agent):
    """Does the skill improve financial recommendations?"""
    result = await copilot_eval(
        agent, "I have $5,000 to allocate. How should I split it between needs, savings, and wants?"
    )
    assert result.success
```

This example checks session completion only, not advice quality or skill
effectiveness. Add fixed checks of concrete output, such as exact allocation
amounts in a JSON artifact, to establish task correctness. Compare both sides
with the same checks and repeat representative cases before claiming improvement.

## Next Steps

- [Comparing Configurations](comparing.md) — Systematic testing patterns
- [Multi-Turn Sessions](sessions.md) — Conversations with context

> 📁 **Real Examples:**
> - [copilot/test_05_skills.py](https://github.com/sbroenne/pytest-skill-engineering/blob/main/tests/integration/copilot/test_05_skills.py) — Skill loading and A/B comparisons

## Copilot Skills

Use `CopilotEval` with `skill_directories` to test native skill loading.
`Skill.from_path()` loads skill metadata for inspection and other skill workflows;
it is not a `CopilotEval` constructor argument.

When your skill is built for Copilot (e.g. distributed via `npx skills add`), you want the real Copilot agent to load it — exactly as end users will experience it:

```python
from pytest_skill_engineering.copilot import CopilotEval


async def test_skill_presents_scenarios(copilot_eval):
    agent = CopilotEval(
        name="with-skill",
        skill_directories=["skills/my-skill"],  # loads SKILL.md + references/
        max_turns=10,
    )
    result = await copilot_eval(agent, "What can you help me with?")
    assert result.success
    assert "baseline" in result.final_response.lower()
```

Copilot loads the skill natively — no synthetic tool injection. Attach required
MCP servers through `mcp_servers`; ambient SDK configuration discovery is disabled
by default. See [Configuration](../reference/configuration.md) for the explicit
discovery opt-in.

See [Test Coding Agents](../how-to/test-coding-agents.md#testing-skills) for a full example.

The framework does not distribute a companion skill for its own use. Testing
your domain skills remains supported; the
[case study](../use-cases/companion-skill.md) explains the distinction.
