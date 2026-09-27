# Quickstart example

This standalone project runs one real GitHub Copilot session against the bundled
Todo MCP server. It verifies that Copilot selects `todo-add_task` and produces HTML
and JSON reports.

## Run it

```bash
gh auth login --hostname github.com
uv sync
uv run python -m pytest tests/test_copilot_eval.py -v
```

The run uses `gpt-5.6-sol`, requires a GitHub Copilot subscription, and may
consume premium requests. `pricing.toml` provides explicit rates for cost
estimates; adjust them if your billing basis differs. A successful run creates:

- `aitest-reports/report.html` — the rendered report with AI analysis
- `aitest-reports/results.json` — the raw execution evidence

Open `aitest-reports/report.html`, then replace the bundled Todo MCP
configuration and prompt with your own server and user task.

To create the same starter in an existing Python project:

```bash
uv add pytest-skill-engineering
uv run pytest-skill-engineering init
uv run pytest-skill-engineering doctor
```
