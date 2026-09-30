# Examples

Start with the standalone [quickstart project](quickstart/). It runs one real
Copilot eval against the bundled Todo MCP server. pytest shows the result and
JSON captures execution for your coding agent to inspect.

The [customer workflow project](skill-dogfood/) demonstrates the next step:
have a coding agent write a test, observe a real failure, interpret the native
evidence, repair an invoice CLI, and rerun unchanged checks. It also preserves
our historical companion-skill comparison through a frozen test fixture.
The companion skill was removed from the product. Defaults are offline;
live execution is explicit.
Its harder checkout workflow adds durable state, duplicate/conflicting requests,
and 42 fixed checks. The [use case](../docs/use-cases/companion-skill.md) records
the comparison design, actual results, and decision not to ship the skill.

The repository's own integration tests demonstrate advanced scenarios:

- `test_02_models.py` — model comparison
- `test_03_instructions.py` — system prompt comparison
- `test_05_skills.py` — skill comparison
- `test_09_cli.py` — CLI workflows
- `test_12_custom_agents.py` — custom agent dispatch

Those tests validate pytest-skill-engineering itself. New users should run the
quickstart first rather than treating the repository test suite as a template.
