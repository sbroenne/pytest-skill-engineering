"""Copilot task execution and evidence for testing AI-facing tools and skills."""

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
from pytest_skill_engineering.execution import (  # noqa: E402
    CLIServer,
    MCPServer,
    Wait,
    WaitStrategy,
)

# Reporting
from pytest_skill_engineering.reporting import (  # noqa: E402
    SuiteReport,
    TestReport,
    build_suite_report,
    generate_json,
    load_suite_report,
)

__all__ = [  # noqa: RUF022
    # Core
    "AITestError",
    "EngineTimeoutError",
    "EvalResult",
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
    "export_grading",
    "has_skill_evals",
    "load_custom_agent",
    "load_custom_agents",
    "load_instruction_file",
    "load_instruction_files",
    "load_plugin",
    "load_prompt",
    "load_prompt_file",
    "load_prompt_files",
    "load_prompts",
    "load_skill",
    "load_skill_evals",
    "load_system_prompts",
    # Copilot (primary eval harness)
    "ClaudeCodePersona",
    "CopilotCLIPersona",
    "CopilotEval",
    "CopilotResult",
    "HeadlessPersona",
    "Persona",
    "VSCodePersona",
    "run_copilot",
    # Server config types
    "CLIServer",
    "MCPServer",
    "Wait",
    "WaitStrategy",
    # Reporting
    "SuiteReport",
    "TestReport",
    "build_suite_report",
    "generate_json",
    "load_suite_report",
]

from importlib.metadata import version as _get_version  # noqa: E402

__version__ = _get_version("pytest-skill-engineering")
