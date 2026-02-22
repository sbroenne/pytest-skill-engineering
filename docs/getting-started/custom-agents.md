---
description: "Test custom agent definitions from .agent.md files. Use Eval.from_agent_file() for synthetic testing or load_custom_agent() with CopilotEval for real subagent dispatch."
---

# Custom Agents

A **custom agent** is a specialized AI sub-agent defined in a `.agent.md` file (VS Code format) or `.md` file (Claude Code format). These files describe the agent's purpose, instructions, and optional tool restrictions using YAML frontmatter and a markdown prompt body.

pytest-skill-engineering supports custom agent files as a first-class concept — you can test them synthetically with `Eval.from_agent_file()`, or test real Copilot subagent dispatch with `load_custom_agent()` + `CopilotEval`.

## Custom Eval File Format

Custom agent files use YAML frontmatter for metadata and a markdown body for the agent's instructions:

```markdown title=".github/agents/reviewer.agent.md"
---
name: reviewer
description: 'Code review specialist — identifies bugs and code quality issues'
tools:
  - read_file
  - list_directory
---

# Code Reviewer

You are a code review specialist. When asked to review code:

1. Read the relevant files using `read_file`
2. Check for bugs, security issues, and code quality problems
3. Provide actionable feedback with specific line references

Focus on correctness first, then maintainability.
```

### File Locations

| Format | Location | Description |
|--------|----------|-------------|
| VS Code | `.github/agents/*.agent.md` | VS Code Copilot custom agents |
| Claude Code | `.claude/agents/*.md` | Claude Code custom agents |

### Frontmatter Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Eval display name (optional — derived from filename if absent) |
| `description` | string | Short description of the agent's purpose |
| `tools` | list | Tool names this agent is restricted to (optional) |

Any additional frontmatter fields (e.g. `maturity`, `handoffs`) are preserved in `metadata` and can be accessed programmatically.

## Using with `Eval.from_agent_file()` (synthetic testing)

`Eval.from_agent_file()` loads a custom agent file and uses the prompt body as the agent's custom instructions. This lets you test whether the agent's instructions produce the expected behaviour using any LLM provider — no Copilot subscription required.

```python
import pytest
from pytest_skill_engineering import Eval, Provider, MCPServer

code_server = MCPServer(command=["python", "code_server.py"])

agent = Eval.from_agent_file(
    ".github/agents/reviewer.agent.md",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[code_server],
)

async def test_reviewer_reads_files(eval_run):
    """Reviewer should read files before giving feedback."""
    result = await eval_run(agent, "Review the authentication module in src/auth.py")
    assert result.success
    assert result.tool_was_called("read_file")
```

### What `from_agent_file()` does

- Sets the agent's custom instructions from the agent file's markdown body
- Sets `name` from the filename (e.g. `reviewer.agent.md` → `reviewer`)
- Maps `tools` frontmatter field to `allowed_tools` (restricts which tools the agent can call)
- Any kwarg you pass (e.g. `name=`, `max_turns=`) overrides the file values

### Overriding file values

```python
agent = Eval.from_agent_file(
    ".github/agents/reviewer.agent.md",
    provider=Provider(model="azure/gpt-4.1"),
    mcp_servers=[code_server],
    name="reviewer-smart",     # override the name
    max_turns=20,              # override max_turns
)
```

## Using with `load_custom_agent()` + `CopilotEval` (real dispatch)

`load_custom_agent()` and `load_custom_agents()` load agent files into dicts compatible with `CopilotEval.custom_agents`. This tests **real subagent dispatch** — Copilot natively loads and routes tasks to your sub-agents, exactly as end users experience it.

```python
from pytest_skill_engineering import load_custom_agent, load_custom_agents
from pytest_skill_engineering.copilot import CopilotEval

# Single agent
reviewer = load_custom_agent(".github/agents/reviewer.agent.md")

@pytest.mark.copilot
async def test_orchestrator_dispatches_to_reviewer(copilot_eval):
    agent = CopilotEval(
        name="orchestrator",
        instructions="Delegate code reviews to the reviewer agent.",
        custom_agents=[reviewer],
    )
    result = await copilot_eval(agent, "Review src/auth.py for security issues.")
    assert result.success
    # Check the sub-agent was invoked
    assert any(s.eval_name == "reviewer" for s in result.subagent_invocations)
```

### Load all agents from a directory

```python
from pytest_skill_engineering import load_custom_agents

agents = load_custom_agents(
    ".github/agents/",
    exclude={"orchestrator"},  # don't load the orchestrator as a sub-agent
)

@pytest.mark.copilot
async def test_orchestrator_with_all_subagents(copilot_eval):
    agent = CopilotEval(
        name="orchestrator",
        instructions="Delegate tasks to the appropriate specialist.",
        custom_agents=agents,
    )
    result = await copilot_eval(agent, "Create and review a calculator module.")
    assert result.success
```

### Asserting on `subagent_invocations`

```python
async def test_correct_agent_is_chosen(copilot_eval):
    agents = load_custom_agents(".github/agents/")

    agent = CopilotEval(
        name="orchestrator",
        instructions="Use specialist agents for each task.",
        custom_agents=agents,
    )
    result = await copilot_eval(agent, "Write unit tests for the billing module.")

    invoked = [s.eval_name for s in result.subagent_invocations]
    assert "test-writer" in invoked
    assert "reviewer" not in invoked  # reviewer shouldn't be invoked for test writing
```

## A/B Testing: with and without the agent

Compare behaviour with and without a custom agent to verify its instructions add value:

