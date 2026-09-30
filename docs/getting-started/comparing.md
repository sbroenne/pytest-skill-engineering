# Comparing configurations

Choose a question, fix the output criteria, and vary one factor: model, system
prompt, skill, custom agent definition, or server configuration.

For separate parametrized tests, each test has its own pytest outcome. For
`ab_run`, both saved entries share the combined test's outcome; record checks
for each side separately.

```python
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from pytest_skill_engineering.copilot import CopilotEval


async def test_skill_comparison(ab_run, record_property):
    baseline = CopilotEval(
        name="baseline", model="gpt-5.6-luna",
        instructions="Calculate the requested amount and save the JSON file.",
    )
    treatment = replace(
        baseline, name="with-skill", skill_directories=["skills/math-helper"],
    )
    before, after = await ab_run(
        baseline, treatment,
        "Write amount.json with only the numeric field total, equal to 1000 * 1.05 ** 3.",
    )
    verified = []
    for side, result in (("baseline", before), ("treatment", after)):
        assert result.agent is not None
        assert result.agent.working_directory is not None
        path = Path(result.agent.working_directory) / "amount.json"
        observed = json.loads(path.read_text())
        passed = abs(observed["total"] - 1000 * 1.05**3) < 0.00001
        record_property(f"{side}_verification", {
            "artifact": str(path), "observed": observed, "passed": passed,
        })
        verified.append(result.success and passed)
    assert all(verified)
```

Supply your own skill at that path. `ab_run` creates separate working directories
and executes sequentially, but does not reset shared external services or
desktops. Own those resets when relevant.

## Interpret observations carefully

Keep the task, model, initial data, permissions, tools, limits, and checks fixed.
Use a representative case set and [repetitions](iterations.md) for reliability.
Do not turn one observed difference into a causal improvement claim.

Your coding agent interprets the saved outcomes and usage. The framework does
not rank configurations, and the shared outcome of an A/B test is not an
independent per-side pass rate.
Unavailable pricing is not measured zero cost.

See [server comparisons](ab-testing-servers.md) and
[evidence inspection](../how-to/inspect-evidence.md) for captured configuration and evidence.
