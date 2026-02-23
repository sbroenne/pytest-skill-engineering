---
description: "Comprehensive assertion examples for pytest-skill-engineering. Covers tool calls, output validation, performance checks, CLI results, and more — all using plain pytest assertions."
---

# Assertions Cookbook

pytest-skill-engineering uses **plain pytest assertions**. There's no custom DSL — you write Python:

```python
assert result.success
assert result.tool_was_called("transfer")
assert "balance" in result.final_response
```

This page shows how to assert everything you'd want to check, organized by category.

## Tool Call Assertions

### Was a tool called?

```python
assert result.tool_was_called("get_balance")
assert not result.tool_was_called("delete_account")
```

### How many times?

```python
assert result.tool_call_count("get_balance") == 2
assert result.tool_call_count("transfer") >= 1
```

### Tool call order

Verify tools were called in a specific sequence:

```python
names = [c.name for c in result.all_tool_calls]
assert names.index("get_balance") < names.index("transfer")
```

Or check an exact sequence of calls:

```python
names = [c.name for c in result.all_tool_calls]
assert names == ["get_balance", "transfer", "get_balance"]
```

### Tool parameters

Check what arguments were passed to a tool:

```python
# First call's argument
assert result.tool_call_arg("transfer", "amount") == 200

# All calls to a tool
for call in result.tool_calls_for("transfer"):
    assert call.arguments["from_account"] == "checking"

# Nested parameters (dot notation — manually)
call = result.tool_calls_for("create_user")[0]
assert call.arguments["address"]["city"] == "Paris"
```

### Parameter pattern matching

```python
import re

call = result.tool_calls_for("search")[0]
assert re.match(r"\d{4}-\d{2}-\d{2}", call.arguments["date"])
```

### Tool results

Inspect what a tool returned:

```python
import json

call = result.tool_calls_for("get_balance")[0]
data = json.loads(call.result)
assert data["balance"] >= 0
```

Use JSONPath for complex tool results (install `jsonpath-ng`):

```python
from jsonpath_ng import parse

call = result.tool_calls_for("get_user")[0]
data = json.loads(call.result)
matches = parse("$.accounts[*].type").find(data)
assert any(m.value == "checking" for m in matches)
```

### Only expected tools were called

```python
allowed = {"get_balance", "get_transactions"}
assert result.tool_names_called <= allowed
```

### No tools were called

```python
assert len(result.all_tool_calls) == 0
```

## Output Assertions

### Contains text

```python
assert "balance" in result.final_response.lower()
assert "$500" in result.final_response
```

### Does NOT contain text

```python
assert "error" not in result.final_response.lower()
assert "sorry" not in result.final_response.lower()
```

### Regex match

```python
import re

assert re.search(r"\$\d+\.\d{2}", result.final_response)
```

### All responses (multi-turn)

```python
all_text = " ".join(result.all_responses)
assert "transferred" in all_text.lower()
```

### Semantic assertions

Use the built-in `llm_assert` fixture (powered by pydantic-evals LLM judge) for meaning-based checks:

```python
async def test_response_quality(eval_run, agent, llm_assert):
    result = await eval_run(agent, "Show me my balances")
    assert llm_assert(
        result.final_response,
        "includes both checking and savings account balances"
    )
```

Configure the judge model via `--llm-model`:

```bash
# GitHub Copilot
pytest --llm-model=copilot/gpt-5-mini

# Azure OpenAI
pytest --llm-model=azure/gpt-5.2-chat
```

## Multi-Dimension Scoring

Use the `llm_score` fixture for rubric-based evaluation across multiple dimensions:

```python
from pytest_skill_engineering import ScoringDimension, assert_score

RUBRIC = [
    ScoringDimension("accuracy", "Correct and factual content"),
    ScoringDimension("completeness", "Covers all requested topics"),
    ScoringDimension("clarity", "Well-organized and readable"),
]

async def test_output_quality(eval_run, agent, llm_score):
    result = await eval_run(agent, "Explain retry patterns")
    scores = llm_score(result.final_response, RUBRIC)
    assert_score(scores, min_total=10)  # 10/15
```

### Threshold variants

```python
# Percentage threshold
assert_score(scores, min_pct=0.7)  # 70% of max

# Per-dimension minimums
assert_score(scores, min_dimensions={"accuracy": 4, "completeness": 3})

# Combined
assert_score(scores, min_total=10, min_dimensions={"accuracy": 4})
```

### Weighted dimensions

```python
RUBRIC = [
    ScoringDimension("accuracy", "Factual correctness", weight=2.0),
    ScoringDimension("style", "Writing quality", weight=0.5),
]
scores = llm_score(content, RUBRIC)
print(scores.weighted_score)  # 0.0-1.0 weighted average
```

See the [Multi-Dimension Scoring guide](../how-to/multi-dimension-scoring.md) for full details.

## Image Assertions

### Check if images were returned

```python
screenshots = result.tool_images_for("screenshot")
assert len(screenshots) > 0
assert screenshots[-1].media_type == "image/png"
assert len(screenshots[-1].data) > 1000  # Reasonable size
```

### AI-graded image evaluation

Use the `llm_assert_image` fixture to have a vision LLM evaluate an image:

```python
async def test_chart_quality(eval_run, agent, llm_assert_image):
    result = await eval_run(agent, "Create a bar chart")
    screenshots = result.tool_images_for("screenshot")
    assert llm_assert_image(
        screenshots[-1],
        "shows a bar chart with labeled axes"
    )
```

Configure the vision judge model via `--llm-vision-model` or `--llm-model`:

```bash
# GitHub Copilot (vision-capable)
pytest --llm-vision-model=copilot/gpt-4o

# Azure OpenAI
pytest --llm-vision-model=azure/gpt-4o
```

### Image properties

```python
screenshots = result.tool_images_for("screenshot")
for img in screenshots:
    print(f"Type: {img.media_type}, Size: {len(img.data)} bytes")
```

See the [Image Assertions guide](../how-to/image-assertions.md) for complete documentation.

## Performance Assertions

### Max duration

```python
assert result.duration_ms < 10_000  # Under 10 seconds
```

### Max tokens

```python
total_tokens = result.token_usage.get("prompt", 0) + result.token_usage.get("completion", 0)
assert total_tokens < 5000
```

### Max cost

```python
assert result.cost_usd < 0.01  # Under 1 cent
```

### Max turns

```python
assert len(result.turns) <= 6
```

## Error Assertions

### No errors

```python
assert result.success
assert result.error is None
```

### Tool errors

Check that no tool call produced an error:

```python
assert all(c.error is None for c in result.all_tool_calls)
```

### Expected error handling

Verify the agent handled an error gracefully:

```python
result = await eval_run(agent, "Transfer $1M from empty account")
# Eval should succeed (handle the error), not crash
assert result.success
assert "insufficient" in result.final_response.lower()
```

## Clarification Detection

Requires `ClarificationDetection(enabled=True)` on the agent. See [Choosing a Harness](../explanation/choosing-a-harness.md) for setup.

### Eval didn't ask questions

```python
assert not result.asked_for_clarification
```

### Count clarification requests

```python
assert result.clarification_count == 0
```

### Inspect clarification details

```python
if result.clarification_stats:
    print(f"Asked {result.clarification_stats.count} time(s)")
    print(f"At turns: {result.clarification_stats.turn_indices}")
    print(f"Examples: {result.clarification_stats.examples}")
```

## CLI Server Assertions

When testing CLI tools via `CLIServer`, tool results contain JSON with `exit_code`, `stdout`, and `stderr`:

```python
import json

# Get the CLI execution result
call = result.tool_calls_for("git_execute")[0]
cli_result = json.loads(call.result)

# Exit code
assert cli_result["exit_code"] == 0

# Stdout content
assert "main" in cli_result["stdout"]

# Stderr is empty (no errors)
assert cli_result["stderr"] == ""
```

### Regex on CLI output

```python
import re

call = result.tool_calls_for("git_execute")[0]
cli_result = json.loads(call.result)
assert re.search(r"commit [a-f0-9]{7}", cli_result["stdout"])
```

## Session Assertions

### Verifying context continuity

```python
@pytest.mark.session("banking-flow")
class TestBankingWorkflow:
    async def test_check_balance(self, eval_run, agent):
        result = await eval_run(agent, "What's my checking balance?")
        assert result.success
        assert not result.is_session_continuation

    async def test_transfer(self, eval_run, agent):
        result = await eval_run(agent, "Transfer $100 to savings")
        assert result.success
        assert result.is_session_continuation
        assert result.session_context_count > 0
```

### Data extraction between session tests

Extract values from tool results and use them in later tests:

```python
@pytest.mark.session("user-flow")
class TestUserWorkflow:
    user_id: str

    async def test_create(self, eval_run, agent):
        result = await eval_run(agent, "Create a user named Alice")
        assert result.success
        # Extract from tool result
        call = result.tool_calls_for("create_user")[0]
        data = json.loads(call.result)
        self.__class__.user_id = data["id"]

    async def test_lookup(self, eval_run, agent):
        result = await eval_run(
            agent, f"Find user {self.user_id}"
        )
        assert result.tool_was_called("get_user")
```

## Boolean Combinators

Use Python's `and`, `or`, `not` — no special syntax needed:

```python
# ANY of these tools was called (OR)
assert result.tool_was_called("get_balance") or result.tool_was_called("get_all_balances")

# ALL of these tools were called (AND)
assert result.tool_was_called("get_balance") and result.tool_was_called("transfer")

# This tool was NOT called (NOT)
assert not result.tool_was_called("delete_account")
```

For complex conditions, use `any()` / `all()`:

```python
required_tools = ["get_balance", "transfer", "get_transactions"]
assert all(result.tool_was_called(t) for t in required_tools)

optional_tools = ["get_exchange_rate", "convert_currency"]
assert any(result.tool_was_called(t) for t in optional_tools)
```

## Skill Assertions

### Skill references were used

When an agent has a skill with references, verify the agent accessed them:

```python
assert result.tool_was_called("read_skill_reference")
```

### Specific reference was read

```python
call = result.tool_calls_for("read_skill_reference")[0]
assert call.arguments["filename"] == "pricing-rules.md"
```