```python
from pytest_skill_engineering import load_custom_agent
from pytest_skill_engineering.copilot import CopilotEval

reviewer = load_custom_agent(".github/agents/reviewer.agent.md")

@pytest.mark.copilot
async def test_reviewer_improves_feedback_quality(copilot_eval):
    without = CopilotEval(
        name="no-reviewer",
        instructions="Review code when asked.",
    )
    with_reviewer = CopilotEval(
        name="with-reviewer",
        instructions="Delegate code review to the reviewer agent.",
        custom_agents=[reviewer],
    )

    r_without = await copilot_eval(without, "Review src/auth.py for security issues.")
    r_with    = await copilot_eval(with_reviewer, "Review src/auth.py for security issues.")

    # Specialist agent should produce more specific findings
    assert r_with.success
    assert len(r_with.final_response) > len(r_without.final_response)
```

## Choosing the right approach

| | `Eval.from_agent_file()` | `load_custom_agent()` + `CopilotEval` |
|---|---|---|
| **What runs the agent** | PydanticAI synthetic loop | Real GitHub Copilot (CLI SDK) |
| **Tests** | Eval's instructions (system prompt) | Real subagent dispatch and routing |
| **LLM** | Any provider (Azure, OpenAI, Copilot…) | GitHub Copilot only |
| **Speed** | Fast (in-process) | Slower (~5–10s CLI startup) |
| **Requires Copilot** | No | Yes (`gh auth login`) |
| **Best for** | Iterating on agent instructions in CI | End-to-end dispatch validation |

> **Rule of thumb:** Use `Eval.from_agent_file()` to iterate on and validate the agent's instructions. Use `load_custom_agent()` + `CopilotEval` to verify that Copilot correctly routes tasks to the right sub-agent.

See [Choosing a Test Harness](../explanation/choosing-a-harness.md) for a full comparison.

## Prompt Files (Slash Commands)

Alongside custom agents, VS Code and Claude Code support **prompt files** — reusable prompts that users invoke as slash commands (e.g. `/review`, `/explain`). These are the user-invocation side of the bundle, as opposed to custom agents which are the agent-configuration side.

| File | Location | Invoked as |
|------|----------|-----------|
| `review.prompt.md` | `.github/prompts/` | `/review` in Copilot Chat |
| `review.md` | `.claude/commands/` | `/review` in Claude Code |

Use `load_prompt_file()` to load the body of a prompt file and use it as a test input:

```python
from pytest_skill_engineering import Eval, Provider, MCPServer, load_prompt_file, load_prompt_files

code_server = MCPServer(command=["python", "code_server.py"])
agent = Eval(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[code_server],
)

async def test_review_prompt(eval_run):
    """The /review slash command produces actionable feedback."""
    prompt = load_prompt_file(".github/prompts/review.prompt.md")
    result = await eval_run(agent, prompt["body"])
    assert result.success
```

### Test all prompt files at once

```python
import pytest
from pytest_skill_engineering import load_prompt_files

PROMPTS = load_prompt_files(".github/prompts/")

@pytest.mark.parametrize("prompt", PROMPTS, ids=lambda p: p["name"])
async def test_prompt_files(eval_run, agent, prompt):
    """All slash commands produce a successful response."""
    result = await eval_run(agent, prompt["body"])
    assert result.success
```

### Format

Prompt files follow the same pattern as custom agent files — optional YAML frontmatter, markdown body:

```markdown title=".github/prompts/review.prompt.md"
---
description: Review code for quality and security issues
mode: agent
---

Review the current file for:
- Security vulnerabilities
- Performance issues
- Code style problems

Provide specific line numbers and suggested fixes.
```

`load_prompt_file()` returns `{"name", "body", "description", "metadata"}`. The `body` is what the user's slash command sends to the agent.

> **VS Code vs Claude Code:** VS Code files use `.prompt.md` extension in `.github/prompts/`. Claude Code files use plain `.md` in `.claude/commands/`. `load_prompt_files()` handles both — `.prompt.md` files take precedence if both exist with the same name.

## A/B Testing Eval Instructions

Iterating on a custom agent file? Test multiple versions side-by-side and let the leaderboard pick the winner.

Store each version as a separate file and parametrize over them:

```
.github/agents/
├── reviewer-v1.agent.md   # "Review code for any issues"
└── reviewer-v2.agent.md   # Focused checklist: security → correctness → style
```

```python
import pytest
from pathlib import Path
from pytest_skill_engineering import Eval, Provider, MCPServer

code_server = MCPServer(command=["python", "code_server.py"])
PROVIDER = Provider(model="azure/gpt-5-mini")

AGENT_VERSIONS = {
    path.stem: path
    for path in Path(".github/agents").glob("reviewer-*.agent.md")
}

@pytest.mark.parametrize("name,path", AGENT_VERSIONS.items())
async def test_reviewer_finds_security_issue(eval_run, name, path):
    agent = Eval.from_agent_file(path, provider=PROVIDER, mcp_servers=[code_server])
    result = await eval_run(agent, "Review src/auth.py for security vulnerabilities")
    assert result.success
    assert result.tool_was_called("read_file")
```

The AI analysis report auto-detects that the agent instructions vary and shows a leaderboard ranking each version by pass rate and cost.

> **Tip:** This works exactly the same for skills — swap `Eval.from_agent_file()` for `Eval(skill=Skill.from_path(...))` and parametrize over skill versions.

## Next Steps

- [Comparing Configurations](comparing.md) — A/B test agent variants systematically
- [Test Coding Agents](../how-to/test-coding-agents.md) — Full Copilot agent testing guide
- [Eval Skills](skills.md) — Add domain knowledge to agents
