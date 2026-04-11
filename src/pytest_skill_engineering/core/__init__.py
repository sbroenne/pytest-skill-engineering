"""Core module - result types and skill management."""

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
from pytest_skill_engineering.core.scoring import ScoreResult, ScoringDimension, assert_score
from pytest_skill_engineering.core.skill import Skill, SkillError, SkillMetadata, load_skill
from pytest_skill_engineering.core.skill_benchmark import (
    BenchmarkComparison,
    CaseBenchmark,
    SkillBenchmarkResult,
)
from pytest_skill_engineering.core.skill_eval_results import (
    SkillCaseResult,
    SkillGradingResult,
)
from pytest_skill_engineering.core.skill_evals import (
    SkillEvalCase,
    has_skill_evals,
    load_skill_evals,
)
from pytest_skill_engineering.core.skill_grading import export_grading
from pytest_skill_engineering.core.skill_refiner import (
    RefinementResult,
    RefinementSuggestion,
    analyze_skill_failures,
)

__all__ = [
    "AITestError",
    "BenchmarkComparison",
    "CaseBenchmark",
    "EvalResult",
    "EngineTimeoutError",
    "HookDefinition",
    "ImageContent",
    "MCPPrompt",
    "MCPPromptArgument",
    "Plugin",
    "PluginMetadata",
    "Prompt",
    "RefinementResult",
    "RefinementSuggestion",
    "ScoreResult",
    "ScoringDimension",
    "ServerStartError",
    "Skill",
    "SkillBenchmarkResult",
    "SkillCaseResult",
    "SkillError",
    "SkillInfo",
    "SkillGradingResult",
    "SkillMetadata",
    "SubagentInvocation",
    "ToolCall",
    "ToolInfo",
    "Turn",
    "analyze_skill_failures",
    "assert_score",
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
