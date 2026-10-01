---
description: "Auto-generated API documentation for pytest-skill-engineering core types: CopilotEval, Skill, EvalResult, and more."
---

# API Reference

Auto-generated API documentation from source code.

## Copilot Types

::: pytest_skill_engineering.copilot.eval.CopilotEval
    options:
      show_source: false
      heading_level: 3

::: pytest_skill_engineering.copilot.result.CopilotResult
    options:
      show_source: false
      heading_level: 3

## Result Types

::: pytest_skill_engineering.core.result.EvalResult
    options:
      show_source: false
      heading_level: 3

::: pytest_skill_engineering.core.result.Turn
    options:
      show_source: false
      heading_level: 3

::: pytest_skill_engineering.core.result.ToolCall
    options:
      show_source: false
      heading_level: 3

::: pytest_skill_engineering.core.result.ClarificationStats
    options:
      show_source: false
      heading_level: 3

::: pytest_skill_engineering.core.result.ToolInfo
    options:
      show_source: false
      heading_level: 3

::: pytest_skill_engineering.core.result.SkillInfo
    options:
      show_source: false
      heading_level: 3

::: pytest_skill_engineering.core.result.SubagentInvocation
    options:
      show_source: false
      heading_level: 3

## Explicit case loading and export

Free-text expectations are descriptions, not automatically executed checks.
Consumers supply their own booleans and evidence to the exporter.

::: pytest_skill_engineering.core.skill_evals.load_skill_evals
    options:
      show_source: false
      heading_level: 3

::: pytest_skill_engineering.core.skill_evals.SkillEvalCase
    options:
      show_source: false
      heading_level: 3

::: pytest_skill_engineering.core.skill_grading.export_grading
    options:
      show_source: false
      heading_level: 3

## Native execution evidence

These APIs save and load captured execution and ordinary pytest outcomes.
They do not render reports, interpret results, rank configurations, or select winners.

::: pytest_skill_engineering.reporting.collector.TestReport
    options:
      show_source: false
      heading_level: 3

::: pytest_skill_engineering.reporting.collector.SuiteReport
    options:
      show_source: false
      heading_level: 3

::: pytest_skill_engineering.reporting.generator.generate_json
    options:
      show_source: false
      heading_level: 3

::: pytest_skill_engineering.reporting.generator.load_suite_report
    options:
      show_source: false
      heading_level: 3

## Skill Types

::: pytest_skill_engineering.core.skill.Skill
    options:
      show_source: false
      heading_level: 3

::: pytest_skill_engineering.core.skill.SkillMetadata
    options:
      show_source: false
      heading_level: 3

::: pytest_skill_engineering.core.skill.load_skill
    options:
      show_source: false
      heading_level: 3

## Custom Agent Types

::: pytest_skill_engineering.core.evals.load_custom_agent
    options:
      show_source: false
      heading_level: 3

::: pytest_skill_engineering.core.evals.load_custom_agents
    options:
      show_source: false
      heading_level: 3

## Plugin Types

::: pytest_skill_engineering.core.plugin.Plugin
    options:
      show_source: false
      heading_level: 3

::: pytest_skill_engineering.core.plugin.PluginMetadata
    options:
      show_source: false
      heading_level: 3

::: pytest_skill_engineering.core.plugin.HookDefinition
    options:
      show_source: false
      heading_level: 3

## Plugin Loading

::: pytest_skill_engineering.core.plugin.load_plugin
    options:
      show_source: false
      heading_level: 3
