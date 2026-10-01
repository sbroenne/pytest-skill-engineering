# Assertions and independent verification

Use ordinary pytest assertions. There are no `llm_assert`, `llm_score`, or
automatic free-text expectation evaluators in version 1.0.

## Separate execution from correctness

```python
assert result.success, result.error
assert result.evidence_complete, result.capture_errors
assert result.tool_was_called("transfer")
calls = result.tool_calls_for("transfer")
assert len(calls) == 1
assert calls[0].arguments["amount"] == 100
```

These establish session and call properties, not a successful business operation.
Verify the resulting store, exact output schema and values, or produced file too.
Check operation errors even if the transport succeeded.

```python
observed = fixture_store.accounts
expected = {"checking": 1400, "savings": 3100}
verified = observed == expected
record_property("verification", {"observed": observed, "expected": expected, "passed": verified})
assert verified
```

Here `fixture_store` is consumer-owned application state, not a built-in fixture.
Record checks before asserting them so failed runs retain the observations.
Properties do not change pytest's verdict by themselves.

## Subjective requirements

Turn requirements into observable checks where possible. If a requirement remains
subjective, let the current coding agent or a human review the saved evidence and
label the conclusion advice. Substring checks can test required wording; they
cannot establish semantic correctness.

## Images

Tool calls expose `image_content` and `image_media_type`; reports preserve
captured images. Check metadata and consumer-owned image measurements. There is
no semantic image judge. See [tool images](../how-to/image-assertions.md).
