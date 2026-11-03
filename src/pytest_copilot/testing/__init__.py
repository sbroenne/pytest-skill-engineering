"""Test harnesses for pytest-copilot integration testing.

Provides stateful backends and MCP servers for testing agent behavior.

Available Test Servers
----------------------
BankingService
    Banking operations with business rules and error handling. Stateful.

TodoStore
    Task management for CRUD operation tests. Stateful.
"""

from pytest_copilot.testing.banking import BankingService
from pytest_copilot.testing.todo import TodoStore

__all__ = ["BankingService", "TodoStore"]
