"""Print the saved evidence location alongside ordinary pytest output."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.config import Config
    from _pytest.terminal import TerminalReporter


def log_report_path(config: Config, format_name: str, path: Path) -> None:
    """Print the native evidence path."""
    terminal: TerminalReporter | None = config.pluginmanager.get_plugin("terminalreporter")
    if terminal:
        terminal.write_line(f"aitest {format_name}: {path}")
