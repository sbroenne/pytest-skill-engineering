---
description: "Validate HTML report rendering with Playwright browser automation. Ensure report components render correctly across scenarios."
---

# Visual Testing with Playwright

Validate HTML report rendering and UI interactions using Playwright browser automation.

## Overview

pytest-skill-engineering includes a comprehensive visual test suite that verifies:

- **Report Rendering** — Headers, metrics, sections display correctly
- **UI Interactions** — Expand/collapse, filters, agent selector toggling
- **Eval Comparison** — Multi-column layouts for comparing agents
- **Mermaid Diagrams** — Tool usage flow diagrams render and open
- **Session Grouping** — Multi-turn sessions display with proper styling

Visual tests are located in `tests/visual/` and use Pytest with Playwright.

## Running Visual Tests

```bash
# Run all visual tests
pytest tests/visual/ -v

# Run specific test file
pytest tests/visual/test_01_single_agent.py -v

# Run quick check (quiet mode)
pytest tests/visual/ -q
```

## Visual Test Files

| File | Tests | Coverage |
|------|-------|----------|
| `test_01_single_agent.py` | 10 | Single agent (no leaderboard, no selector) |
| `test_02_multi_agent.py` | 15 | 2 agents (leaderboard, comparison columns) |
| `test_03_sessions.py` | 12 | Multi-turn sessions with 2 agents |
| `test_04_agent_selector.py` | 13 | 3 agents (selector UI, toggling) |

Total: 44 visual tests covering all report configurations.

## Test Structure

Each visual test file has test classes organized by feature:

```python
class TestSingleAgentHeader:
    def test_header_exists(self, page, single_agent_report):
        """Header section should exist."""
        
class TestSingleAgentAIAnalysis:
    def test_ai_analysis_exists(self, page, single_agent_report):
        """AI analysis section should exist."""
        
class TestSingleAgentTestGrid:
    def test_test_rows_exist(self, page, single_agent_report):
        """Test rows should exist."""
```

## Common Patterns

### Waiting for Elements

```python
# Wait for page to load
page.wait_for_load_state("networkidle")

# Wait for element to be visible
assert element.is_visible()

# Wait with timeout
page.wait_for_timeout(300)
```

### Expanding Test Details

```python
# Find and click test header to expand
header = page.locator(".test-row .px-5.py-3").first
header.click()
page.wait_for_timeout(300)

# Verify detail is now visible
visible_details = page.locator(".test-row:first-child .test-detail:not(.hidden)")
assert visible_details.count() > 0
```

### Counting UI Elements

```python
# Count all elements matching selector
rows = page.locator(".leaderboard-table tbody tr")
assert rows.count() == 2  # Exactly 2 agent rows

# Count visible (not hidden) elements
visible = page.locator(".comparison-column:not(.hidden)")
assert visible.count() == 2
```

### Eval Selector Testing

```python
# Check default selection (first 2 agents)
checked = page.locator('input[name="compare-agent"]:checked')
assert checked.count() == 2

# Check selected chip styling
first_chip = page.locator(".agent-chip").nth(0)
classes = first_chip.get_attribute("class") or ""
assert "selected" in classes
```

### Mermaid Diagram Interaction

```python
# Expand test to show diagram
header.click()
page.wait_for_timeout(500)

# Find and click mermaid container (has onclick handler)
mermaid = page.locator(".test-row:first-child .test-detail [data-mermaid-code]").first
if mermaid.count() > 0:
    mermaid.click()
    page.wait_for_timeout(500)

# Verify overlay opened
overlay = page.locator("#overlay")
is_active = overlay.evaluate("el => el.classList.contains('active')")
assert is_active
```

## Test Fixtures

Visual tests use report fixtures defined in `tests/visual/conftest.py`:

```python
@pytest.fixture(scope="module")
def single_agent_report() -> Path:
    """HTML report from 01_single_agent.json (1 agent, no comparison UI)."""
    return _ensure_html_report("01_single_agent")

@pytest.fixture(scope="module")
def multi_agent_report() -> Path:
    """HTML report from 02_multi_agent.json (2 agents, leaderboard, no selector)."""
    return _ensure_html_report("02_multi_agent")
```

Each fixture auto-generates from JSON if the HTML doesn't exist.

## Configuration

Visual tests configure pytest-asyncio in strict mode (manual, not auto):

```python
# tests/visual/conftest.py
def pytest_configure(config: pytest.Config) -> None:
    """Disable asyncio for visual tests."""
    config._inicache["asyncio_mode"] = "strict"

# Override async cleanup fixture
@pytest.fixture(autouse=True)
def _aitest_auto_cleanup() -> None:
    """No-op override of async cleanup fixture for sync Playwright tests."""
    pass
```

This prevents conflicts with pytest-asyncio since Playwright tests are synchronous.

## Best Practices

### Do ✅

- Always use `page.wait_for_load_state("networkidle")` before assertions
- Click element headers before checking expanded state
- Wait 200-300ms after clicks for DOM updates
- Use `:not(.hidden)` to check visibility (Tailwind pattern)
- Test within first element when checking single instances: `.test-row:first-child`

### Don't ❌

- Don't assume elements exist without clicking/expanding first
- Don't test without waiting for page load
- Don't use hardcoded sleep without context comment
- Don't check `display: none` style directly (Tailwind uses classes)
- Don't test all agents — scope to first for performance

## Expected Results

All 44 visual tests should pass:

```
tests/visual/test_01_single_agent.py::TestSingleAgentHeader::test_header_exists PASSED
tests/visual/test_01_single_agent.py::TestSingleAgentHeader::test_suite_title_from_docstring PASSED
...
44 passed in 124.35s
```

If a test fails:
1. Check the selector (element IDs/classes may have changed)
2. Verify the page actually loaded (`page.wait_for_load_state("networkidle")`)
3. Run single test with `-vv` for more detail
4. Take a screenshot: `page.screenshot(path="debug.png")`

## Debugging Tips

```python
# Take screenshot of current state
page.screenshot(path="screenshot.png")

# Print page HTML
print(page.content())

# Query element properties
button = page.locator(".filter-btn").first
print(f"Classes: {button.get_attribute('class')}")
print(f"Text: {button.text_content()}")

# List all matching elements
elements = page.locator(".agent-chip")
for i in range(elements.count()):
    print(f"Chip {i}: {elements.nth(i).text_content()}")
```

## Adding New Visual Tests

When adding new report features:

1. Create test class in appropriate file (01/02/03/04)
2. Use existing fixtures (`page` and report fixture)
3. Follow naming pattern: `test_something_behavior`
4. Add docstring explaining what's tested
5. Use existing selector patterns (`.test-row`, `.agent-chip`, etc.)
6. Add waiting where needed (DOM updates are async)
7. Run `pytest tests/visual/ -q` to verify

Example:

```python
class TestNewFeature:
    def test_feature_renders(self, page, multi_agent_report):
        """New feature should be visible."""
        page.goto(f"file://{multi_agent_report}")
        page.wait_for_load_state("networkidle")
        
        feature = page.locator(".new-feature-class")
        assert feature.count() > 0
        assert feature.is_visible()
```
