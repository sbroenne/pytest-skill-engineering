# Assertions

Validate agent behavior using `AgentResult` methods and the AI judge.

## AgentResult Properties

| Property | Type | Description |
|----------|------|-------------|
| `success` | `bool` | Did the agent complete without errors? |
| `final_response` | `str` | The agent's final text response |
| `turns` | `list[Turn]` | All execution turns |
| `duration_ms` | `int` | Total execution time |
| `token_usage` | `TokenUsage` | Prompt/completion/total tokens |
| `cost_usd` | `float` | Estimated cost in USD |
| `error` | `str \| None` | Error message if failed |

## Tool Assertions

### tool_was_called

Check if a tool was invoked:

```python
# Basic check
assert result.tool_was_called("get_weather")

# Check exact call count
assert result.tool_was_called("get_weather", times=2)
```

### tool_call_count

Get number of tool invocations:

```python
count = result.tool_call_count("get_weather")
assert count >= 1
assert count <= 5
```

### tool_call_arg

Get an argument from a tool call:

```python
# Get argument from first call
city = result.tool_call_arg("get_weather", "city")
assert city == "Paris"

# Get argument from specific call (0-indexed)
second_city = result.tool_call_arg("get_weather", "city", call_index=1)
assert second_city == "London"
```

### get_tool_calls

Get all calls to a specific tool:

```python
calls = result.get_tool_calls("get_weather")

for call in calls:
    print(f"Called with: {call.arguments}")
    print(f"Result: {call.result}")
    print(f"Duration: {call.duration_ms}ms")
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

## AI Judge

Use LLM-based evaluation for semantic assertions. Requires [pytest-llm-assert](https://github.com/sbroenne/pytest-llm-assert).

### Basic Usage

```python
@pytest.mark.asyncio
async def test_with_judge(aitest_run, agent, judge):
    result = await aitest_run(agent, "What's the weather in Paris?")
    
    assert result.success
    assert judge(result.final_response, "mentions the weather in Paris")
```

### Multi-Criteria Evaluation

```python
@pytest.mark.asyncio
async def test_recommendation(aitest_run, agent, judge):
    result = await aitest_run(
        agent, 
        "Compare weather in Paris and London for a trip"
    )
    
    assert result.success
    assert judge(result.final_response, """
        - Mentions weather for both Paris and London
        - Makes a recommendation for one city
        - Provides reasoning based on weather data
    """)
```

### Combining with Tool Assertions

```python
@pytest.mark.asyncio
async def test_complete_workflow(aitest_run, agent, judge):
    result = await aitest_run(agent, "Get 3-day forecast for Paris")
    
    # Check tool was used correctly
    assert result.success
    assert result.tool_was_called("get_forecast")
    
    # Check response quality
    assert judge(result.final_response, """
        - Shows forecast for 3 days
        - Includes temperature information
        - Mentions Paris specifically
    """)
```

## Performance Assertions

### Execution Time

```python
# Check total execution time
assert result.duration_ms < 30000  # Under 30 seconds
```

### Token Usage

```python
# Check token consumption
assert result.token_usage.total_tokens < 5000

# Detailed breakdown
print(f"Prompt tokens: {result.token_usage.prompt_tokens}")
print(f"Completion tokens: {result.token_usage.completion_tokens}")
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

## Complete Examples

### Testing Tool Selection

```python
@pytest.mark.asyncio
async def test_correct_tool_selection(aitest_run, agent):
    result = await aitest_run(agent, "What's the weather in Paris?")
    
    assert result.success
    assert result.tool_was_called("get_weather")
    assert not result.tool_was_called("get_forecast")  # Shouldn't use forecast
    
    # Check correct argument
    city = result.tool_call_arg("get_weather", "city")
    assert city.lower() == "paris"
```

### Testing Multi-Step Workflow

```python
@pytest.mark.asyncio
async def test_trip_planning(aitest_run, agent):
    result = await aitest_run(
        agent,
        "Compare weather in Paris and Sydney for my trip"
    )
    
    assert result.success
    
    # Should call weather for both cities
    assert result.tool_call_count("get_weather") >= 2
    
    # Check both cities mentioned
    response = result.final_response.lower()
    assert "paris" in response
    assert "sydney" in response
```

### Testing Error Recovery

```python
@pytest.mark.asyncio
async def test_handles_invalid_city(aitest_run, agent):
    result = await aitest_run(agent, "Weather in Atlantis")
    
    # Agent should complete even if tool returns error
    assert result.success
    
    # Should mention the city doesn't exist or isn't found
    response = result.final_response.lower()
    assert "not found" in response or "doesn't exist" in response
```

## Types Reference

### Turn

A single turn in the agent execution:

| Property | Type | Description |
|----------|------|-------------|
| `role` | `str` | "user", "assistant", or "tool" |
| `content` | `str` | Message content |
| `tool_calls` | `list[ToolCall]` | Tool calls made (if any) |
| `token_usage` | `TokenUsage` | Tokens for this turn |

### ToolCall

A single tool invocation:

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | Tool name |
| `arguments` | `dict` | Arguments passed |
| `result` | `str` | Tool response |
| `duration_ms` | `int` | Execution time |

### TokenUsage

Token consumption metrics:

| Property | Type | Description |
|----------|------|-------------|
| `prompt_tokens` | `int` | Tokens in prompts |
| `completion_tokens` | `int` | Tokens in completions |
| `total_tokens` | `int` | Total tokens used |
