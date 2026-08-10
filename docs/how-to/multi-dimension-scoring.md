---
description: "Score outputs on multiple rubric dimensions with llm_score and Copilot judge models."
---

# Multi-dimension scoring

Use `llm_score` when you want rubric-based evaluation instead of a single boolean assertion.

## Define a rubric

```python
from pytest_skill_engineering import ScoringDimension


RUBRIC = [
    ScoringDimension("accuracy", "The response is factually correct."),
    ScoringDimension("coverage", "The response covers the required points."),
    ScoringDimension("actionability", "The response gives actionable next steps."),
]
```

## Score content

```python
def test_plan_quality(llm_score, plan_text):
    result = llm_score(plan_text, RUBRIC, content_label="implementation plan")

    assert result.total >= 6
```

## Judge model resolution

The judge model resolves in this order:

1. `--llm-model`
2. `--aitest-summary-model`
3. `copilot/gpt-5.4-mini`

Examples:

```bash
uv run python -m pytest tests/ --llm-model=copilot/gpt-5.4-mini
uv run python -m pytest tests/ --aitest-summary-model=copilot/gpt-5.4-mini
```
