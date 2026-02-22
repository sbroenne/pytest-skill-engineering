---
description: "EvalResult API reference. Inspect tool calls, turns, tokens, cost, and assert on agent behavior in pytest-skill-engineering tests."
---

# EvalResult

Validate agent behavior using `EvalResult` properties and methods.

## Properties

| Property | Type | Description |
|----------|------|-------------|
| `success` | `bool` | Did the agent complete without errors? |
| `final_response` | `str` | The agent's final text response |
| `turns` | `list[Turn]` | All execution turns |
| `duration_ms` | `float` | Total execution time |
| `token_usage` | `dict[str, int]` | Prompt and completion token counts |
| `cost_usd` | `float` | Estimated cost in USD |
| `error` | `str \| None` | Error message if failed |
| `clarification_stats` | `ClarificationStats \| None` | Clarification detection stats (when enabled) |

## Clarification Detection

Detect when the agent asks for clarification instead of acting autonomously. Uses an LLM judge to classify responses.

The judge performs a simple YES/NO classification, so a cheap model like `gpt-5-mini` is sufficient. Unlike `--aitest-summary-model` (which generates complex analysis), the judge doesn't need a capable model.

### Configuration

```python
from pytest_skill_engineering import Eval, Provider, ClarificationDetection, ClarificationLevel

agent = Eval(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[server],
    clarification_detection=ClarificationDetection(
        enabled=True,
        level=ClarificationLevel.ERROR,       # INFO, WARNING, or ERROR
        judge_model="azure/gpt-5-mini",       # None = use agent's model
    ),
)
```

### Assertions

```python
# Did the agent ask for clarification?
assert not result.asked_for_clarification

# How many times?
assert result.clarification_count == 0

# Detailed stats
if result.clarification_stats:
    print(f"Count: {result.clarification_stats.count}")
    print(f"Turns: {result.clarification_stats.turn_indices}")
    print(f"Examples: {result.clarification_stats.examples}")
```

## Tool Assertions

### tool_was_called

Check if a tool was invoked:

```python
# Basic check - was it called at all?
assert result.tool_was_called("get_balance")

# Check specific call count
assert result.tool_call_count("get_balance") == 2
```

### tool_call_count

Get number of tool invocations:

```python
count = result.tool_call_count("get_balance")
assert count >= 1
assert count <= 5
```

### tool_call_arg

Get an argument from the first call to a tool:

```python
# Get argument from first call
account = result.tool_call_arg("get_balance", "account")
assert account == "checking"

# For multiple calls, use tool_calls_for and index manually
calls = result.tool_calls_for("get_balance")
if len(calls) > 1:
    second_account = calls[1].arguments.get("account")
```

### tool_calls_for

Get all calls to a specific tool:

```python
calls = result.tool_calls_for("get_balance")

for call in calls:
    print(f"Called with: {call.arguments}")
    print(f"Result: {call.result}")
```

### tool_images_for

Get all images returned by a specific tool:

```python
screenshots = result.tool_images_for("screenshot")

for img in screenshots:
    print(f"Type: {img.media_type}, Size: {len(img.data)} bytes")
```

Returns a list of `ImageContent` objects. Each has:

| Property | Type | Description |
|----------|------|-------------|
| `data` | `bytes` | Raw image bytes |
| `media_type` | `str` | MIME type (e.g., `"image/png"`) |

## ToolCall Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Tool name |
| `arguments` | `dict` | Arguments passed to the tool |
| `result` | `str \| None` | Text result (or description for images) |
| `error` | `str \| None` | Error message if failed |
| `duration_ms` | `float \| None` | Call duration |
| `image_content` | `bytes \| None` | Raw image data (if tool returned image) |
| `image_media_type` | `str \| None` | Image MIME type (if tool returned image) |

## Output Assertions

### Check Response Content

```python
# Case-insensitive content check
assert "checking" in result.final_response.lower()

# Multiple conditions
response = result.final_response.lower()
assert "balance" in response
assert "1,500" in response or "1500" in response
```

### Check for Absence

```python
# Ensure no errors mentioned
assert "error" not in result.final_response.lower()
assert "failed" not in result.final_response.lower()
```

## Performance Assertions

### Execution Time

```python
# Check total execution time
assert result.duration_ms < 30000  # Under 30 seconds
```

### Token Usage

```python
# Check total token consumption
total = result.token_usage.get("prompt", 0) + result.token_usage.get("completion", 0)
assert total < 5000

# Detailed breakdown
print(f"Prompt tokens: {result.token_usage.get('prompt', 0)}")
print(f"Completion tokens: {result.token_usage.get('completion', 0)}")
```

### Cost

```python
# Check estimated cost
assert result.cost_usd < 0.10  # Under 10 cents
```

## Error Handling

### Check for Success

```python
# Basic success check
assert result.success

# With error message on failure
assert result.success, f"Eval failed: {result.error}"
```

### Inspect Errors

```python
if not result.success:
    print(f"Error: {result.error}")
    
    # Check last turn for details
    last_turn = result.turns[-1]
    print(f"Last message: {last_turn.content}")
```

## AI-Powered Assertions

For semantic validation, use the built-in `llm_assert` fixture (powered by pydantic-evals LLM judge):

```python
async def test_response_quality(eval_run, agent, llm_assert):
    """Use the llm_assert fixture for semantic validation."""
    result = await eval_run(agent, "What's my checking balance?")
    
    assert result.success
    assert llm_assert(result.final_response, "mentions account balance")
```

## Complete Examples

### Testing Tool Selection

```python
async def test_correct_tool_selection(eval_run, agent):
    result = await eval_run(agent, "What's my checking balance?")
    
    assert result.success
    assert result.tool_was_called("get_balance")
    assert not result.tool_was_called("transfer")
    
    account = result.tool_call_arg("get_balance", "account")
    assert account.lower() == "checking"
```

### Testing Multi-Step Workflow

```python
async def test_trip_planning(eval_run, agent):
    result = await eval_run(
        agent,
        "Show me both my checking and savings balances"
    )
    
    assert result.success
    assert result.tool_call_count("get_balance") >= 2 or result.tool_was_called("get_all_balances")
    
    response = result.final_response.lower()
    assert "checking" in response
    assert "savings" in response
```
