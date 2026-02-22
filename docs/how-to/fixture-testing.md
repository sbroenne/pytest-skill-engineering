---
description: "Use pre-built fixture test suites with semantic, tool, and performance assertions to validate AI agent behavior systematically."
---

# Fixture Testing with Comprehensive Assertions

Test your AI agents using pre-built fixture test suites with semantic, tool, and performance assertions.

## Overview

Fixture tests demonstrate best practices for comprehensive AI agent validation. Each scenario is a separate file in `tests/fixtures/`:

| File | Agents | Purpose |
|------|--------|---------|
| `scenario_01_single_agent.py` | 1 | Basic report, no comparison UI |
| `scenario_02_multi_agent.py` | 2 | Leaderboard, comparison |
| `scenario_03_sessions.py` | 2 | Session grouping + comparison |
| `scenario_04_agent_selector.py` | 3 | Eval selector UI |

They demonstrate:

- **Semantic Assertions** — AI validates response quality
- **Tool Argument Assertions** — Verify correct parameters passed
- **Tool Count Assertions** — Check single vs. multiple tool calls
- **Performance Assertions** — Validate cost and duration
- **Multi-Eval Comparison** — Compare models and skills
- **Session Testing** — Multi-turn context preservation

## Running Fixture Tests

```bash
# Run a specific scenario
pytest tests/fixtures/scenario_01_single_agent.py -v

# Run a single test
pytest tests/fixtures/scenario_01_single_agent.py::test_balance_check -v

# Generate fixture JSON report
pytest tests/fixtures/scenario_01_single_agent.py -v \
    --aitest-json=tests/fixtures/reports/01_single_agent.json

# Run all fixtures
pytest tests/fixtures/ -v
```

## Test Suites

### 1. Single Eval (4 tests)

`scenario_01_single_agent.py` — one agent, multiple prompts:

```python
agent = Eval.from_instructions(
    "banking-agent",
    BANKING_PROMPT,
    provider=Provider(model="azure/gpt-5-mini", rpm=10, tpm=10000),
    mcp_servers=[banking_server],
)

async def test_balance_check(eval_run, llm_assert):
    result = await eval_run(agent, "What's my checking account balance?")
    assert result.success
    assert result.tool_was_called("get_balance")
    assert llm_assert(result.final_response, "mentions the account balance")
    assert result.cost_usd < 0.05
```

**Tests:** `test_balance_check`, `test_transfer_funds`, `test_transaction_history`, `test_expected_failure`

### 2. Two Agents (6 tests)

`scenario_02_multi_agent.py` — define agents once, parametrize tests:

```python
AGENTS = [
    Eval(name="gpt-5-mini", provider=Provider(model="azure/gpt-5-mini"), ...),
    Eval(name="gpt-4.1-mini", provider=Provider(model="azure/gpt-4.1-mini"), ...),
]

@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_balance_check(eval_run, agent, llm_assert):
    result = await eval_run(agent, "What's my checking account balance?")
    assert result.success
```

Each test runs on both models — AI analysis auto-generates leaderboard.

### 3. Sessions (6 tests)

`scenario_03_sessions.py` — multi-turn conversation with context:

```python
@pytest.mark.session("banking-workflow")
class TestBankingWorkflow:
    @pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
    async def test_check_balance(self, eval_run, agent, llm_assert):
        result = await eval_run(agent, "What's my checking account balance?")
        assert result.success
        assert result.tool_was_called("get_balance")

    @pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
    async def test_transfer_funds(self, eval_run, agent, llm_assert):
        result = await eval_run(agent, "Transfer $100 from checking to savings")
        assert result.is_session_continuation
```

The `@pytest.mark.session` marker ensures tests share agent state.

### 4. Eval Selector (6 tests)

`scenario_04_agent_selector.py` — three agents for selector UI:

```python
AGENTS = [
    Eval(name="gpt-5-mini", ...),
    Eval(name="gpt-4.1-mini", ...),
    Eval(name="gpt-5-mini+skill", ..., skill=FINANCIAL_SKILL),
]

@pytest.mark.parametrize("agent", AGENTS, ids=lambda a: a.name)
async def test_balance_query(eval_run, agent, llm_assert):
    result = await eval_run(agent, "What's my checking account balance?")
    assert result.success
```

With 3+ agents, the report includes an interactive agent selector.

## Assertion Patterns

### Semantic Assertions (LLM-Based)

Validate response quality using AI judgment:

```python
# llm_assert is a pytest fixture — just add it to your test function signature
# Does response mention expected content?
assert llm_assert(result.final_response, "mentions account balance with dollar amount")

# Complex criteria
assert llm_assert(
    result.final_response,
    "lists both checking and savings account balances"
)
```

### Tool Call Assertions

Verify the agent used the right tools:

```python
# Simple: was tool called at all?
assert result.tool_was_called("get_balance")

# Count: how many times?
assert result.tool_call_count("get_balance") >= 2

# Arguments: what parameters were passed?
account = result.tool_call_arg("get_balance", "account")
assert account.lower() == "checking"

# Multiple calls: get all invocations
calls = result.tool_calls_for("transfer")
assert len(calls) >= 1
assert calls[0].arguments["amount"] == 100
```

