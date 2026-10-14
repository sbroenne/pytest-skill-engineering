---
description: "Load instruction-file content as a system prompt and check the generated output."
---

# Custom Instructions

Load an instruction file when you want to test a project's conventions with
Copilot. Pass its content to `CopilotEval.instructions`, then assert on the
output those conventions require.

This tests explicitly supplied instructions. It does **not** reproduce an
editor's automatic file matching or prove that ambient instructions were loaded.
SDK configuration discovery is disabled by default.

## Loading a Single Instruction File

For example, create `.github/instructions/python-style.instructions.md`:

```markdown
---
applyTo: "**/*.py"
description: Python function conventions
---

Use snake_case function names.
Annotate every function parameter and return value.
Give every public function a docstring.
```

Load and check it in a test:

```python
from __future__ import annotations

import ast
import re

from pytest_skill_engineering import load_instruction_file
from pytest_skill_engineering.copilot import CopilotEval


async def test_function_conventions(copilot_eval, tmp_path):
    instruction = load_instruction_file(".github/instructions/python-style.instructions.md")
    agent = CopilotEval(
        name="python-style",
        model="gpt-5.6-sol",
        instructions=instruction["content"],
        working_directory=str(tmp_path),
    )
    result = await copilot_eval(
        agent, "Create arithmetic.py with a public function that adds two numbers."
    )

    assert result.success, result.error
    tree = ast.parse((tmp_path / "arithmetic.py").read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    assert functions
    for function in functions:
        assert re.fullmatch(r"_?[a-z][a-z0-9]*(?:_[a-z0-9]+)*", function.name)
        assert ast.get_docstring(function)
        parameters = function.args.posonlyargs + function.args.args + function.args.kwonlyargs
        if function.args.vararg is not None:
            parameters.append(function.args.vararg)
        if function.args.kwarg is not None:
            parameters.append(function.args.kwarg)
        assert all(parameter.annotation is not None for parameter in parameters)
        assert function.returns is not None
```

These checks inspect syntax, annotations, docstrings, and the shown snake_case
rule. They do not establish that addition works. Add your project's independent
behavior tests for a complete check.
Run generated code only in an environment approved for untrusted code.

`load_instruction_file()` returns:

| Key | Value |
|---|---|
| `name` | Filename-derived name, with the instruction suffix removed |
| `content` | Markdown body, with frontmatter removed |
| `apply_to` | Frontmatter `applyTo`, or `""` |
| `description` | Frontmatter description, or `""` |
| `metadata` | Full parsed frontmatter mapping |
| `path` | Supplied source path as a string |

## Instruction File Formats

The same loader accepts `.instructions.md`, `.github/copilot-instructions.md`,
`AGENTS.md`, and `CLAUDE.md`. Plain Markdown needs no frontmatter.

### `.instructions.md` (VS Code)

`applyTo` describes editor file matching. The loader returns it as `apply_to`;
passing `content` to an eval does not apply that glob or save the file metadata
automatically.

### `.github/copilot-instructions.md` (VS Code, project-wide)

Use this file for repository-wide conventions. To load it with project custom
agent definitions, use `CopilotEval.from_copilot_config(project_root)`.

### `AGENTS.md` / `CLAUDE.md` (plain markdown)

You can explicitly load either file and use its body as instructions. Doing so
does not switch the execution to another coding-agent product.

## Testing loaded instructions

There is no `CopilotEval.from_instruction_files()` factory. Load the files
explicitly or use the appropriate project loader.

### Combining Multiple Instruction Files

This configuration fragment concatenates files in the chosen order:

```python
from pytest_skill_engineering import load_instruction_file
from pytest_skill_engineering.copilot import CopilotEval

paths = [
    ".github/copilot-instructions.md",
    ".github/instructions/python-style.instructions.md",
]
instructions = [load_instruction_file(path) for path in paths]
agent = CopilotEval(
    name="combined-conventions",
    instructions="\n\n".join(item["content"] for item in instructions),
)
```

All concatenated instructions apply to this session, regardless of their
`applyTo` values. Resolve conflicting rules deliberately.

## Loading All Instruction Files from a Directory

`load_instruction_files()` loads immediate `*.instructions.md` files and
well-known instruction filenames. Filter by filename-derived name:

```python
from pytest_skill_engineering import load_instruction_files

instructions = load_instruction_files(
    ".github/instructions",
    include={"python-style", "testing-conventions"},
    exclude={"experimental"},
)
```

Use pytest parametrization when each file should have its own task and outcome.
Do not apply unrelated files to one generic task and call session completion
evidence of adherence.

## Instruction file evidence

Name evals and pytest parameters after their variants. JSON captures the
configured system prompt, not automatically the source filenames or per-file
results. Record safe filenames with `record_property` if you need them.

See [System prompts](system-prompts.md), [Prompt files](prompt-files.md), and
[Custom agents](custom-agents.md) for the corresponding configuration boundaries.
