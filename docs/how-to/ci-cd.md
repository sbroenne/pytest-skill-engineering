---
description: "Run pytest-skill-engineering in CI/CD pipelines with JUnit XML, GitHub Actions, and Azure Pipelines. Includes OIDC authentication setup."
---

# CI/CD Integration

Run pytest-skill-engineering in CI pipelines with JUnit XML reporting and automated report generation.

## JUnit XML for CI Pipelines

pytest includes built-in JUnit XML output that works with all CI systems. Use it alongside report generation:

```bash
uv run python -m pytest tests/ \
    --junitxml=results.xml \
    --aitest-html=report.html \
    --aitest-summary-model=copilot/gpt-5.4-mini
```

| Format | Purpose | Consumers |
|--------|---------|----------|
| `--junitxml` | Pass/fail tracking, test history | GitHub Actions, Azure Pipelines, Jenkins |
| `--aitest-html` | AI insights, tool analysis | Human review |
| `--aitest-md` | Documentation, wikis | mkdocs, GitHub wikis, READMEs |
| `--aitest-json` | Raw data for custom tooling | Scripts, dashboards |

## JUnit XML Properties

pytest-skill-engineering automatically enriches JUnit XML with eval metadata as `<property>` elements:

```xml
<testcase name="test_balance" time="2.34">
  <properties>
    <property name="aitest.agent.name" value="banking-agent"/>
    <property name="aitest.model" value="gpt-5.4-mini"/>
    <property name="aitest.skill" value="financial-advisor"/>
    <property name="aitest.prompt" value="concise"/>
    <property name="aitest.servers" value="banking_mcp,calendar_mcp"/>
    <property name="aitest.allowed_tools" value="get_balance,transfer"/>
    <property name="aitest.tokens.input" value="1250"/>
    <property name="aitest.tokens.output" value="89"/>
    <property name="aitest.cost_usd" value="0.000425"/>
    <property name="aitest.turns" value="3"/>
    <property name="aitest.tools.called" value="get_balance,transfer"/>
    <property name="aitest.success" value="true"/>
  </properties>
</testcase>
```

| Property | Description |
|----------|-------------|
| `aitest.agent.name` | Eval identifier |
| `aitest.model` | LLM model used |
| `aitest.skill` | Skill name (if used) |
| `aitest.prompt` | System prompt name (if parametrized) |
| `aitest.servers` | Comma-separated list of MCP server names |
| `aitest.allowed_tools` | Tool filter from Eval (if specified) |
| `aitest.tokens.input` | Input tokens consumed |
| `aitest.tokens.output` | Output tokens generated |
| `aitest.cost_usd` | Estimated cost in USD |
| `aitest.turns` | Number of conversation turns |
| `aitest.tools.called` | Comma-separated list of tools called |
| `aitest.success` | Whether the eval completed successfully |

These properties enable CI dashboards to display eval metrics alongside test results.

## GitHub Actions

This project includes a ready-to-use hero test workflow at `.github/workflows/hero-tests.yml`.

### How It Works

1. **Trigger**: Add the `run-hero-tests` label to a PR, or run manually via `workflow_dispatch`
2. **Authentication**: Grants `copilot-requests: write` and passes the built-in `GITHUB_TOKEN` directly to the Copilot SDK
3. **Execution**: Runs `tests/showcase/` against the current Copilot SDK setup with AI-powered insights
4. **Results**:
    - **JUnit annotations** on the PR checks tab (pass/fail per test)
    - **HTML report artifact** downloadable from the workflow run
    - **Auto-commit** of `docs/demo/hero-report.html` back to the branch
5. **Cleanup**: The `run-hero-tests` label is automatically removed after completion

### Workflow Overview

```yaml
# .github/workflows/hero-tests.yml (simplified)
permissions:
  contents: write
  copilot-requests: write

- name: Run hero tests
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    uv run python -m pytest tests/showcase/ -v \
      --aitest-html=docs/demo/hero-report.html \
      --junitxml=hero-results.xml \
      -o "addopts=--aitest-summary-model=copilot/gpt-5.5"

- name: Publish JUnit results
  uses: dorny/test-reporter@v1
  if: always()
  with:
    name: Hero Test Results
    path: hero-results.xml
    reporter: java-junit

- name: Upload HTML report
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: hero-report
    path: |
      docs/demo/hero-report.html
      aitest-reports/results*.json

- name: Commit updated hero report
  uses: stefanzweifel/git-auto-commit-action@v5
  if: success()
  with:
    commit_message: "ci: update hero report [skip ci]"
    file_pattern: docs/demo/hero-report.html
```

### Copilot CI Auth Setup

To enable Copilot-backed CI runs:

1. Grant the job `contents: read` (or `write` when committing reports) and `copilot-requests: write`
2. Pass `${{ secrets.GITHUB_TOKEN }}` to the test process as `GITHUB_TOKEN`
3. For organization-owned repositories, enable **Allow use of Copilot CLI billed to the organization**
4. Create the optional `hero-tests` environment if you want protection rules
5. Create the `run-hero-tests` PR label

### Overriding pyproject.toml Defaults

The `addopts` in `pyproject.toml` sets default report paths. The workflow overrides this using pytest's `-o` flag:

```bash
# Override addopts to avoid conflict with pyproject.toml defaults
uv run python -m pytest tests/showcase/ -v \
  -o "addopts=--aitest-summary-model=copilot/gpt-5.5" \
  --aitest-html=docs/demo/hero-report.html \
  --junitxml=hero-results.xml
```

### Custom Workflow

For your own tests, adapt the pattern:

```yaml
# .github/workflows/test.yml
- name: Run eval tests
  run: |
    uv run python -m pytest tests/ \
      --junitxml=reports/results.xml \
      --aitest-html=reports/report.html \
      --aitest-json=reports/report.json \
      --aitest-summary-model=copilot/gpt-5.5

- name: Upload test results
  uses: actions/upload-artifact@v4
  if: always()
  with:
    name: test-reports
    path: reports/

- name: Publish JUnit results
  uses: dorny/test-reporter@v1
  if: always()
  with:
    name: Test Results
    path: reports/results.xml
    reporter: java-junit
```

## Azure Pipelines

```yaml
- task: PublishTestResults@2
  inputs:
    testResultsFormat: 'JUnit'
    testResultsFiles: 'reports/results.xml'
  condition: always()
```
