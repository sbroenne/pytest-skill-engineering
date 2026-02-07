"""Fixtures conftest - Azure auth configuration for llm_assert."""

# Re-export pytest_configure so llm_assert uses Azure instead of OpenAI
from tests.integration.conftest import pytest_configure  # noqa: F401
