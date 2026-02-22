---
description: "Test custom instruction files — verify that .github/copilot-instructions.md, *.instructions.md, AGENTS.md, and CLAUDE.md produce the right LLM behavior."
---

# Custom Instructions

**Custom instruction files** define HOW the AI should behave — coding conventions, naming rules, architecture patterns. They are always-on context injected into every interaction. pytest-skill-engineering lets you test whether the LLM actually follows these conventions.

| File | Where | Purpose |
|------|-------|---------|
| `.github/copilot-instructions.md` | Repo root | Project-wide coding standards (VS Code Copilot) |
| `*.instructions.md` | Anywhere | File-scoped rules with optional `applyTo` glob |
| `AGENTS.md` | Repo root | Workspace instructions (OpenAI Codex / multi-agent) |
| `CLAUDE.md` | Repo root | Claude Code workspace instructions |

These are distinct from Custom Agents (`.agent.md` specialist personas) and Prompt Files (slash commands). Custom instructions define conventions; prompt files are user inputs.

## Loading a Single Instruction File

Use `load_instruction_file()` to load a single file:

```python
from pytest_skill_engineering import Eval, Provider, MCPServer, load_instruction_file

code_server = MCPServer(command=["python", "code_server.py"])

async def test_follows_naming_conventions(eval_run):
    """Agent follows snake_case naming conventions from coding-standards.instructions.md."""
    instr = load_instruction_file(".github/copilot-instructions.md")
    agent = Eval(
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[code_server],
        system_prompt=instr["content"],
    )
    result = await eval_run(agent, "Write a function that adds two numbers")
    assert result.success
    assert "add_numbers" in result.final_response  # snake_case enforced
```

`load_instruction_file()` returns a dict with:

| Key | Description |
|-----|-------------|
| `name` | Derived from filename (e.g. `copilot-instructions`, `coding-standards`) |
| `content` | The instruction text (frontmatter stripped) |
| `apply_to` | From frontmatter `applyTo:` field, or empty string |
| `description` | From frontmatter `description:` field, or empty string |
| `metadata` | All other frontmatter fields |
| `path` | Absolute path to the file (as string) |

## Instruction File Formats

### `.instructions.md` (VS Code)

```markdown title=".github/instructions/coding-standards.instructions.md"
---
applyTo: "**/*.py"
description: Python coding standards
---

Use snake_case for all variable and function names.
Never use abbreviations — prefer `calculate_total` over `calc_tot`.
All functions must have type annotations.
```

The `applyTo` glob tells VS Code which files trigger this instruction.
pytest-skill-engineering stores it in `apply_to` for reporting.

### `.github/copilot-instructions.md` (VS Code, project-wide)

```markdown title=".github/copilot-instructions.md"
# Project Coding Standards

All code must follow these conventions:
- Use snake_case for Python identifiers
- Write docstrings for all public functions
- Prefer explicit over implicit
```

No frontmatter required — just plain markdown.

### `AGENTS.md` / `CLAUDE.md` (plain markdown)

```markdown title="AGENTS.md"
You are working in a Python monorepo. Always:
1. Run tests before committing
2. Check for type errors with mypy
3. Follow the project's naming conventions in docs/conventions.md
```

## Testing with `Eval.from_instruction_files()`

The `from_instruction_files()` factory loads one or more instruction files and
combines their content into the system prompt:

```python
import pytest
from pytest_skill_engineering import Eval, Provider, MCPServer

code_server = MCPServer(command=["python", "code_server.py"])

agent = Eval.from_instruction_files(
    [".github/copilot-instructions.md"],
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[code_server],
)

async def test_naming_conventions(eval_run):
    """Agent follows project naming conventions."""
    result = await eval_run(agent, "Write a Python function to compute factorial")
    assert result.success
    assert "def " in result.final_response
```

### Combining Multiple Instruction Files

```python
agent = Eval.from_instruction_files(
    [
        ".github/copilot-instructions.md",
        ".github/instructions/python-style.instructions.md",
        ".github/instructions/testing-conventions.instructions.md",
    ],
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[code_server],
    name="full-conventions",  # optional — auto-derived from file names
)
```

The files are concatenated in order, separated by a blank line.

## Loading All Instruction Files from a Directory

Use `load_instruction_files()` to load all `*.instructions.md` files and
well-known files (`copilot-instructions.md`, `AGENTS.md`, `CLAUDE.md`):

```python
import pytest
from pytest_skill_engineering import Eval, Provider, load_instruction_files

INSTRUCTIONS = load_instruction_files(".github/instructions/")

@pytest.mark.parametrize("instr", INSTRUCTIONS, ids=lambda i: i["name"])
async def test_instruction_file(eval_run, instr):
    """Each instruction file produces adherent LLM behavior."""
    agent = Eval(
        provider=Provider(model="azure/gpt-5-mini"),
        system_prompt=instr["content"],
    )
    result = await eval_run(agent, "Write a Python class for a bank account")
    assert result.success
```

`load_instruction_files()` accepts `include` and `exclude` sets to filter by name:

```python
# Only load specific files
INSTRUCTIONS = load_instruction_files(
    ".github/instructions/",
    include={"coding-standards", "testing-conventions"},
)

# Skip certain files
INSTRUCTIONS = load_instruction_files(
    ".github/instructions/",
    exclude={"experimental"},
)
```

## Instruction File Info in Reports

When you use `Eval.from_instruction_files()`, the report tracks which instruction
files were used and their pass rates in the **Custom Instruction Files** section
of the AI analysis. The AI will assess whether the LLM followed each convention,
cite specific tests where rules were violated, and suggest changes to improve
adherence.

## Next Steps

- [Prompt Files](prompt-files.md) — Test user-facing slash commands
- [Custom Agents](custom-agents.md) — Test `.agent.md` specialist agent files
- [EvalResult Reference](../reference/result.md) — All result fields
