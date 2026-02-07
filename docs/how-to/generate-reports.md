# How to Generate Reports

Generate HTML, JSON, and Markdown reports with AI-powered insights.

## Quick Start (Recommended)

Configure once in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = """
--aitest-summary-model=azure/gpt-5.2-chat
--aitest-html=aitest-reports/report.html
"""
```

Then just run:

```bash
pytest tests/
```

Reports are generated automatically with AI insights. This approach is recommended because:

- **Version controlled** — Team shares the same configuration
- **Less typing** — No need to remember CLI flags
- **Consistent** — Every run produces reports the same way

!!! important
    AI insights are **mandatory** for report generation. You must specify `--aitest-summary-model`.

## CLI Options (Alternative)

You can also use CLI flags directly:

```bash
# Run tests with AI-powered HTML report
pytest tests/ \
    --aitest-summary-model=azure/gpt-5.2-chat \
    --aitest-html=report.html

```

| Option | Description |
|--------|-------------|
| `--aitest-html=PATH` | Generate HTML report |
| `--aitest-json=PATH` | Custom JSON path (default: `aitest-reports/results.json`) |
| `--aitest-summary-model=MODEL` | Model for AI insights (**required**) |
| `--aitest-min-pass-rate=N` | Fail if pass rate below N% (e.g., `80`) |

## Report Regeneration

Regenerate reports from saved JSON without re-running tests:

```bash
# Regenerate HTML from saved JSON (reuses existing AI insights)
pytest-aitest-report aitest-reports/results.json \
    --html report.html

# Regenerate with fresh AI insights from a different model
pytest-aitest-report results.json \
    --html report.html \
    --summary --summary-model azure/gpt-4.1
```

This is useful for:

- Iterating on report styling without re-running expensive LLM tests
- Generating different formats from one test run
- Experimenting with different AI summary models

## Agent Leaderboard

When you test multiple agents, the report shows an **Agent Leaderboard** ranking all configurations:

| Agent | Pass Rate | Cost |
|-------|-----------|------|
| ✓ gpt-4.1 (detailed) | 100% | $0.15 |
| ✓ gpt-5-mini (detailed) | 97% | $0.03 |
| ✗ gpt-5-mini (concise) | 82% | $0.02 |

**Winning Agent = Highest pass rate → Lowest cost (tiebreaker)**

### Dimension Detection

The AI detects *what varies* between agents to focus its analysis:

| What Varies | AI Analysis Focuses On |
|-------------|------------------------|
| Model | Which model works best |
| System Prompt | Which instructions work best |
| Skill | Whether domain knowledge helps |
| Server | Which implementation is more reliable |

**Winning = Highest pass rate → Lowest cost (tiebreaker)**

### Leaderboard Ranking

When comparing Agents, rankings are based on:

1. **Pass rate** (primary) — higher is better
2. **Total cost** (tiebreaker) — lower is better

## AI Insights

Reports include AI analysis with actionable recommendations. For a detailed explanation of each insight section, see [AI Analysis](../explanation/ai-reports.md).

### Recommended Models

Use the **most capable model you can afford** for quality analysis:

| Provider | Recommended Models |
|----------|-------------------|
| Azure OpenAI | `azure/gpt-5.2-chat` (best), `azure/gpt-4.1` |
| OpenAI | `openai/gpt-4.1`, `openai/gpt-4o` |
| Anthropic | `anthropic/claude-opus-4`, `anthropic/claude-sonnet-4` |

!!! warning "Don't Use Cheap Models for Analysis"
    Smaller models (gpt-4o-mini, gpt-5-mini) produce generic, low-quality insights.
    The summary model analyzes your test results and generates actionable feedback.
    Use your most capable model here—this is a one-time cost per test run.

## Report Structure

For details on the HTML report layout including header, leaderboard, and test details, see [Report Structure](../contributing/report-structure.md).

## JSON Report Structure

```json
{
  "schema_version": "3.0",
  "mode": "model_comparison",
  "summary": {
    "total": 10,
    "passed": 8,
    "failed": 2,
    "pass_rate": 80.0
  },
  "dimensions": {
    "models": ["gpt-5-mini", "gpt-4.1"],
    "prompts": ["concise", "detailed"]
  },
  "insights": {
    "markdown_summary": "## 🎯 Recommendation\n\n...",
    "recommendation": {...},
    "failures": [...],
    "mcp_feedback": [...]
  },
  "tests": [...]
}
```

## CI/CD Integration

### JUnit XML for CI Pipelines

pytest includes built-in JUnit XML output that works with all CI systems. Use it alongside aitest reports:

```bash
pytest tests/ \
    --junitxml=results.xml \
    --aitest-html=report.html \
    --aitest-summary-model=azure/gpt-5.2-chat
