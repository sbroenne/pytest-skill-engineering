# AgentResult

Validate agent behavior using `AgentResult` properties and methods.

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

## Tool Assertions

### tool_was_called

Check if a tool was invoked:

```python
# Basic check - was it called at all?
assert result.tool_was_called("get_weather")

# Check specific call count
assert result.tool_call_count("get_weather") == 2
```

### tool_call_count

Get number of tool invocations:

```python
count = result.tool_call_count("get_weather")
assert count >= 1
assert count <= 5
```

### tool_call_arg

Get an argument from the first call to a tool:

```python
# Get argument from first call
city = result.tool_call_arg("get_weather", "city")
assert city == "Paris"

# For multiple calls, use tool_calls_for and index manually
calls = result.tool_calls_for("get_weather")
if len(calls) > 1:
    second_city = calls[1].arguments.get("city")
```

### tool_calls_for

Get all calls to a specific tool:

```python
calls = result.tool_calls_for("get_weather")

for call in calls:
    print(f"Called with: {call.arguments}")
    print(f"Result: {call.result}")
```

## Output Assertions

### Check Response Content

```python
# Case-insensitive content check
assert "paris" in result.final_response.lower()

# Multiple conditions
response = result.final_response.lower()
assert "weather" in response
assert "sunny" in response or "cloudy" in response
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
assert result.success, f"Agent failed: {result.error}"
```

### Inspect Errors

```python
if not result.success:
    print(f"Error: {result.error}")
    
    # Check last turn for details
    last_turn = result.turns[-1]
    print(f"Last message: {last_turn.content}")
```

## AI-Powered Assertions (Optional)

For semantic validation, use [pytest-llm-assert](https://github.com/sbroenne/pytest-llm-assert):

```bash
uv add pytest-llm-assert
```

```python
async def test_response_quality(aitest_run, agent, llm_assert):
    """Use the llm_assert fixture for semantic validation."""
    result = await aitest_run(agent, "What's the weather in Paris?")
    
    assert result.success
    assert llm_assert(result.final_response, "mentions weather conditions")
```

## Complete Examples

### Testing Tool Selection

```python
async def test_correct_tool_selection(aitest_run, agent):
    result = await aitest_run(agent, "What's the weather in Paris?")
    
    assert result.success
    assert result.tool_was_called("get_weather")
    assert not result.tool_was_called("get_forecast")
    
    city = result.tool_call_arg("get_weather", "city")
    assert city.lower() == "paris"
```

### Testing Multi-Step Workflow

```python
async def test_trip_planning(aitest_run, agent):
    result = await aitest_run(
        agent,
        "Compare weather in Paris and Sydney"
    )
    
    assert result.success
    assert result.tool_call_count("get_weather") >= 2
    
    response = result.final_response.lower()
    assert "paris" in response
    assert "sydney" in response
```
