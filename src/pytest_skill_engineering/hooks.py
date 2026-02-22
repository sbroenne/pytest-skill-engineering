"""pytest-skill-engineering hook specifications.

Downstream plugins can implement these hooks to customize behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.config import Config


class AitestHookSpec:
    """Hook specifications for pytest-skill-engineering extensibility."""

    @pytest.hookspec(firstresult=True)
    def pytest_skill_engineering_analysis_prompt(self, config: Config) -> str | None:
        """Return a custom analysis prompt for AI insights generation.

        Called when generating AI insights for reports. The first plugin
        that returns a non-None string wins (``firstresult=True``).

        Args:
            config: The pytest config object.

        Returns:
            Custom prompt text as a string, or None to use the default prompt.

        Example::

            # In your plugin's plugin.py
            import pytest

            @pytest.hookimpl
            def pytest_skill_engineering_analysis_prompt(config):
                return (Path(__file__).parent / "prompts" / "my_prompt.md").read_text()
        """
