# Quickstart example

This standalone project runs one real GitHub Copilot session against the bundled
Todo MCP server. It verifies exact task arguments and returned task state, then
shows ordinary pytest results and saves JSON execution evidence.

## Run it

```bash
gh auth login --hostname github.com
uv sync
uv run python -m pytest tests/test_copilot_eval.py -v
```

The run uses `gpt-5.6-sol`, requires a GitHub Copilot subscription, and may
consume premium requests. `pricing.toml` provides explicit rates for cost
estimates; adjust them if your billing basis differs. A successful run creates:

- `aitest-reports/results.json` — the raw execution evidence

Ask your coding agent to inspect `aitest-reports/results.json`, then replace the bundled Todo MCP
configuration and prompt with your own server and user task.

To create the same starter in an existing Python project:

```bash
uv add pytest-skill-engineering
uv run pytest-skill-engineering init
uv run pytest-skill-engineering doctor
```

The example requires framework 1.x. Before 1.0 is published, run it from a
checked-out framework environment or install the checkout explicitly; do not
expect the public package registry to contain an unpublished release.
