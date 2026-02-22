---
description: "Run pytest-skill-engineering in CI/CD pipelines with JUnit XML, GitHub Actions, and Azure Pipelines. Includes OIDC authentication setup."
---

# CI/CD Integration

Run pytest-skill-engineering in CI pipelines with JUnit XML reporting and automated report generation.

## JUnit XML for CI Pipelines

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
| `--aitest-md` | Documentation, wikis | mkdocs, GitHub wikis, READMEs |
| `--aitest-json` | Raw data for custom tooling | Scripts, dashboards |

## JUnit XML Properties

pytest-skill-engineering automatically enriches JUnit XML with agent metadata as `<property>` elements:

```xml
<testcase name="test_balance" time="2.34">
  <properties>
    <property name="aitest.agent.name" value="banking-agent"/>
    <property name="aitest.model" value="gpt-5-mini"/>
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

## GitHub Actions

This project includes a ready-to-use hero test workflow at `.github/workflows/hero-tests.yml`.

### How It Works

1. **Trigger**: Add the `run-hero-tests` label to a PR, or run manually via `workflow_dispatch`
2. **Authentication**: Uses Azure OIDC (Workload Identity Federation) — no stored API keys
3. **Execution**: Runs `tests/showcase/` against Azure OpenAI with AI-powered insights
4. **Results**:
    - **JUnit annotations** on the PR checks tab (pass/fail per test)
    - **HTML report artifact** downloadable from the workflow run
    - **Auto-commit** of `docs/demo/hero-report.html` back to the branch
5. **Cleanup**: The `run-hero-tests` label is automatically removed after completion

### Workflow Overview

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

### Azure OIDC Setup (One-Time)

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

### Overriding pyproject.toml Defaults

The `addopts` in `pyproject.toml` sets default report paths. The workflow overrides this using pytest's `-o` flag:

```bash
# Override addopts to avoid conflict with pyproject.toml defaults
uv run pytest tests/showcase/ -v \
  -o "addopts=--aitest-summary-model=azure/gpt-5.2-chat" \
  --aitest-html=docs/demo/hero-report.html \
  --junitxml=hero-results.xml
```

### Custom Workflow

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

## Azure Pipelines

```yaml
- task: PublishTestResults@2
  inputs:
    testResultsFormat: 'JUnit'
    testResultsFiles: 'reports/results.xml'
  condition: always()
```
