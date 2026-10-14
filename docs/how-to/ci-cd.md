# CI/CD integration

Run explicitly authorized live tasks in CI and upload native JSON with ordinary
pytest outcomes. Keep paid workflows separate from offline checks. A saved
report records execution; your assertions still determine task correctness.

## GitHub Actions

This complete workflow assumes a committed uv lockfile, installed test
dependencies, and your live task file at `tests/test_tools.py`:

```yaml
name: Copilot task checks

on:
  workflow_dispatch:

jobs:
  task-checks:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      copilot-requests: write
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@v10
      - run: uv sync --frozen
      - name: Run authorized tasks
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          uv run python -m pytest tests/test_tools.py -o addopts= \
            --junitxml=reports/results.xml \
            --aitest-json=reports/results.json
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: test-evidence
          path: reports/
```

Use authentication and organization billing settings approved for your
repository. The permission and token do not by themselves establish Copilot
entitlement. `GITHUB_TOKEN` takes precedence over `GH_TOKEN`. Protect paid jobs
with appropriate approvals and never expose credentials to untrusted
pull-request code. Pin action revisions according to your repository policy.

`workflow_dispatch` makes this example manual; it is not an automatic paid PR
check. Reading saved JSON requires no Copilot credentials or request permission.

## Preserve all pytest outcomes

JUnit includes ordinary tests and setup failures, including cases with no
captured eval result. Native JSON includes captured task executions and their
pytest outcomes. Absence from task evidence does not mean a test passed.

The `-o addopts=` override removes inherited options so the destinations above
are explicit. A failed JSON publication returns nonzero and keeps a prior file
intact; stale evidence must not be mistaken for the current run.

## Verification properties and metrics

Record safe build identifiers and application observations with
`record_property`, then assert the independent check. Framework JUnit metadata
also includes available configuration and execution fields, such as model,
tool filters, usage, and session success.

Session success is not application correctness. Missing usage is unknown,
not zero. USD estimates need explicit [pricing](cost-estimation.md).
Paired A/B entries share one pytest outcome; save verification for each side.

## Offline checks

For changes to this repository's controls and evidence contracts:

```bash
uv run python -m pytest tests/contracts -q -o addopts=
```

These checks need no paid model calls and establish framework behavior, not
model performance. The
[skill dogfooding sample](https://github.com/sbroenne/pytest-skill-engineering/tree/main/examples/skill-dogfood)
also defaults to offline tests; its local live cases are explicit.
Use authorized real integration cases when changing AI-facing execution.
