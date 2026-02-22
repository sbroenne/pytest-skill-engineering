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
    pre-commit install
    ```

2. Run checks:
    ```bash
    pre-commit run --all-files    # Lint, format, type check, docs build
    pytest tests/unit/ -v         # Unit tests (fast, no LLM)
    pytest tests/integration/ -v  # Integration tests (requires LLM credentials)
    ```

All PRs are **squash merged**. See [CONTRIBUTING.md](https://github.com/sbroenne/pytest-skill-engineering/blob/main/CONTRIBUTING.md) for the full guide.

## Guides

- **[Architecture](architecture.md)** — How the engine executes tests and dispatches tools
- **[Report Structure](report-structure.md)** — Visual components, layout behavior, and design spec
