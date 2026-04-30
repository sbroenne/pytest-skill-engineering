# Migration Guide: pytest-aitest → pytest-skill-engineering

This guide covers migrating from `pytest-aitest` to `pytest-skill-engineering`.

---

## 1. Package rename

### Install

```bash
# Remove old package
pip uninstall pytest-aitest

# Install new package
uv add pytest-skill-engineering
```

### Import path

```python
# Old
from pytest_aitest import Agent, AgentResult, ...

# New
from pytest_skill_engineering.copilot import CopilotEval
from pytest_skill_engineering import EvalResult, ...
```

---

## 2. Class renames

| pytest-aitest | pytest-skill-engineering |
|---------------|--------------------------|
| `Agent` | `CopilotEval` |
| `AgentResult` | `EvalResult` |
| `CopilotAgent` | `CopilotEval` |
| `aitest_run` fixture | `copilot_eval` fixture |
| `copilot_run` fixture | `copilot_eval` fixture |

All other types (`EvalResult`, `Skill`, `Wait`, etc.) are unchanged.

---

## 3. `system_prompt=` migration

Use `CopilotEval` instead of the raw `system_prompt=` constructor argument.

### Before

```python
from pytest_aitest import Agent, Provider

agent = Agent(
    provider=Provider(model="azure/gpt-5.4-mini"),
    system_prompt="You are a banking assistant. Use tools to manage accounts.",
    system_prompt_name="banking-v1",
)
```

### After

```python
from pytest_skill_engineering.copilot import CopilotEval

agent = CopilotEval(
    name="banking-v1",
    instructions="You are a banking assistant. Use tools to manage accounts.",
)
```

### Without a label

If the original code had no `system_prompt_name`, use the test name or `"default"`:

```python
# Old
agent = Eval(
    provider=Provider(model="azure/gpt-5.4-mini"),
    system_prompt="You are a helpful assistant.",
)

# New
agent = CopilotEval(
    name="default",
    instructions="You are a helpful assistant.",
)
```

### With extra options

Other keyword arguments (`skill_directories`, `custom_agents`, `excluded_tools`, etc.) are passed through:

```python
agent = CopilotEval(
    name="banking-v1",
    instructions="You are a banking assistant.",
    model="gpt-5.4-mini",
)
```

---

## 4. `load_system_prompts()` → `load_custom_agents()` migration

`load_system_prompts()` returned a `dict[str, str]` mapping prompt name → prompt text.
`load_custom_agents()` returns a `list[dict]` where each dict has `name`, `prompt`, and `description` keys.

Prompt files must be named `*.agent.md` (instead of `*.md`) for `load_custom_agents()` to find them.

### Before

```python
from pytest_aitest import Agent, Provider, load_system_prompts

PROMPTS_DIR = Path("prompts/")
PROMPTS = load_system_prompts(PROMPTS_DIR)
# PROMPTS = {"concise": "Be brief...", "detailed": "Explain everything..."}

AGENTS = [
    Agent(
        provider=Provider(model="azure/gpt-5.4-mini"),
        system_prompt=prompt_text,
        system_prompt_name=prompt_name,
    )
    for prompt_name, prompt_text in PROMPTS.items()
]
```

### After

Rename your prompt files from `*.md` to `*.agent.md`, then:

```python
from pytest_skill_engineering.copilot import CopilotEval
from pytest_skill_engineering import load_custom_agents

PROMPTS_DIR = Path("prompts/")
AGENTS_DATA = load_custom_agents(PROMPTS_DIR)
# AGENTS_DATA = [
#   {"name": "concise", "prompt": "Be brief...", "description": "", "metadata": {}},
#   {"name": "detailed", "prompt": "Explain everything...", "description": "", "metadata": {}},
# ]

AGENTS = [
    CopilotEval(
        name=agent_data["name"],
        instructions=agent_data["prompt"],
    )
    for agent_data in AGENTS_DATA
]
```

### Parametrized tests

```python
# Old
@pytest.mark.parametrize("prompt_name,system_prompt", PROMPTS.items())
async def test_with_prompt(eval_run, prompt_name, system_prompt):
    agent = Agent(system_prompt=system_prompt, system_prompt_name=prompt_name, ...)

# New
@pytest.mark.parametrize("agent_data", AGENTS_DATA, ids=lambda d: d["name"])
async def test_with_prompt(copilot_eval, agent_data):
    agent = CopilotEval(name=agent_data["name"], instructions=agent_data["prompt"])
```

---

## 5. Fixture renames

```python
# Old conftest.py / test file
async def test_banking(aitest_run):
    result = await aitest_run(agent, "What's my balance?")

# New
async def test_banking(copilot_eval):
    result = await copilot_eval(agent, "What's my balance?")
```

```python
# Old (Copilot)
async def test_copilot(copilot_run):
    result = await copilot_run(copilot_agent, "Write math.py")

# New
async def test_copilot(copilot_eval):
    result = await copilot_eval(copilot_eval_agent, "Write math.py")
```
