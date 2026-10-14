---
description: "Validate your own skills, load them into Copilot, and check task output."
---

# Skills

Supply `skill_directories` when a task should use your domain skill. Copilot
loads the skill natively; pytest checks the output you require. Loading a skill
does not prove that Copilot read or followed it.

The framework does not distribute a companion skill for its own use. This
page covers consumer-provided skills following the
[Agent Skills specification](https://agentskills.io/specification).

## Creating a Skill

A skill directory contains `SKILL.md` and optional reference documents:

```text
skills/
└── invoice-format/
    ├── SKILL.md
    └── references/
        └── fields.md
```

### SKILL.md Format

```markdown
---
name: invoice-format
description: Save invoices in the project's JSON format.
---

When creating an invoice, read references/fields.md for the required fields.
Write JSON only to the requested artifact path.
```

Put the task-routing guidance and core rules in `SKILL.md`. Put detailed
schemas, tables, or examples in references linked from it.

## Skill References

Copilot can read `references/` files using its file tools. Supplied personas
also expose `list_skill_references` and `read_skill_reference` for validated,
enabled references. `client_mode="empty"` does not inject persona tools.
Neither mechanism guarantees that the model will consult a reference.

### Example Reference Document

```markdown
# Invoice fields

Use exactly these fields:
- quantity: the requested integer quantity
- unit_price: the requested numeric price
- total: quantity multiplied by unit_price
```

### How the Eval Uses References

The runner validates references before execution. The model can then choose
to read them and use their content. Inspect observed reads if they matter to
your requirement, but verify the saved artifact independently.

Reference files may live in subdirectories, such as
`references/commands/read.md`. Link from `SKILL.md` using paths relative to
the skill root. `Skill.references` and the reference tools use paths relative
to `references/`, with `/` separators on every platform.

Validation recursively checks nonempty UTF-8 Markdown. Equal basenames in
different folders are distinct, but duplicate relative reference paths across
enabled skills are rejected. Disabled skills are not advertised or readable
through reference tools; that does not prevent access through other filesystem
tools.

Links must resolve within `references/`, and that directory must resolve within
the skill directory. Broken links, directory cycles, unreadable entries, and
non-file entries are explicit errors. Checks also apply to Windows junctions.

### When to Use References vs Instructions

Use `SKILL.md` for when and how to apply the skill. Use references for details
that can be read on demand. Use `CopilotEval.instructions` for session-wide
behavior rather than copying the entire skill into the system prompt.

The frontmatter name must match its directory name. Names use lowercase
letters, digits, and single hyphens; descriptions and Markdown bodies must be
nonempty. Local validation also supports optional `scripts/` and `assets/`
directories, but loading them is not proof that the model executed a script
or used an asset.

## Using a Skill

```python
from pytest_skill_engineering.copilot import CopilotEval

agent = CopilotEval(
    name="invoice-format",
    model="gpt-5.6-sol",
    skill_directories=["skills/invoice-format"],
)
```

Each path can identify an individual skill directory or a parent containing
immediate skill directories. Relative paths resolve from the Python process's
current directory, **not** from `working_directory`.

Explicit directories enable native SDK skill loading, including in
`client_mode="empty"`. They do not enable ambient configuration discovery.
Empty mode still excludes personal/project configuration, custom instructions,
file hooks, managed settings, and persona injection. Supply task tools
explicitly; its default available-tool list is empty.

Before sending the prompt, the runner validates the requested skills, then
checks SDK availability through `session.rpc.skills.ensure_loaded()`,
`reload()`, and `list()`. Missing, unreadable, invalid, duplicate-name, or
undiscovered skills yield `success=False`, `stop_reason="execution_error"`,
and a setup error without sending a model message.

A parent with no immediate `SKILL.md` packages is an error. Unrelated child
directories without `SKILL.md` are ignored. Loading warnings are logged and
saved; loading errors stop execution. There is one execution attempt.

`extra_config={"enable_skills": False}` conflicts with explicit nonempty
directories and raises `ValueError` from `build_session_config()`. Remove the
directories for a no-skill baseline. Use `disabled_skills=["skill-name"]` to
disable particular discovered skills; they remain in discovery evidence with
`enabled=False`. Passthrough directories follow the same checks and cannot
replace a nonempty `skill_directories` field.

### Preflight Without Model Execution

Validate an individual skill locally:

```python
from pytest_skill_engineering import load_skill

skill = load_skill("skills/invoice-format")
assert skill.name == "invoice-format"
print(sorted(skill.references))
```

`load_skill()` and `Skill.from_path()` perform local format, reference, and
readability checks. They start no SDK client and send no model message. Invalid
input raises `SkillError`. For a collection, validate each immediate child
containing `SKILL.md`; a collection path is not itself a valid individual skill.

Local validation does not establish runtime availability or detect duplicate
names across several requested directories. If you perform a separate SDK
discovery probe, use `build_session_config()` and the public skills RPCs without
calling `send()` or `send_and_wait()`. Discovery alone does not replace local
validation.

## Testing Skill Effectiveness

With the sample skill above, check the saved invoice:

```python
import json


async def test_invoice_skill(copilot_eval, tmp_path):
    agent = CopilotEval(
        name="invoice-format",
        model="gpt-5.6-sol",
        skill_directories=["skills/invoice-format"],
        working_directory=str(tmp_path),
    )
    result = await copilot_eval(
        agent,
        "Use invoice-format to save invoice.json for 3 items priced at 12.50 each.",
    )

    assert result.success, result.error
    assert json.loads((tmp_path / "invoice.json").read_text(encoding="utf-8")) == {
        "quantity": 3,
        "unit_price": 12.5,
        "total": 37.5,
    }
```

This checks the artifact contract for one task. To investigate the skill's
effect, compare a no-skill configuration with the same model, instructions,
tools, task, initial state, and checks. See [Comparing configurations](comparing.md).
Do not require a baseline to fail just to make a skill appear useful.

## Copilot Skills

`result.skill_discovery` records SDK metadata and loading diagnostics. It is
not a claim that the model used the skill. Observed reads remain tool-call
evidence; exact output checks remain your test's responsibility.

`Skill.from_path()` is a metadata loader, not a `CopilotEval` constructor
argument. Attach any required MCP servers through `mcp_servers`.

## Next Steps

- [Test skills and custom agents](../how-to/test-coding-agents.md#testing-skills).
- [Multi-step tasks and explicit context](sessions.md).
- [Configuration reference](../reference/configuration.md) for discovery opt-in.
