# Project Context

- **Owner:** sbroenne
- **Project:** pytest-skill-engineering — pytest plugin for testing MCP servers and CLIs with real LLMs. AI analyzes results and tells you what to fix.
- **Stack:** Python 3.11+, PydanticAI, pydantic-evals, MCP, pytest, htpy, async/await, uv, hatch, ruff, pyright
- **Created:** 2026-03-21

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-03-21 — Full dependency upgrade via `uv lock --upgrade`

Key version bumps:
- **pydantic-ai** 1.61.0 → 1.70.0 (minor, no breaking changes detected)
- **pydantic-evals** 1.61.0 → 1.70.0
- **openai** 2.21.0 → 2.29.0
- **litellm** 1.81.13 → 1.82.5
- **github-copilot-sdk** 0.1.25 → 0.2.0 (minor→major-ish, new typer/shellingham deps added)
- **mkdocs-material** 9.6.23 → 9.7.6
- **ruff** 0.15.1 → 0.15.7
- **mistralai** 1.12.3 → 2.1.2 (major bump, transitive dep via pydantic-ai)
- **websockets** 15.0.1 → 16.0 (major bump, transitive)
- **huggingface-hub** 0.36.2 → 1.7.2 (major bump, transitive via litellm)
- **virtualenv** 20.36.1 → 21.2.0 (major bump, transitive via pre-commit)

No code changes needed — ruff check, ruff format, and pyright all passed clean.
The `griffe`/`griffecli`/`invoke`/`rsa` packages were removed (no longer needed by updated deps).
New transitive deps added: `typer`, `shellingham`, `annotated-doc`, `uncalled-for`, `python-discovery`.
