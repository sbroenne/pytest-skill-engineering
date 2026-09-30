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
    uv sync --frozen --all-extras
    uv run pre-commit install
    ```

2. Verify the deterministic development environment:
    ```bash
    uv run pytest-skill-engineering --version
    uv run python -m pytest tests/contracts/ -q -o addopts=
    ```

3. Use the validation path for your change:

    | Change | Validate with |
    |---|---|
    | Python source | Ruff, formatting, Pyright, contracts, then the relevant Copilot integration file |
    | Copilot behavior | One relevant `tests/integration/copilot/` file at a time |
    | Documentation | Strict MkDocs build |
    | Evidence persistence | Native JSON round-trip and failure-path contracts |

All PRs are **squash merged**. The
[full contribution guide](https://github.com/sbroenne/pytest-skill-engineering/blob/main/CONTRIBUTING.md)
contains the exact commands and explains when a paid real-Copilot run is
required.

## Guides

- **[Architecture](architecture.md)** — How the engine executes tests and dispatches tools
- **[Evidence Structure](evidence-structure.md)** — Captured data, serialization, and persistence checks
