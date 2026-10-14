# Assertions and independent verification

Your assertions decide whether a task passed. Check the actual output, not just
the session's completion or the model's response.

## Check the requested result

For a state-changing tool, inspect the resulting application state:

```python
observed = fixture_store.accounts
expected = {"checking": 1400, "savings": 3100}
verified = observed == expected
record_property(
    "verification",
    {"observed": observed, "expected": expected, "passed": verified},
)
assert verified
```

This fragment belongs after execution in an async test. `fixture_store` is
your application's test fixture, not a framework fixture.

For a file-writing task, check the file's existence and contents. For a returned
operation, check its documented schema, values, and application-level errors.
Transport success alone is insufficient.

## Check execution evidence separately

```python
assert result.success, result.error
assert result.evidence_complete, result.capture_errors
assert result.tool_was_called("transfer")
calls = result.tool_calls_for("transfer")
assert len(calls) == 1
assert calls[0].arguments["amount"] == 100
```

These assertions establish session and call properties, not a successful
transfer. Add them when those properties are part of the test's requirement,
alongside the application check.

## Save useful observations

`record_property` is a pytest fixture. The framework saves JSON-compatible
properties with captured executions.
Record checks before asserting them so failed runs retain the observations.
Properties do not change pytest's verdict by themselves.

For an A/B test, record each side's verification separately before asserting the
combined result. Both saved executions share the test's one pytest outcome.

## Subjective requirements

Turn requirements into observable checks where possible. If a requirement remains
subjective, let the current coding agent or a human review the saved evidence and
label the conclusion advice. Substring checks can test required wording; they
cannot establish semantic correctness. The framework has no automatic
free-text expectation evaluator or AI judge.

## Images

Tool calls expose `image_content` and `image_media_type`; reports preserve
captured images. Check metadata and consumer-owned image measurements. There is
no semantic image judge. See [tool images](../how-to/image-assertions.md).
