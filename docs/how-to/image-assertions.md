---
description: "Inspect tool-returned images in Copilot results and reports using structural assertions."
---

# Tool-returned images

## Current status

Tool-returned images are captured in results and surfaced in reports.
Inspect `image_content` (bytes) and `image_media_type` on calls returned by
`result.tool_calls_for(...)`.

Semantic image judging is not supported. Use ordinary pytest assertions for
image presence and metadata, and inspect the captured images in the report.

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
