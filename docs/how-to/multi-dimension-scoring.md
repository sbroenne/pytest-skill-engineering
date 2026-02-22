---
description: "Score AI agent output on multiple named dimensions using LLM-as-judge evaluation with configurable rubrics, weighted composites, and threshold assertions."
---

# Multi-Dimension Scoring

Evaluate AI agent output on multiple named dimensions using the `llm_score` fixture. Each dimension receives an integer score on a configurable scale, enabling quality regression testing and A/B comparisons.

## Overview

| Fixture | Use Case | Return Type |
|---------|----------|-------------|
| `llm_assert` | Single-criterion pass/fail | `bool` |
| `llm_score` | Multi-dimension numeric scoring | `ScoreResult` |

Use `llm_assert` for binary assertions ("does the response mention X?"). Use `llm_score` when you need granular quality measurement across several dimensions.

## Quick Start

```python
from pytest_aitest import ScoringDimension, assert_score

RUBRIC = [
    ScoringDimension("accuracy", "Factually correct"),
    ScoringDimension("completeness", "Covers all required points"),
    ScoringDimension("clarity", "Easy to understand"),
]

async def test_plan_quality(aitest_run, agent, llm_score):
    result = await aitest_run(agent, "Create an implementation plan")

    scores = llm_score(
        result.final_response,
        RUBRIC,
        content_label="implementation plan",
    )

    # Assert minimum thresholds
    assert_score(scores, min_total=10)
```

## Defining a Rubric

A rubric is a list of `ScoringDimension` objects. Each dimension has:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | required | Short identifier (e.g. `"accuracy"`) |
| `description` | `str` | required | What the judge evaluates |
| `max_score` | `int` | `5` | Upper bound of the scale (minimum is always 1) |
| `weight` | `float` | `1.0` | Relative weight for composite score |

```python
from pytest_aitest import ScoringDimension

RUBRIC = [
    ScoringDimension(
        "phase_structure",
        "Plan has clearly numbered, ordered implementation phases "
        "with specific actionable steps.",
    ),
    ScoringDimension(
        "file_references",
        "Plan references specific files from the codebase by path.",
    ),
    ScoringDimension(
        "validation_phase",
        "Includes a final validation phase with lint, build, and test steps.",
        max_score=10,  # Custom scale
        weight=2.0,    # Double importance in composite score
    ),
]
```

## Using the Fixture

### Sync Usage (default)

```python
def test_output_quality(llm_score):
    result = llm_score(content, RUBRIC)
    assert result.total >= 10
```

### With Context

Provide additional context to help the judge evaluate:

```python
def test_plan_quality(llm_score):
    result = llm_score(
        plan_text,
        RUBRIC,
        content_label="implementation plan",
        context=f"The task was: {TASK}\n\nCodebase:\n{source_files}",
    )
    assert_score(result, min_total=15)
```

### Async Usage

For async test functions, use `async_score()`:

```python
async def test_output_quality(llm_score):
    result = await llm_score.async_score(content, RUBRIC)
    assert result.total >= 10
```

## ScoreResult

`llm_score` returns a `ScoreResult` with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `scores` | `dict[str, int]` | Per-dimension scores keyed by name |
| `total` | `int` | Sum of all dimension scores |
| `max_total` | `int` | Maximum possible total |
| `weighted_score` | `float` | Weighted composite (0.0 – 1.0) |
| `reasoning` | `str` | Free-text explanation from the judge |

```python
result = llm_score(content, RUBRIC)

# Access individual scores
print(result.scores["accuracy"])      # e.g. 4
print(result.scores["completeness"])  # e.g. 3

# Totals
print(f"{result.total}/{result.max_total}")  # e.g. 12/15

# Weighted composite
print(f"{result.weighted_score:.0%}")  # e.g. 80%

# Judge reasoning
print(result.reasoning)
```

## Threshold Assertions

Use `assert_score()` for clean threshold checks:

```python
from pytest_aitest import assert_score

# Minimum total score
assert_score(result, min_total=10)

# Minimum weighted percentage
assert_score(result, min_pct=0.7)

# Per-dimension minimums
assert_score(result, min_dimensions={"accuracy": 4, "completeness": 3})

# Combine all three
assert_score(
    result,
    min_total=10,
    min_pct=0.7,
    min_dimensions={"accuracy": 3},
)
```

Failed assertions include diagnostic details:

```
AssertionError: Total score 8/15 below minimum 10.
Scores: {'accuracy': 3, 'completeness': 2, 'clarity': 3}.
Reasoning: The plan lacks specific file references and ...
```

## Weighted Scoring

Dimension weights affect the `weighted_score` composite but not the `total` (raw sum):

