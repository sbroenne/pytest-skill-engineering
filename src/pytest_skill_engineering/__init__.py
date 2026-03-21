"""pytest-skill-engineering: Pytest plugin for testing AI agents with MCP and CLI servers."""

import logging

# Configure library logging per Python best practices:
# https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library
# Libraries should add NullHandler to prevent "No handler found" warnings
# when the application hasn't configured logging.
logging.getLogger(__name__).addHandler(logging.NullHandler())

# Core types  # noqa: E402 - logging must be configured before submodule imports
# Copilot coding agent support (now required)
from pytest_skill_engineering.copilot import (  # noqa: E402
    ClaudeCodePersona,
    CopilotCLIPersona,
    CopilotEval,
    CopilotResult,
    HeadlessPersona,
    Persona,
    VSCodePersona,
    run_copilot,
)
from pytest_skill_engineering.core import (  # noqa: E402
    AITestError,
    EngineTimeoutError,
    EvalResult,
    HookDefinition,
    ImageContent,
    MCPPrompt,
    MCPPromptArgument,
    Plugin,
    PluginMetadata,
    Prompt,
    ServerStartError,
    Skill,
    SkillError,
    SkillEvalCase,
    SkillInfo,
    SkillMetadata,
    SubagentInvocation,
    ToolCall,
    ToolInfo,
    Turn,
    export_grading,
    has_skill_evals,
    load_custom_agent,
    load_custom_agents,
    load_instruction_file,
    load_instruction_files,
    load_plugin,
    load_prompt,
    load_prompt_file,
    load_prompt_files,
    load_prompts,
    load_skill,
    load_skill_evals,
    load_system_prompts,
)

# Scoring
from pytest_skill_engineering.fixtures.llm_score import (  # noqa: E402
    ScoreResult,
    ScoringDimension,
    assert_score,
)

# Hooks (for plugin extensibility)
from pytest_skill_engineering.hooks import AitestHookSpec  # noqa: E402
from pytest_skill_engineering.plugin import (  # noqa: E402
    get_analysis_prompt,
    get_analysis_prompt_details,
)

# Reporting
from pytest_skill_engineering.reporting import (  # noqa: E402
    SuiteReport,
    TestReport,
    build_suite_report,
    generate_html,
    generate_json,
)

__all__ = [  # noqa: RUF022
    # Core
    "EvalResult",
    "AITestError",
    "EngineTimeoutError",
    "HookDefinition",
    "ImageContent",
    "MCPPrompt",
    "MCPPromptArgument",
    "Plugin",
    "PluginMetadata",
    "Prompt",
    "ServerStartError",
    "Skill",
    "SkillError",
    "SkillEvalCase",
    "SkillInfo",
    "SkillMetadata",
    "SubagentInvocation",
    "ToolCall",
    "ToolInfo",
    "Turn",
    "load_custom_agent",
    "load_custom_agents",
    "load_instruction_file",
    "load_instruction_files",
    "load_plugin",
    "load_prompt_file",
    "load_prompt_files",
    "load_prompt",
    "load_prompts",
    "load_system_prompts",
    "load_skill",
    "load_skill_evals",
    "has_skill_evals",
    "export_grading",
    # Copilot (primary eval harness)
    "CopilotEval",
    "CopilotResult",
    "ClaudeCodePersona",
    "CopilotCLIPersona",
    "HeadlessPersona",
    "Persona",
    "VSCodePersona",
    "run_copilot",
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

__version__ = _get_version("pytest-skill-engineering")
