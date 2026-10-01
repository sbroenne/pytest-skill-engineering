---
description: "Inspect tool-returned images in Copilot results and saved evidence using structural checks."
---

# Tool-returned images

## Current status

Tool-returned images are captured in results and preserved in native JSON.
Inspect `image_content` (bytes) and `image_media_type` on calls returned by
`result.tool_calls_for(...)`.

The first image remains in those fields. All later images from the same
completion are in `call.additional_images`, as `ImageContent` objects with
`data` and `media_type`. Saved `EvalResult.tool_images_for(name)` returns every
image for that tool, in order. SDK content blocks and binary image results are
captured; malformed image data produces an explicit capture error.

Semantic image judging is not supported. Use ordinary pytest assertions for
image presence and metadata. Your coding agent can inspect the captured images;
the framework does not automatically interpret them.

## What works today

```python
async def test_screenshot_tool_returns_png(copilot_eval, agent):
    result = await copilot_eval(agent, "Capture a screenshot of the chart")

    assert result.success
    screenshots = [
        call for call in result.tool_calls_for("screenshot") if call.image_content is not None
    ]
    assert screenshots
    assert screenshots[-1].image_media_type == "image/png"
    assert screenshots[-1].image_content
```

Use the exact tool name captured in your result; MCP tools may have a server
prefix. Checking media type does not establish that the image shows the
requested chart.

## Inspect a saved image

Native JSON stores image bytes as base64. Loading evidence restores the bytes
without starting Copilot:

```python
from pathlib import Path

from pytest_skill_engineering.reporting import load_suite_report

evidence = load_suite_report("results.json")
result = evidence.tests[0].eval_result
assert result is not None
images = [call for call in result.all_tool_calls if call.image_content is not None]
assert images and images[-1].image_media_type == "image/png"
assert images[-1].image_content is not None
Path("captured.png").write_bytes(images[-1].image_content)
```

Treat captured images as private evidence. Review them before sharing.
