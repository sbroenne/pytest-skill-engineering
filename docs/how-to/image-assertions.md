---
description: "Check tool-returned image bytes and metadata, then extract images from saved evidence."
---

# Tool-returned images

Use ordinary pytest assertions to verify that a tool returned an image with
the expected bytes or format. Capturing a screenshot does not establish that
the application or chart shown in it is correct.

## Current status

The first image from a tool completion is stored in `call.image_content`
(bytes) and `call.image_media_type`. Later images are in
`call.additional_images` as `ImageContent` objects with `data` and `media_type`.
The framework captures SDK content blocks and binary image results; malformed
image data produces a capture error.

Native JSON preserves the images. Its loaded `EvalResult.tool_images_for(name)`
returns every image for that tool in order. There is no automatic semantic
image verdict; define your own structural checks or independent application
checks.

## What works today

This **illustrative test** requires your `screenshot_eval` fixture, configured
with a screenshot tool and a known application state:

```python
async def test_screenshot_returns_png(copilot_eval, screenshot_eval):
    result = await copilot_eval(screenshot_eval, "Capture a screenshot of the chart.")

    assert result.success, result.error
    assert result.evidence_complete, result.capture_errors
    calls = result.tool_calls_for("screenshot")
    assert calls
    call = calls[-1]
    assert call.success is True and call.evidence_complete
    assert call.image_media_type == "image/png"
    assert call.image_content is not None
    assert call.image_content.startswith(b"\x89PNG\r\n\x1a\n")
```

Use your actual runtime tool name, including an MCP prefix when present.
These assertions check capture, declared media type, and a PNG signature.
They do not fully decode the image or verify its contents. Use your own
decoder or fixture-state checks when the task requires those guarantees.

## Inspect a saved image

Native schema-4.0 JSON stores image bytes as base64. Loading it restores bytes
without starting Copilot:

```python
from pathlib import Path

from pytest_skill_engineering.reporting import load_suite_report

evidence = load_suite_report("results.json")
result = evidence.tests[0].eval_result
assert result is not None
images = result.tool_images_for("screenshot")
assert images
assert images[0].media_type == "image/png"
Path("captured.png").write_bytes(images[0].data)
```

Select the relevant case and tool name in your own report; this example assumes
the first captured test is the screenshot task. The helper includes additional
images, not just the first image from each call.

Captured screenshots may contain private application data. Review them before
sharing. See [Inspect execution evidence](inspect-evidence.md) for the rest of
the saved trace and verification properties.
