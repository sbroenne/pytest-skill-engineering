# Examples

The best live examples are the real Copilot integration tests in `tests/integration/copilot/`.

## Highlights

- `test_01_basic.py` — basic file creation and editing
- `test_02_models.py` — model comparison
- `test_03_instructions.py` — system prompt comparison
- `test_05_skills.py` — skill comparison
- `test_09_cli.py` — CLI workflows
- `test_12_custom_agents.py` — custom agent dispatch

## Run one

```bash
gh auth login
uv run python -m pytest tests/integration/copilot/test_01_basic.py -v
```

## MCP example shape

```python
import sys

from pytest_skill_engineering.copilot import CopilotEval


agent = CopilotEval(
    name="banking-default",
    model="gpt-5.4-mini",
    instructions="Use the banking tools before answering.",
    mcp_servers={
        "banking": {
            "command": sys.executable,
            "args": ["-m", "pytest_skill_engineering.testing.banking_mcp"],
            "tools": ["*"],
        }
    },
)
```
