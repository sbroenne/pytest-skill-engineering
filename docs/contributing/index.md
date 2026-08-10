---
description: "Contribute to pytest-skill-engineering: development setup, coding standards, and project architecture."
---

# Contributing

Resources for contributors and developers working on pytest-skill-engineering itself.

## Development Setup

1. Clone and install:
    ```bash
    git clone https://github.com/sbroenne/pytest-skill-engineering.git
    cd pytest-skill-engineering
    uv sync --all-extras
    uv run pre-commit install
    ```

2. Run checks:
    ```bash
    uv run pre-commit run --all-files               # Lint, format, type check, docs build
    uv run python -m pytest tests/unit/test_reporting.py tests/unit/test_html_reports.py tests/unit/test_cli.py -v
    uv run python -m pytest tests/integration/copilot/ -v  # Real Copilot behavior checks
    ```

All PRs are **squash merged**. See [CONTRIBUTING.md](https://github.com/sbroenne/pytest-skill-engineering/blob/main/CONTRIBUTING.md) for the full guide.

## Guides

- **[Architecture](architecture.md)** — How the engine executes tests and dispatches tools
- **[Report Structure](report-structure.md)** — Visual components, layout behavior, and design spec
