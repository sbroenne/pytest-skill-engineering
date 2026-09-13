---
description: "Test custom instruction files — verify that .github/copilot-instructions.md, *.instructions.md, AGENTS.md, and CLAUDE.md produce the right LLM behavior."
---

# Custom Instructions

**Custom instruction files** define HOW the AI should behave — coding conventions, naming rules, architecture patterns. They are always-on context injected into every interaction. pytest-skill-engineering lets you test whether the LLM actually follows these conventions.

| File | Where | Purpose |
|------|-------|---------|
| `.github/copilot-instructions.md` | Repo root | Project-wide coding standards (VS Code Copilot) |
| `*.instructions.md` | Anywhere | File-scoped rules with optional `applyTo` glob |
| `AGENTS.md` | Repo root | Workspace instructions used by some coding-agent tools |
| `CLAUDE.md` | Repo root | Claude Code workspace instructions |

These are distinct from Custom Agents (`.agent.md` specialist personas) and Prompt Files (slash commands). Custom instructions define conventions; prompt files are user inputs.

## Loading a Single Instruction File

Use `load_instruction_file()` to load a single file:

```python
from pytest_skill_engineering.copilot import CopilotEval
from pytest_skill_engineering import load_instruction_file


async def test_follows_naming_conventions(copilot_eval):
    """Agent follows snake_case naming conventions from coding-standards.instructions.md."""
    instr = load_instruction_file(".github/copilot-instructions.md")
    agent = CopilotEval(
        name="standards-test",
        instructions=instr["content"],
    )
    result = await copilot_eval(agent, "Write a function that adds two numbers")
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

## Testing loaded instructions

Load the file and pass its content as the system prompt. `CopilotEval` does not
have a `from_instruction_files()` factory:

```python
from pytest_skill_engineering import load_instruction_file
from pytest_skill_engineering.copilot import CopilotEval

instruction = load_instruction_file(".github/copilot-instructions.md")
agent = CopilotEval(
    name="conventions-test",
    instructions=instruction["content"],
)


async def test_naming_conventions(copilot_eval):
    """Agent follows project naming conventions."""
    result = await copilot_eval(agent, "Write a Python function to compute factorial")
    assert result.success
    assert "def " in result.final_response
```

### Combining Multiple Instruction Files

```python
paths = [
    ".github/copilot-instructions.md",
    ".github/instructions/python-style.instructions.md",
    ".github/instructions/testing-conventions.instructions.md",
]
instructions = [load_instruction_file(path) for path in paths]
agent = CopilotEval(
    name="full-conventions",
    instructions="\n\n".join(item["content"] for item in instructions),
)
```

The files are concatenated in order, separated by a blank line.

## Loading All Instruction Files from a Directory

Use `load_instruction_files()` to load all `*.instructions.md` files and
well-known files (`copilot-instructions.md`, `AGENTS.md`, `CLAUDE.md`):

```python
import pytest
from pytest_skill_engineering.copilot import CopilotEval
from pytest_skill_engineering import load_instruction_files

INSTRUCTIONS = load_instruction_files(".github/instructions/")


@pytest.mark.parametrize("instr", INSTRUCTIONS, ids=lambda i: i["name"])
async def test_instruction_file(copilot_eval, instr):
    """Each instruction file produces adherent LLM behavior."""
    agent = CopilotEval(
        name=f"test-{instr['name']}",
        instructions=instr["content"],
    )
    result = await copilot_eval(agent, "Write a Python class for a bank account")
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

Use descriptive eval names and pytest parameter IDs to identify instruction
variants. The combined system prompt is included in the eval configuration for
analysis, but passing file content through `instructions` does not automatically
preserve file names or create per-file pass rates. Assert the required behavior
in each test.

## Next Steps

- [Prompt Files](prompt-files.md) — Test user-facing slash commands
- [Custom Agents](custom-agents.md) — Test `.agent.md` specialist agent files
- [CopilotResult Reference](../reference/result.md) — All result fields
