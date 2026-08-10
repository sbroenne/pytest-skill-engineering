---
description: "Current state of image assertions with Copilot: tool images are captured, but llm_assert_image is not yet available through the documented SDK path."
---

# Image assertions

## Current status

Tool-returned images are captured in results and surfaced in reports.
You can inspect them with `result.tool_images_for(...)`.

`llm_assert_image` exists as a fixture entry point, but it currently raises `NotImplementedError` because the documented Copilot SDK flow does not yet expose image inputs for semantic judging.

## What works today

```python
async def test_screenshot_tool_returns_png(copilot_eval, agent):
    result = await copilot_eval(agent, "Capture a screenshot of the chart")

    screenshots = result.tool_images_for("screenshot")
    assert screenshots
    assert screenshots[-1].media_type == "image/png"
```

## What to avoid documenting as supported

Do not document `llm_assert_image(...)` as a working semantic-vision assertion until Copilot SDK image input support is available through the public runtime.
