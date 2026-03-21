"""Core module - result types and skill management."""

from typing import TYPE_CHECKING

from pytest_skill_engineering.core.errors import AITestError, EngineTimeoutError, ServerStartError
from pytest_skill_engineering.core.evals import (
    load_custom_agent,
    load_custom_agents,
    load_instruction_file,
    load_instruction_files,
    load_prompt_file,
    load_prompt_files,
)
from pytest_skill_engineering.core.plugin import HookDefinition, Plugin, PluginMetadata, load_plugin
from pytest_skill_engineering.core.prompt import (
    Prompt,
    load_prompt,
    load_prompts,
    load_system_prompts,
)
from pytest_skill_engineering.core.result import (
    EvalResult,
    ImageContent,
    MCPPrompt,
    MCPPromptArgument,
    SkillInfo,
    SubagentInvocation,
    ToolCall,
    ToolInfo,
    Turn,
)
from pytest_skill_engineering.core.skill import Skill, SkillError, SkillMetadata, load_skill
from pytest_skill_engineering.core.skill_evals import (
    SkillEvalCase,
    has_skill_evals,
    load_skill_evals,
)
from pytest_skill_engineering.core.skill_grading import export_grading

__all__ = [
    "AITestError",
    "EvalResult",
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
    "load_skill",
    "load_system_prompts",
    "SkillEvalCase",
    "has_skill_evals",
    "load_skill_evals",
    "export_grading",
]


# Re-export SkillCaseResult and SkillGradingResult for public API
# These are defined in fixtures.skill_eval but conceptually part of core skill-creator integration
def __getattr__(name: str):
    """Lazy import for SkillCaseResult and SkillGradingResult to avoid circular imports."""
    if name in ("SkillCaseResult", "SkillGradingResult"):
        from pytest_skill_engineering.fixtures.skill_eval import (
            SkillCaseResult,
            SkillGradingResult,
        )

        return SkillCaseResult if name == "SkillCaseResult" else SkillGradingResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if TYPE_CHECKING:
    from pytest_skill_engineering.fixtures.skill_eval import SkillCaseResult, SkillGradingResult

    __all__ += ["SkillCaseResult", "SkillGradingResult"]
