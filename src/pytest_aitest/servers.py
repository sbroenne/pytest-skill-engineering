"""Server management for pytest-aitest.

This module provides backwards-compatible imports from the new package structure.
New code should import from pytest_aitest.execution directly.
"""

# Re-export from execution module for backwards compatibility
from pytest_aitest.execution.servers import (
    CLIServerProcess,
    MCPServerProcess,
    ServerManager,
)

__all__ = [
    "CLIServerProcess",
    "MCPServerProcess",
    "ServerManager",
]
