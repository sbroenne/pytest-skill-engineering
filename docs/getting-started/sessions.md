# Multi-step tasks and explicit context

Every `copilot_eval` call creates a new Copilot session. The public fixture does
not reuse conversation history between calls or between pytest tests.

For a workflow, place the required context and actions in one task:

```python
result = await copilot_eval(
    agent,
    "Transfer $100 from checking to savings, then retrieve the updated balances.",
)
assert result.success, result.error
assert result.tool_was_called("banking-transfer")
```

Here `agent` is your configured banking eval. Also verify exact arguments,
returned operation data, call order when required, and final account values.
Tool presence alone does not establish a correct transfer.

## Do not confuse descriptions with persisted state

Writing "a previous transfer occurred" in a new prompt does not change a fresh
fixture database. If a follow-up test requires changed account state, initialize
that state explicitly in its own application fixture.

Sharing a test class or recording two runs does not create a shared conversation
or prove history retention. For context-dependent behavior,
declare the necessary context in the task and check its actual output.

## Compare and repeat

Parametrize independent eval configurations or use `ab_run` with fixed checks.
Each repetition recreates function-scoped fixtures; session-scoped external
state is not automatically reset.

See [comparisons](comparing.md), [iterations](iterations.md), and the real
[`test_06_sessions.py`](https://github.com/sbroenne/pytest-skill-engineering/blob/main/tests/integration/copilot/test_06_sessions.py)
examples.
