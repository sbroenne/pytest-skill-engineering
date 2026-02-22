# Contributing to pytest-skill-engineering

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/sbroenne/pytest-skill-engineering.git
   cd pytest-skill-engineering
   ```

2. Install in editable mode with dev dependencies:
   ```bash
   uv sync --all-extras
   ```

   This installs the package from your local source code. Any changes you make to `src/pytest_skill_engineering/` are immediately available — no reinstall needed.

3. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

### Editable Install Explained

Python has two install modes:

| Mode | Command | Use case |
|------|---------|----------|
| **Regular** | `uv add pytest-skill-engineering` | End users, pulls from PyPI |
| **Editable** | `uv sync` (in project dir) | Developers, uses local source |

With editable mode, Python points to your source folder instead of copying files. Edit code → run tests → see changes instantly.

### Using in Other Projects

To test your local changes in another project while developing:

```bash
# In your other project directory
cd d:\source\my-mcp-server

# Add pytest-skill-engineering as an editable dependency
uv add --editable d:\source\pytest-skill-engineering
```

This adds a local reference to your `pyproject.toml`:
```toml
dependencies = [
    "pytest-skill-engineering @ file:///d:/source/pytest-skill-engineering",
]
```

Now your other project uses your local source. Changes to pytest-skill-engineering are immediately available — no reinstall needed.

## Code Quality

This project uses automated tools to maintain code quality:

- **[Ruff](https://docs.astral.sh/ruff/)** — Linting and formatting
- **[Pyright](https://github.com/microsoft/pyright)** — Type checking
- **[pre-commit](https://pre-commit.com/)** — Git hooks for automated checks
- **[CodeQL](https://codeql.github.com/)** — Security scanning on GitHub

### Running Checks Manually

```bash
# Run all pre-commit hooks (same checks as git commit)
pre-commit run --all-files

# Or run individual tools
ruff check .                 # Lint
ruff format .                # Format
pyright src                  # Type Check
```

### Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`. If a hook fails, fix the issues and commit again.

The hooks will:
1. **Lint** (ruff) — Auto-fix linting issues where possible
2. **Format** (ruff) — Auto-format code
3. **Type Check** (pyright) — Validate type hints

## Running Tests

```bash
# Run unit tests (fast, no LLM calls)
pytest tests/unit/ -v

# Run integration tests (requires LLM credentials)
pytest tests/integration/ -v

# Run all tests
pytest -v
```

For architecture details, report structure, and developer guides, see the **[Contributing docs](https://sbroenne.github.io/pytest-skill-engineering/contributing/)**.

### Integration Tests

Integration tests require LLM provider credentials. Set up at least one:

```bash
# Azure OpenAI (uses Entra ID - no API key needed)
export AZURE_API_BASE=https://your-resource.cognitiveservices.azure.com
az login

# Google Vertex AI
export GOOGLE_CLOUD_PROJECT=your-project-id
gcloud auth application-default login
```

## Project Structure

```
pytest-skill-engineering/
├── src/pytest_skill_engineering/
│   ├── __init__.py      # Package exports
│   ├── cli.py           # CLI for report regeneration
│   ├── plugin.py        # pytest plugin hooks
│   ├── core/            # Core types (Agent, Provider, Result, Skill)
│   ├── execution/       # Engine, server management, skill tools
│   ├── fixtures/        # pytest fixtures (aitest_run, factories)
│   ├── reporting/       # Collector, aggregator, insights, generator
│   └── templates/       # Jinja2 + Tailwind HTML report templates
├── tests/
│   ├── unit/            # Pure logic tests (no LLM calls)
│   ├── integration/     # Integration tests (real LLM calls)
│   └── showcase/        # Hero report generation
├── docs/                # MkDocs documentation
├── pyproject.toml       # Project configuration
└── .pre-commit-config.yaml
```

## Making Changes

1. Create a branch for your changes
2. Make your changes
3. Ensure all checks pass: `pre-commit run --all-files`
4. Run tests: `pytest tests/unit/ -v`
5. Submit a pull request

All PRs are **squash merged** to keep a clean commit history on main.

## Code Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) (enforced by Ruff)
- Use type hints for all public APIs
- Keep functions focused and small
- Write docstrings for public classes and methods

## Releasing

Releases are triggered via GitHub Actions workflow dispatch:

1. Go to [Actions → Release](https://github.com/sbroenne/pytest-skill-engineering/actions/workflows/release.yml)
2. Click "Run workflow"
3. Select the version bump type:
   - **patch** (default) — Bug fixes, backwards-compatible (e.g., 0.2.0 → 0.2.1)
   - **minor** — New features, backwards-compatible (e.g., 0.2.0 → 0.3.0)
   - **major** — Breaking changes (e.g., 0.2.0 → 1.0.0)
4. Or specify a custom version (e.g., `1.2.3`) to override automatic versioning

The workflow will:
1. Calculate the new version from the latest git tag
2. Update `pyproject.toml` with the new version
3. Build the package
4. Test the build
5. Create and push a git tag (e.g., `v0.2.1`)
6. Publish to PyPI
7. Create a GitHub release
8. Deploy updated documentation

**Note**: The version in `pyproject.toml` is automatically updated during the release workflow. You do not need to manually update it before releasing.
