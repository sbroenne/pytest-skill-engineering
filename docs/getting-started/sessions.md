# Multi-step tasks and explicit context

Every `copilot_eval` call starts a new Copilot session. The fixture does not
retain conversation history across calls or pytest tests. Use one prompt for a
task requiring several steps.

The following fragment assumes `agent` has your banking tools and an initialized
test account:

```python
result = await copilot_eval(
    agent,
    "Transfer $100 from checking to savings, then retrieve the updated balances.",
)
assert result.success, result.error
assert result.tool_was_called("banking-transfer")
```

The tool check establishes only that a call was observed. Also check completed
calls, exact arguments, operation errors, and final account values through your
application fixture. Assert call order only when it is part of the requirement.

## Do not confuse descriptions with persisted state

An earlier task can change files or external state, but it does not give the next
call conversation history. Likewise, writing "a previous transfer occurred" in
the prompt does not initialize a fixture database.

For independent tests, initialize required state in each application fixture.
For context-dependent behavior, include the required context explicitly in the
task and verify its output. That tests use of supplied context, not retention
of a prior conversation.

## Compare and repeat

[Parametrization and `ab_run`](comparing.md) execute independent configurations.
[Repetitions](iterations.md) recreate function-scoped fixtures, not shared
services or desktops. Own any external-state reset.

The repository's
[`test_06_sessions.py`](https://github.com/sbroenne/pytest-skill-engineering/blob/main/tests/integration/copilot/test_06_sessions.py)
shows explicit-context and multi-step tasks.
