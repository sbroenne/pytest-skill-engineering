---
description: "Assertions for CopilotResult objects: structural assertions, semantic assertions, scoring, and current image-assertion limits."
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

- `result.tool_images_for("tool_name")` is supported
- `llm_assert_image` currently raises `NotImplementedError` with the documented Copilot SDK path

Use structural checks on returned images until Copilot SDK image-input support is exposed publicly.