### Performance Assertions

Validate efficiency:

```python
# Cost (in USD)
assert result.cost_usd < 0.01  # Under 1 cent

# Duration (in milliseconds)
assert result.duration_ms < 30000  # Under 30 seconds

# Token usage
total_tokens = (result.token_usage.get("prompt", 0) + 
                result.token_usage.get("completion", 0))
assert total_tokens < 5000
```

## Generated Reports

Running fixture tests generates JSON and HTML reports:

```bash
pytest tests/fixtures/scenario_01_single_agent.py -v \
    --aitest-json=tests/fixtures/reports/01_single_agent.json \
    --aitest-html=docs/reports/01_single_agent.html

# Output:
# aitest JSON report: tests\fixtures\reports\01_single_agent.json
# aitest HTML report: docs\reports\01_single_agent.html
```

Reports include:

- **AI Analysis** — LLM-generated insights on performance
- **Test Results** — All assertions with pass/fail details
- **Tool Feedback** — Suggestions for improving tool descriptions
- **Tool Call Flows** — Mermaid diagrams showing sequence
- **Leaderboard** — Compare agents if multiple models tested

## Running Comprehensive Test Suite

Generate reports for all 4 fixture suites:

```bash
# Generate each fixture individually
pytest tests/fixtures/scenario_01_single_agent.py -v \
    --aitest-json=tests/fixtures/reports/01_single_agent.json
pytest tests/fixtures/scenario_02_multi_agent.py -v \
    --aitest-json=tests/fixtures/reports/02_multi_agent.json
pytest tests/fixtures/scenario_03_sessions.py -v \
    --aitest-json=tests/fixtures/reports/03_multi_agent_sessions.json
pytest tests/fixtures/scenario_04_agent_selector.py -v \
    --aitest-json=tests/fixtures/reports/04_agent_selector.json
```

Then regenerate HTML from all JSONs:

```bash
python scripts/generate_fixture_html.py
```

This updates HTML reports in `docs/reports/` without re-running tests (faster).

## Assertion Workflow

When writing fixture tests, follow this pattern:

1. **Create agent** — Configure provider, servers, system prompt, skill
2. **Run prompt** — Use `eval_run(agent, "user message")`
3. **Validate success** — `assert result.success`
4. **Assert tool usage** — `assert result.tool_was_called(...)`
5. **Check arguments** — `assert result.tool_call_arg(...) == expected`
6. **Semantic validation** — `assert llm_assert(response, "criterion")`
7. **Performance validation** — `assert result.cost_usd < threshold`

Example:

```python
async def test_transfer_workflow(self, eval_run, banking_server, llm_assert):
    agent = Eval(...)
    
    result = await eval_run(
        agent,
        "Check my checking balance, then transfer $100 to savings."
    )
    
    # Validate execution
    assert result.success, f"Eval failed: {result.error}"
    
    # Validate tools used
    assert result.tool_was_called("transfer")
    amount = result.tool_call_arg("transfer", "amount")
    assert amount == 100, f"Expected $100, got {amount}"
    
    # Validate response quality
    assert llm_assert(result.final_response, "confirms transfer of $100 to savings")
    
    # Validate efficiency
    assert result.cost_usd < 0.05, f"Cost too high: ${result.cost_usd}"
    assert result.duration_ms < 30000, f"Took too long: {result.duration_ms}ms"
```

## Debugging Failed Tests

If a fixture test fails:

1. **Check the error message** — AI assertion detail explains why
2. **Run the test locally** — `pytest tests/fixtures/... -vv`
3. **Check JSON report** — `tests/fixtures/reports/01_*.json` has full details
4. **Verify agent config** — Is the right server/model/prompt used?
5. **Check tool availability** — Does `result.available_tools` include what you need?

### Common Issues

**"Tool not found"**
```python
# Check available tools
print(f"Available: {[t.name for t in result.available_tools]}")

# Ensure MCP server is running
assert len(result.available_tools) > 0
```

**"Wrong parameter passed"**
```python
# Get all calls to debug
calls = result.tool_calls_for("get_balance")
for i, call in enumerate(calls):
    print(f"Call {i}: {call.arguments}")
```

**"Response doesn't match criterion"**
```python
# Print what the LLM actually said
print(f"Response:\n{result.final_response}")

# Check if criterion is too strict
assert llm_assert(result.final_response, "mentions balance")  # Too vague
assert llm_assert(result.final_response, "exact phrase")      # Too narrow
```

## Best Practices

### Do ✅
- Use semantic assertions for subjective quality checks
- Use tool assertions for behavioral verification
- Use performance assertions for efficiency checks
- Combine assertion types for comprehensive validation
- Document what each assertion validates with comments

### Don't ❌
- Don't rely only on `result.success` (it's too broad)
- Don't hardcode exact prices for cost assertions (use thresholds)
- Don't expect specific tool call counts without testing multiple times
- Don't use semantic assertions for tool-related checks (use `tool_was_called`)
- Don't assume tool arguments — always verify with `tool_call_arg`
