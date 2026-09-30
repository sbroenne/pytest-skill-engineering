# CI/CD integration

Run authorized live cases with Copilot access, and upload native evidence plus
ordinary pytest outcomes. Your coding agent interprets the evidence.

```powershell
uv run python -m pytest "tests\test_tools.py" --junitxml=results.xml --aitest-json=results.json
```

JUnit includes all collected test outcomes. Eval reports include tests with
captured eval execution; setup failures and ordinary tests without eval results
remain visible through pytest and JUnit.

## GitHub Actions

```yaml
permissions:
  contents: read
  copilot-requests: write

steps:
  - uses: actions/checkout@v4
  - uses: astral-sh/setup-uv@v7
  - run: uv sync --frozen
  - name: Run authorized evals
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

Use the authentication and organization billing settings approved for your
repository. The runtime selects `GITHUB_TOKEN` before `GH_TOKEN`; a token alone
does not establish Copilot entitlement. Protect paid workflows with appropriate
approvals and do not expose credentials to untrusted pull-request code.

The repository's integration and hero workflows are examples of explicit live
execution. Do not turn them into automatic report-judging jobs. Reading saved
JSON does not require those permissions.

## Verification properties and metrics

Use `record_property` for safe application checks and build identifiers.
Framework JUnit metadata includes eval identity, model, server names, tool
filters, usage, and session success where available. Session success is not
application correctness; assert the independent check too.

Missing usage is not known zero. USD values are estimates requiring explicit
pricing. A/B entries share one test outcome: preserve side-specific verification.

## Offline checks

Control, schema, and report contracts can run without paid model calls:

```powershell
uv run python -m pytest "tests\contracts" -q -o addopts=
```

These establish framework boundaries and evidence fidelity, not model performance.
Use real integration cases for AI-facing execution changes.