```

| Format | Purpose | Consumers |
|--------|---------|----------|
| `--junitxml` | Pass/fail tracking, test history | GitHub Actions, Azure Pipelines, Jenkins |
| `--aitest-html` | AI insights, tool analysis | Human review |
| `--aitest-json` | Raw data for custom tooling | Scripts, dashboards |

### JUnit XML Properties

pytest-aitest automatically enriches JUnit XML with agent metadata as `<property>` elements:

```xml
<testcase name="test_weather" time="2.34">
  <properties>
    <property name="aitest.agent.name" value="weather-agent"/>
    <property name="aitest.model" value="gpt-5-mini"/>
    <property name="aitest.skill" value="weather-expert"/>
    <property name="aitest.prompt" value="concise"/>
    <property name="aitest.servers" value="weather_mcp,calendar_mcp"/>
    <property name="aitest.allowed_tools" value="get_forecast,get_weather"/>
    <property name="aitest.tokens.input" value="1250"/>
    <property name="aitest.tokens.output" value="89"/>
    <property name="aitest.cost_usd" value="0.000425"/>
    <property name="aitest.turns" value="3"/>
    <property name="aitest.tools.called" value="get_forecast,get_weather"/>
    <property name="aitest.success" value="true"/>
  </properties>
</testcase>
```

| Property | Description |
|----------|-------------|
| `aitest.agent.name` | Agent identifier |
| `aitest.model` | LLM model used |
| `aitest.skill` | Skill name (if used) |
| `aitest.prompt` | System prompt name (if parametrized) |
| `aitest.servers` | Comma-separated list of MCP server names |
| `aitest.allowed_tools` | Tool filter from Agent (if specified) |
| `aitest.tokens.input` | Input tokens consumed |
| `aitest.tokens.output` | Output tokens generated |
| `aitest.cost_usd` | Estimated cost in USD |
| `aitest.turns` | Number of conversation turns |
| `aitest.tools.called` | Comma-separated list of tools called |
| `aitest.success` | Whether the agent completed successfully |

These properties enable CI dashboards to display agent metrics alongside test results.

### GitHub Actions

This project includes a ready-to-use hero test workflow at `.github/workflows/hero-tests.yml`.

#### How It Works

1. **Trigger**: Add the `run-hero-tests` label to a PR, or run manually via `workflow_dispatch`
2. **Authentication**: Uses Azure OIDC (Workload Identity Federation) — no stored API keys
3. **Execution**: Runs `tests/showcase/` against Azure OpenAI with AI-powered insights
4. **Results**:
    - **JUnit annotations** on the PR checks tab (pass/fail per test)
    - **HTML report artifact** downloadable from the workflow run
    - **Auto-commit** of `docs/demo/hero-report.html` back to the branch
5. **Cleanup**: The `run-hero-tests` label is automatically removed after completion

#### Workflow Overview

```yaml
# .github/workflows/hero-tests.yml (simplified)
- name: Azure login (OIDC)
  uses: azure/login@v2
  with:
    client-id: ${{ secrets.AZURE_CLIENT_ID }}
    tenant-id: ${{ secrets.AZURE_TENANT_ID }}
    subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

- name: Run hero tests
  run: |
    uv run pytest tests/showcase/ -v \
      --aitest-html=docs/demo/hero-report.html \
      --junitxml=hero-results.xml \
      -o "addopts=--aitest-summary-model=azure/gpt-5.2-chat"

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

#### Azure OIDC Setup (One-Time)

To enable the workflow, configure Workload Identity Federation in Azure:

1. **Create an App Registration** in Azure Entra ID
2. **Add a federated credential** for your GitHub repo:
    - Issuer: `https://token.actions.githubusercontent.com`
    - Subject: `repo:YOUR_ORG/YOUR_REPO:environment:hero-tests`
    - Audience: `api://AzureADTokenExchange`
3. **Grant access**: Assign `Cognitive Services OpenAI User` role on your Azure OpenAI resource
4. **Add GitHub secrets**:
    - `AZURE_CLIENT_ID` — App Registration client ID
    - `AZURE_TENANT_ID` — Azure AD tenant ID
    - `AZURE_SUBSCRIPTION_ID` — Azure subscription ID
5. **Create GitHub environment**: Named `hero-tests` (optional, for protection rules)
6. **Create PR label**: Add `run-hero-tests` label to the repository

!!! tip "No API Keys Required"
    OIDC uses short-lived tokens exchanged at runtime. No secrets to rotate.

#### Overriding pyproject.toml Defaults

The `addopts` in `pyproject.toml` sets default report paths. The workflow overrides this using pytest's `-o` flag:

```bash
# Override addopts to avoid conflict with pyproject.toml defaults
uv run pytest tests/showcase/ -v \
  -o "addopts=--aitest-summary-model=azure/gpt-5.2-chat" \
  --aitest-html=docs/demo/hero-report.html \
  --junitxml=hero-results.xml
```

#### Custom Workflow

For your own tests, adapt the pattern:

```yaml
# .github/workflows/test.yml
- name: Run agent tests
  run: |
    pytest tests/ \
      --junitxml=reports/results.xml \
      --aitest-html=reports/report.html \
      --aitest-json=reports/report.json \
      --aitest-summary-model=azure/gpt-5.2-chat

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

### Azure Pipelines

```yaml
- task: PublishTestResults@2
  inputs:
    testResultsFormat: 'JUnit'
    testResultsFiles: 'reports/results.xml'
  condition: always()
```
