"""Common types for test harnesses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    """Result from a tool call.

    All test harness methods return this type for consistent handling.

    Attributes:
        success: Whether the operation succeeded
        value: The result value (if successful)
        error: Error message (if failed)
    """

    success: bool
    value: Any = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "value": self.value,
            "error": self.error,
        }
