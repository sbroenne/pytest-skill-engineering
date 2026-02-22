# Test Coding Agents

pytest-skill-engineering can test **real coding agents** like GitHub Copilot — not just synthetic agents backed by MCP servers.

## Install

```bash
uv add pytest-skill-engineering[copilot]
```

This installs the `github-copilot-sdk` package alongside pytest-skill-engineering.

## Quick Start

```python
from pytest_skill_engineering.copilot import CopilotEval

@pytest.mark.copilot
async def test_creates_module(copilot_eval, tmp_path):
    agent = CopilotEval(
        name="coder",
        instructions="Create production-quality Python code.",
        working_directory=str(tmp_path),
    )
    result = await copilot_eval(
        agent,
        "Create calculator.py with add, subtract, multiply, divide functions.",
    )
    assert result.success
    assert (tmp_path / "calculator.py").exists()
```

## CopilotEval Configuration

`CopilotEval` is the configuration object for Copilot SDK sessions:

```python
from pytest_skill_engineering.copilot import CopilotEval

agent = CopilotEval(
    name="my-agent",                    # Required: unique agent name
    instructions="Your instructions.",   # System prompt for the agent
    model="gpt-5.2",                     # Optional: model override
    working_directory=str(tmp_path),     # Working directory for file ops
    max_turns=25,                        # Max conversation turns
    timeout_s=300.0,                     # Timeout in seconds
    excluded_tools=["run_in_terminal"],  # Tools to block
    skill_directories=["./skills"],      # Skill directories to load
    reasoning_effort="high",             # Reasoning effort level
    custom_agents=[                      # Custom subagents
        {
            "name": "test-writer",
            "prompt": "Write pytest tests.",
            "description": "Writes unit tests.",
        }
    ],
)
```

## Fixtures

### `copilot_eval`

Runs a single Copilot agent against a task:

```python
result = await copilot_eval(agent, "Create hello.py with print('hello')")
```

Returns a `CopilotResult` with:

- `result.success` — Whether the session completed without errors
- `result.error` — Error message if failed
- `result.final_response` — Eval's final text response
- `result.all_tool_calls` — List of `ToolCall` objects
- `result.tool_was_called("name")` — Check if a tool was called
- `result.tool_names_called` — Set of tool names used
- `result.file("path")` — Read a file from the working directory
- `result.files_created` / `result.files_modified` — File tracking
- `result.usage` — Token usage info
- `result.total_cost_usd` — Estimated cost
- `result.subagent_invocations` — Custom agent dispatch events
- `result.reasoning_traces` — Reasoning effort traces
- `result.raw_events` — Full SDK event stream

### `ab_run`

Runs two agents against the same task in isolated directories:

```python
@pytest.mark.copilot
async def test_ab_comparison(ab_run, tmp_path):
    baseline = CopilotEval(name="baseline", instructions="Write minimal code.")
    treatment = CopilotEval(name="treatment", instructions="Write documented code.")

    b, t = await ab_run(baseline, treatment, "Create calculator.py with add and subtract.")

    assert b.success and t.success
    assert '"""' in t.file("calculator.py")  # Treatment has docstrings
```

## Custom Agents

Define subagents that the main agent can delegate to:

```python
agent = CopilotEval(
    name="orchestrator",
    instructions="Delegate test writing to the test-writer agent.",
    custom_agents=[
        {
            "name": "test-writer",
            "prompt": "Write pytest tests for the given code.",
            "description": "Writes unit tests.",
            "tools": ["create_file", "read_file"],  # Optional tool restriction
        }
    ],
)
```

### Loading from a file

Use `load_custom_agent()` to load a `.agent.md` file into a custom agent dict:

```python
from pytest_skill_engineering import load_custom_agent
from pytest_skill_engineering.copilot import CopilotEval

test_writer = load_custom_agent(".github/agents/test-writer.agent.md")

@pytest.mark.copilot
async def test_orchestrator_delegates_test_writing(copilot_eval):
    agent = CopilotEval(
        name="orchestrator",
        instructions="Delegate test writing to the test-writer agent.",
        custom_agents=[test_writer],
    )
    result = await copilot_eval(agent, "Write unit tests for calculator.py")
    assert result.success
```

### Loading all agents from a directory

Use `load_custom_agents()` to load all `.agent.md` files from a directory:

```python
from pytest_skill_engineering import load_custom_agents

# Load all sub-agents except the orchestrator
subagents = load_custom_agents(
    ".github/agents/",
    exclude={"orchestrator"},
)

@pytest.mark.copilot
async def test_full_agent_team(copilot_eval):
    agent = CopilotEval(
        name="orchestrator",
        instructions="Delegate tasks to the appropriate specialist.",
        custom_agents=subagents,
    )
    result = await copilot_eval(agent, "Create and test a calculator module.")
    assert result.success
```

Both functions are available directly from `pytest_skill_engineering` (no `[copilot]` extra required for loading):

```python
from pytest_skill_engineering import load_custom_agent, load_custom_agents
```

### Asserting on `result.subagent_invocations`

`CopilotResult.subagent_invocations` tracks which sub-agents were dispatched:

```python
async def test_correct_subagent_is_invoked(copilot_eval):
    agents = load_custom_agents(".github/agents/")
    agent = CopilotEval(
        name="orchestrator",
        instructions="Use specialist agents for each task.",
        custom_agents=agents,
    )
    result = await copilot_eval(agent, "Write unit tests for the billing module.")

    invoked = [s.eval_name for s in result.subagent_invocations]
    assert "test-writer" in invoked
```

