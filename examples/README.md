# Examples

Start with the standalone [quickstart project](quickstart/). It runs one real
Copilot eval against the bundled Todo MCP server and produces a report you can
inspect before adapting the test to your own tools.

The repository's own integration tests demonstrate advanced scenarios:

- `test_02_models.py` — model comparison
- `test_03_instructions.py` — system prompt comparison
- `test_05_skills.py` — skill comparison
- `test_09_cli.py` — CLI workflows
- `test_12_custom_agents.py` — custom agent dispatch

Those tests validate pytest-skill-engineering itself. New users should run the
quickstart first rather than treating the repository test suite as a template.
