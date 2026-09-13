---
description: "Assertions for CopilotResult objects: structural assertions, semantic assertions, scoring, and tool-returned images."
---

# Assertions

## Structural assertions

Use normal pytest assertions for deterministic checks:

```python
assert result.success
assert result.tool_was_called("get_balance")
assert result.tool_call_count("transfer") == 1
assert "checking" in (result.final_response or "")
```

## Semantic assertions with `llm_assert`

```python
async def test_balance_response(copilot_eval, llm_assert):
    result = await copilot_eval(agent, "What's my balance?")
    assert llm_assert(result.final_response, "includes the account balance")
```

## Scoring with `llm_score`

Use `llm_score` when you want a rubric score instead of a boolean assertion.

## Images

Inspect images on each tool call with `result.tool_calls_for("tool_name")`
and the call's `image_content` and `image_media_type` fields. Images are also
included in reports.

Use structural checks on image metadata; there is no semantic image-assertion fixture.
See [Tool-returned images](../how-to/image-assertions.md).