```python
RUBRIC = [
    ScoringDimension("critical", "Must-have feature", weight=3.0),
    ScoringDimension("nice_to_have", "Optional polish", weight=1.0),
]

result = llm_score(content, RUBRIC)

# weighted_score considers weights:
# critical: 5/5 * 3.0 = 3.0
# nice_to_have: 2/5 * 1.0 = 0.4
# weighted = 3.4 / 4.0 = 0.85

assert_score(result, min_pct=0.8)
```

## A/B Testing with Scores

Compare agent variants by scoring both on the same rubric:

```python
import pytest
from pytest_aitest import Agent, Provider, ScoringDimension, assert_score

RUBRIC = [
    ScoringDimension("accuracy", "Factually correct"),
    ScoringDimension("completeness", "Covers all points"),
    ScoringDimension("clarity", "Easy to understand"),
]

AGENTS = [
    Agent(name="baseline", provider=Provider(model="azure/gpt-5-mini"), ...),
    Agent(name="improved", provider=Provider(model="azure/gpt-5-mini"), ...),
]

@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_plan_quality(aitest_run, agent, llm_score):
    result = await aitest_run(agent, "Create an implementation plan")
    scores = llm_score(result.final_response, RUBRIC)

    print(f"{agent.name}: {scores.total}/{scores.max_total} "
          f"({scores.weighted_score:.0%})")
    for dim, val in scores.scores.items():
        print(f"  {dim}: {val}")

    assert_score(scores, min_total=10)
```

The pytest-aitest HTML report shows scores per agent for comparison.

## Judge Model Configuration

The judge model is resolved in this order:

1. `--llm-model` if explicitly set
2. `--aitest-summary-model` (shared analysis model)
3. `openai/gpt-5-mini` as final fallback

```bash
# GitHub Copilot (no extra setup if pytest-aitest[copilot] installed)
pytest --llm-model=copilot/gpt-5-mini

# Azure OpenAI
pytest --llm-model=azure/gpt-5.2-chat

# Share model with report summary generation
pytest --aitest-summary-model=azure/gpt-5.2-chat
```

## Complete Example

```python
"""Evaluate task-planner output quality with multi-dimension scoring."""

from pathlib import Path

import pytest
from pytest_aitest import ScoringDimension, assert_score

RUBRIC = [
    ScoringDimension(
        "phase_structure",
        "Plan has clearly numbered, ordered implementation phases "
        "with specific actionable steps.",
    ),
    ScoringDimension(
        "file_references",
        "Plan references specific files from the codebase by path.",
    ),
    ScoringDimension(
        "parallelization",
        "Phases are annotated for parallelizability. Dependencies "
        "between phases are explicit.",
    ),
    ScoringDimension(
        "validation_phase",
        "Plan includes a final validation phase with lint, build, "
        "and test steps.",
    ),
    ScoringDimension(
        "success_criteria",
        "Each phase has measurable, verifiable success criteria.",
    ),
]


def test_plan_quality(llm_score, plan_text, seed_context):
    """LLM judge scores the plan on five dimensions."""
    result = llm_score(
        plan_text,
        RUBRIC,
        content_label="implementation plan",
        context=f"The task: add retry logic\n\n{seed_context}",
    )

    print(f"SCORES: {result.total}/{result.max_total}")
    for dim, score in result.scores.items():
        print(f"  {dim}: {score}")
    print(f"REASONING: {result.reasoning}")

    assert_score(result, min_total=15)
```

## Instruction Adherence Pattern

Evaluate whether agent output follows a set of instruction rules:

```python
ADHERENCE_RUBRIC = [
    ScoringDimension(
        "rule_coverage",
        "How many of the instruction's rules are reflected? "
        "5 = all rules observed, 1 = almost none.",
    ),
    ScoringDimension(
        "rule_accuracy",
        "For rules followed, how correctly are they applied? "
        "5 = perfectly, 1 = incorrectly.",
    ),
    ScoringDimension(
        "contamination_resistance",
        "Does the output avoid patterns that violate the instruction? "
        "5 = fully clean, 1 = copies bad patterns.",
    ),
    ScoringDimension(
        "completeness",
        "Is the output complete and functional? "
        "5 = fully complete, 1 = empty/stub.",
    ),
]


def test_conventions_followed(llm_score, code_text, conventions_text):
    result = llm_score(
        code_text,
        ADHERENCE_RUBRIC,
        content_label="Python code",
        context=conventions_text,
    )
    assert_score(result, min_total=12)
```

## Cost Awareness

Each `llm_score` call makes one LLM request. Typical costs per evaluation:

| Model | Approximate Cost |
|-------|-----------------|
| GPT-5-mini | ~$0.001-0.005 |
| GPT-5.2-chat | ~$0.01-0.03 |
| Claude Sonnet | ~$0.01-0.02 |

For A/B tests with multiple variants, total cost scales linearly with the number of evaluations.
