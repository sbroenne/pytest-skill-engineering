---
description: "Assert on image content returned by MCP tools. Check if images were returned, inspect their properties, and use AI-powered vision evaluation."
---

# Image Assertions

pytest-aitest supports asserting on images returned by MCP tools. This is useful when your tools produce visual output — screenshots, charts, diagrams, or any image content.

## Overview

There are two approaches to image assertions:

| Approach | Use Case | Fixture |
|----------|----------|---------|
| **Structural** | Check images exist, size, type | `result.tool_images_for()` |
| **AI-Graded** | Vision LLM evaluates image quality | `llm_assert_image` |

## Prerequisites

Your MCP tool must return images as `ImageContentBlock` in the MCP response. PydanticAI converts these to `BinaryContent` objects, which pytest-aitest extracts into `ImageContent` objects.

## Checking If Images Were Returned

Use `result.tool_images_for(tool_name)` to get all images returned by a specific tool:

```python
async def test_screenshot_captured(aitest_run, agent):
    result = await aitest_run(agent, "Take a screenshot of the worksheet")

    # Get all images from the "screenshot" tool
    screenshots = result.tool_images_for("screenshot")

    # At least one screenshot was taken
    assert len(screenshots) > 0

    # Check image properties
    assert screenshots[-1].media_type == "image/png"
    assert len(screenshots[-1].data) > 1000  # Reasonable image size
```

### ImageContent Properties

| Property | Type | Description |
|----------|------|-------------|
| `data` | `bytes` | Raw image bytes |
| `media_type` | `str` | MIME type (e.g., `"image/png"`) |

## AI-Graded Image Evaluation

Use the `llm_assert_image` fixture to have a vision-capable LLM evaluate an image against plain-English criteria:

```python
async def test_dashboard_layout(aitest_run, agent, llm_assert_image):
    result = await aitest_run(agent, "Create a dashboard with 4 charts")

    screenshots = result.tool_images_for("screenshot")
    assert len(screenshots) > 0

    # Vision LLM judges the screenshot
    assert llm_assert_image(
        screenshots[-1],
        "Shows 4 charts arranged without overlapping, each with a descriptive title"
    )
```

### How It Works

`llm_assert_image` uses [`pydantic-evals`](https://ai.pydantic.dev/evals/) `judge_output()` which natively supports multimodal content. The image is sent to a vision-capable model along with your criterion, and the model evaluates whether the criterion is met.

### Accepted Input Types

`llm_assert_image` accepts:

- **`ImageContent`** from `result.tool_images_for()` (recommended)
- **Raw `bytes`** with optional `media_type` parameter (default: `image/png`)

```python
# From tool_images_for (recommended)
screenshots = result.tool_images_for("screenshot")
assert llm_assert_image(screenshots[-1], "shows a bar chart")

# From raw bytes
with open("screenshot.png", "rb") as f:
    assert llm_assert_image(f.read(), "shows a bar chart")

# With custom media type
assert llm_assert_image(jpeg_bytes, "shows a table", media_type="image/jpeg")
```

## Vision Model Configuration

### Command-Line Options

```bash
# GitHub Copilot (no extra setup if pytest-aitest[copilot] installed)
pytest --llm-vision-model=copilot/gpt-4o

# Azure OpenAI
pytest --llm-vision-model=azure/gpt-4o

# Falls back to --llm-model if --llm-vision-model not set
pytest --llm-model=copilot/gpt-4o

# Falls back to --aitest-summary-model if neither set
pytest --aitest-summary-model=copilot/gpt-4o
```

### Model Requirements

The vision model must support image input. Recommended models:

| Provider | Models |
|----------|--------|
| GitHub Copilot | `copilot/gpt-4o`, `copilot/gpt-4o-mini` |
| OpenAI | `gpt-4o`, `gpt-4o-mini` |
| Anthropic | `claude-sonnet-4`, `claude-haiku-4` |
| Azure | `azure/gpt-4o` |
| Google | `gemini-2.0-flash` |

## Writing Effective Image Criteria

### Good Criteria

- ✅ `"Shows 4 charts in a 2x2 grid layout"`
- ✅ `"Contains a bar chart with labeled axes"`
- ✅ `"No elements overlap each other"`
- ✅ `"Has a title at the top of the page"`
- ✅ `"Data table has at least 5 rows of content"`

### Less Effective Criteria

- ❌ `"The chart is blue"` — too specific, may fail on theme changes
- ❌ `"Revenue is $1,234,567"` — exact values are hard to read from images
- ❌ `"Looks professional"` — too subjective, inconsistent results

### Tips

- Focus on **structural** properties (layout, count, presence)
- Avoid **exact values** (hard to OCR reliably)
- Be **specific but flexible** about visual properties
- Combine with text assertions for comprehensive coverage

## Complete Example: A/B Testing with Screenshots

```python
"""A/B test: Does a screenshot tool improve dashboard quality?"""

import pytest
from pytest_aitest import Agent, Provider

CONTROL = Agent(
    name="without-screenshot",
    provider=Provider(model="azure/gpt-4o"),
    mcp_servers=[excel_server],
    allowed_tools=["file", "worksheet", "range", "table", "chart"],
)

EXPERIMENT = Agent(
    name="with-screenshot",
    provider=Provider(model="azure/gpt-4o"),
    mcp_servers=[excel_server],
    allowed_tools=["file", "worksheet", "range", "table", "chart", "screenshot"],
)

@pytest.mark.parametrize("agent", [CONTROL, EXPERIMENT], ids=lambda a: a.name)
async def test_dashboard(aitest_run, agent, llm_assert_image):
    result = await aitest_run(agent, "Create a dashboard with 4 charts")
    assert result.success

    # Both variants should create charts
    assert result.tool_was_called("chart")

    # Experiment variant: verify visual quality
    if agent.name == "with-screenshot":
        screenshots = result.tool_images_for("screenshot")
        if screenshots:
            assert llm_assert_image(
                screenshots[-1],
                "Shows 4 charts with no overlapping elements"
            )
```

## HTML Reports

When tools return images, the HTML report shows inline thumbnails next to the tool call. This makes it easy to visually compare results across agents.

## Cost Awareness

Vision model calls are more expensive than text-only calls. A single `llm_assert_image` call with a screenshot typically costs:

- **GPT-4o**: ~$0.01-0.03 per image
- **Claude Sonnet**: ~$0.01-0.02 per image
- **GPT-4o-mini**: ~$0.001-0.005 per image

Use `--llm-vision-model` to select a cost-appropriate model for your CI budget.
