"""pytest-aitest: Pytest plugin for testing AI agents with MCP and CLI servers."""

import logging

# Configure library logging per Python best practices:
# https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library
# Libraries should add NullHandler to prevent "No handler found" warnings
# when the application hasn't configured logging.
logging.getLogger(__name__).addHandler(logging.NullHandler())

# Core types  # noqa: E402 - logging must be configured before submodule imports
from pytest_aitest.core import (  # noqa: E402
    Agent,
    AgentResult,
    AITestError,
    ClarificationDetection,
    ClarificationLevel,
    ClarificationStats,
    CLIExecution,
    CLIServer,
    EngineTimeoutError,
    ImageContent,
    MCPServer,
    Prompt,
    Provider,
    ServerStartError,
    Skill,
    SkillError,
    SkillInfo,
    SkillMetadata,
    ToolCall,
    ToolInfo,
    Turn,
    Wait,
    load_prompt,
    load_prompts,
    load_skill,
    load_system_prompts,
)

# Execution
from pytest_aitest.execution import AgentEngine  # noqa: E402

# Scoring
from pytest_aitest.fixtures.llm_score import (  # noqa: E402
    ScoreResult,
    ScoringDimension,
    assert_score,
)

# Hooks (for plugin extensibility)
from pytest_aitest.hooks import AitestHookSpec  # noqa: E402
from pytest_aitest.plugin import get_analysis_prompt, get_analysis_prompt_details  # noqa: E402

# Reporting
from pytest_aitest.reporting import (  # noqa: E402
    SuiteReport,
    TestReport,
    build_suite_report,
    generate_html,
    generate_json,
)

__all__ = [  # noqa: RUF022
    # Core
    "Agent",
    "AgentResult",
    "AITestError",
    "CLIExecution",
    "CLIServer",
    "ClarificationDetection",
    "ClarificationLevel",
    "ClarificationStats",
    "EngineTimeoutError",
    "ImageContent",
    "MCPServer",
    "Prompt",
    "Provider",
    "ServerStartError",
    "Skill",
    "SkillError",
    "SkillInfo",
    "SkillMetadata",
    "ToolCall",
    "ToolInfo",
    "Turn",
    "Wait",
    "load_prompt",
    "load_prompts",
    "load_system_prompts",
    "load_skill",
    # Execution
    "AgentEngine",
    # Reporting
    "SuiteReport",
    "TestReport",
    "build_suite_report",
    "generate_html",
    "generate_json",
    # Hooks
    "AitestHookSpec",
    "get_analysis_prompt",
    "get_analysis_prompt_details",
    # Scoring
    "ScoreResult",
    "ScoringDimension",
    "assert_score",
]

from importlib.metadata import version as _get_version  # noqa: E402

__version__ = _get_version("pytest-aitest")
