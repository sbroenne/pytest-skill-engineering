"""Test harness for pytest-aitest integration testing.

Provides MCP server implementations for testing agent reasoning capabilities.

Available test servers:
- WeatherStore: Simple weather API for "hello world" tests
- TodoStore: Stateful task management for CRUD tests
- KeyValueStore: Low-level key-value for technical tests (deprecated for examples)
"""

from pytest_aitest.testing.store import KeyValueStore
from pytest_aitest.testing.todo import TodoStore
from pytest_aitest.testing.weather import WeatherStore

__all__ = ["KeyValueStore", "TodoStore", "WeatherStore"]