## Testing Skills

Skills are domain knowledge packages loaded from a directory containing a `SKILL.md` file. Use `skill_directories` to inject a skill into a Copilot session — this is the right way to test Copilot skills, as it exercises the same loading path end users experience.

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
    assert "scenario-a" in result.final_response.lower()
```

### Comparing with and without skill

```python
async def test_skill_improves_routing(copilot_eval):
    without = CopilotEval(name="no-skill", max_turns=10)
    with_skill = CopilotEval(
        name="with-skill",
        skill_directories=["skills/my-skill"],
        max_turns=10,
    )

    r_without = await copilot_eval(without, "Get the ACR baseline for TPID 12345.")
    r_with    = await copilot_eval(with_skill, "Get the ACR baseline for TPID 12345.")

    # Skill should cause the agent to call the right tool
    assert r_with.tool_was_called("ExecuteQueries")
```

### When to use `CopilotEval` vs `Eval` + `Skill`

| | `CopilotEval` + `skill_directories` | `Eval` + `Skill.from_path()` |
|---|---|---|
| **What runs the agent** | Real GitHub Copilot (CLI SDK) | PydanticAI synthetic loop |
| **Skill loading** | Native Copilot skill loading | Injected as virtual reference tools |
| **MCP auth** | Handled by Copilot CLI (OAuth cached) | Managed by test process (token required) |
| **Use when** | Testing a Copilot skill end-to-end | Testing MCP servers / tool descriptions |

> **Rule of thumb:** If you built a `SKILL.md` for Copilot users, test it with `CopilotEval`. If you're testing whether your MCP server tools are discoverable and usable, use `Eval`.

## Skill Directories

Load skill files that inject domain knowledge into the agent:

```python
agent = CopilotEval(
    name="with-skills",
    instructions="Apply all standards from your skills.",
    skill_directories=["./skills"],
)
```

## Tool Restrictions

Block specific tools to control agent behavior:

```python
agent = CopilotEval(
    name="no-terminal",
    instructions="Create files only.",
    excluded_tools=["run_in_terminal"],
)
result = await copilot_eval(agent, "Create hello.py")
assert not result.tool_was_called("run_in_terminal")
```

## Reporting

Copilot test results flow into the same HTML report as synthetic tests. The report auto-detects whether tests used `eval_run` (synthetic) or `copilot_eval` (coding agent) and adapts the AI analysis accordingly.

## Copilot as Model Provider

If you have `pytest-skill-engineering[copilot]` installed, you can use Copilot-accessible models for **all** LLM calls in aitest — judge assertions, AI insights, scoring, and prompt optimization — without needing a separate Azure or OpenAI subscription.

Use the `copilot/` prefix:

```bash
# AI insights report
pytest tests/ --aitest-summary-model=copilot/gpt-5-mini --aitest-html=report.html

# LLM assertions and scoring
pytest tests/ --llm-model=copilot/gpt-5-mini
```

This routes calls through the Copilot SDK, authenticated via `gh auth login` or `GITHUB_TOKEN`. Available models are whatever your Copilot subscription provides (e.g., `gpt-5-mini`, `gpt-5.2`, `claude-opus-4.5`).

## Prompt Optimization with Copilot

`optimize_instruction` works with any model provider, including Copilot:

```python
from pytest_skill_engineering import optimize_instruction

async def test_optimize_system_prompt(optimize_instruction):
    result = await optimize_instruction(
        instruction="You are a helpful assistant.",
        test_cases=[
            {"prompt": "Transfer $100 to savings", "expected": "uses transfer tool"},
        ],
        judge_model="copilot/gpt-5-mini",
    )
    print(result.improved_instruction)
```

## Integration tests: `integration_judge_model` fixture

When writing integration tests that need an auxiliary LLM (for judge assertions, optimizer, etc.), use the `integration_judge_model` fixture instead of hard-coding a provider. It fails **loudly** if no provider is reachable.

```python
# tests/integration/conftest.py or your conftest

# The fixture is provided by pytest_skill_engineering and probes providers automatically.
# Override with env var if needed:
# AITEST_INTEGRATION_JUDGE_MODEL=copilot/gpt-5-mini pytest ...
```

```python
async def test_my_optimizer(optimize_instruction, integration_judge_model):
    result = await optimize_instruction(
        instruction="...",
        test_cases=[...],
        judge_model=integration_judge_model,  # discovered at runtime
    )
    assert result.improved_instruction
```

Provider probe order (first reachable wins):
1. `AITEST_INTEGRATION_JUDGE_MODEL` env var override
2. Azure (`AZURE_API_BASE` or `AZURE_OPENAI_ENDPOINT` + auth)
3. OpenAI (`OPENAI_API_KEY`)
4. Copilot (`gh auth login` or `GITHUB_TOKEN`)

The test **fails** (not skips) if none are available:

```
FAILED - No LLM provider available. Set AITEST_INTEGRATION_JUDGE_MODEL or configure Azure/OpenAI/Copilot credentials.
```

Force a specific provider:

```bash
AITEST_INTEGRATION_JUDGE_MODEL=copilot/gpt-5-mini pytest tests/integration/copilot/test_optimizer_integration.py -v
```
