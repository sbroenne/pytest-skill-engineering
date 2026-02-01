"""Report generation with composable renderers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from pytest_aitest.reporting.aggregator import DimensionAggregator, ReportMode

if TYPE_CHECKING:
    from pytest_aitest.core.result import AgentResult
    from pytest_aitest.reporting.collector import SuiteReport, TestReport


def _render_markdown(text: str) -> Markup:
    """Convert markdown to HTML, sanitized for safe output."""
    try:
        import markdown

        html = markdown.markdown(text, extensions=["extra"])
        return Markup(html)
    except ImportError:
        # Fallback: basic line break handling if markdown not installed
        import html

        escaped = html.escape(text)
        return Markup(escaped.replace("\n", "<br>"))


def get_provider(model_name: str) -> str:
    """Extract provider name from model string for badge styling."""
    model_lower = model_name.lower()
    if "azure" in model_lower:
        return "azure"
    elif "openai" in model_lower or model_lower.startswith("gpt"):
        return "openai"
    elif "anthropic" in model_lower or "claude" in model_lower:
        return "anthropic"
    elif "vertex" in model_lower or "gemini" in model_lower:
        return "vertex"
    return "default"


def _sanitize_mermaid_text(text: str, limit: int) -> str:
    cleaned = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    cleaned = cleaned.replace('"', "'")
    cleaned = " ".join(cleaned.split())
    return cleaned[:limit]


def _to_file_url(path: str) -> str:
    return Path(path).resolve().as_uri()


class ReportGenerator:
    """Generates HTML and JSON reports with smart layout selection.

    Automatically chooses the best report layout based on detected test dimensions:
    - Simple: Standard test list
    - Model comparison: Side-by-side model comparison table
    - Prompt comparison: Prompt variant comparison
    - Matrix: 2D grid of models x prompts

    Example:
        generator = ReportGenerator()
        generator.generate_html(suite_report, "report.html")
        generator.generate_json(suite_report, "report.json")
    """

    def __init__(self) -> None:
        # Use importlib.resources to find templates directory reliably
        import importlib.resources as resources

        templates_dir = resources.files("pytest_aitest").joinpath("templates")
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=True,
        )
        self._env.filters["markdown"] = _render_markdown
        self._aggregator = DimensionAggregator()

    def generate_html(
        self,
        report: SuiteReport,
        output_path: str | Path,
        *,
        ai_summary: str | None = None,
    ) -> None:
        """Generate HTML report with adaptive layout.

        Args:
            report: Test suite report data
            output_path: Path to write HTML file
            ai_summary: Optional LLM-generated summary to include
        """
        # Detect dimensions for smart rendering
        dimensions = self._aggregator.detect_dimensions(report)
        flags = self._aggregator.get_adaptive_flags(report)

        # Prepare context based on mode
        context: dict[str, Any] = {
            "report": report,
            "dimensions": dimensions,
            "flags": flags,
            "mode": dimensions.mode.name.lower(),
            "format_cost": self._format_cost,
            "generate_mermaid": generate_mermaid_sequence,
            "get_provider": get_provider,
            "to_file_url": _to_file_url,
            "float": float,  # For infinity comparison in template
            "ai_summary": ai_summary,
        }

        # Add grouped data based on mode
        if dimensions.mode == ReportMode.MODEL_COMPARISON:
            context["model_groups"] = self._aggregator.group_by_model(report)
            context["model_rankings"] = self._aggregator.get_model_rankings(report)
        elif dimensions.mode == ReportMode.PROMPT_COMPARISON:
            context["prompt_groups"] = self._aggregator.group_by_prompt(report)
            context["prompt_rankings"] = self._aggregator.get_prompt_rankings(report)
        elif dimensions.mode == ReportMode.MATRIX:
            context["matrix"] = self._aggregator.build_matrix(report, dimensions)
            context["model_groups"] = self._aggregator.group_by_model(report)
            context["prompt_groups"] = self._aggregator.group_by_prompt(report)

        template = self._env.get_template("report.html")
        html = template.render(**context)
        Path(output_path).write_text(html)

    def generate_json(self, report: SuiteReport, output_path: str | Path) -> None:
        """Generate JSON report."""
        data = self._serialize_report(report)
        Path(output_path).write_text(json.dumps(data, indent=2))

    @staticmethod
    def _format_cost(cost: float) -> str:
        """Format cost in USD."""
        if cost == 0:
            return "N/A"
        if cost < 0.01:
            return f"${cost:.6f}"
        return f"${cost:.4f}"

    def _serialize_report(self, report: SuiteReport) -> dict[str, Any]:
        """Serialize report to dict for JSON."""
        dimensions = self._aggregator.detect_dimensions(report)

        data: dict[str, Any] = {
            "name": report.name,
            "timestamp": report.timestamp,
            "duration_ms": report.duration_ms,
            "mode": dimensions.mode.name.lower(),
            "dimensions": {
                "models": dimensions.models,
                "prompts": dimensions.prompts,
                "base_tests": dimensions.base_tests,
            },
            "summary": {
                "total": report.total,
                "passed": report.passed,
                "failed": report.failed,
                "skipped": report.skipped,
                "pass_rate": report.pass_rate,
                "total_tokens": report.total_tokens,
                "total_cost_usd": report.total_cost_usd,
                "token_stats": report.token_stats,
                "cost_stats": report.cost_stats,
            },
            "tests": [self._serialize_test(t) for t in report.tests],
        }

        # Add comparison data if applicable
        if dimensions.mode == ReportMode.MODEL_COMPARISON:
            data["model_comparison"] = [
                {
                    "model": g.dimension_value,
                    "pass_rate": g.pass_rate,
                    "passed": g.passed,
                    "failed": g.failed,
                    "total_tokens": g.total_tokens,
                    "total_cost": g.total_cost,
                }
                for g in self._aggregator.group_by_model(report)
            ]
        elif dimensions.mode == ReportMode.PROMPT_COMPARISON:
            data["prompt_comparison"] = [
                {
                    "prompt": g.dimension_value,
                    "pass_rate": g.pass_rate,
                    "passed": g.passed,
                    "failed": g.failed,
                }
                for g in self._aggregator.group_by_prompt(report)
            ]
        elif dimensions.mode == ReportMode.MATRIX:
            matrix = self._aggregator.build_matrix(report, dimensions)
            data["matrix"] = [
                [
                    {
                        "model": cell.model,
                        "prompt": cell.prompt,
                        "outcome": cell.outcome,
                        "passed": cell.passed,
                    }
                    for cell in row
                ]
                for row in matrix
            ]

        return data

    def _serialize_test(self, test: TestReport) -> dict[str, Any]:
        """Serialize test report to dict."""
        data: dict[str, Any] = {
            "name": test.name,
            "outcome": test.outcome,
            "duration_ms": test.duration_ms,
            "metadata": test.metadata,
        }

        if test.error:
            data["error"] = test.error

        if test.agent_result:
            data["agent_result"] = self._serialize_agent_result(test.agent_result)

        if test.assertions:
            data["assertions"] = test.assertions

        return data

    def _serialize_agent_result(self, result: AgentResult) -> dict[str, Any]:
        """Serialize AgentResult to dict."""
        return {
            "success": result.success,
            "error": result.error,
            "duration_ms": result.duration_ms,
            "token_usage": result.token_usage,
            "cost_usd": result.cost_usd,
            "turns": [
                {
                    "role": t.role,
                    "content": t.content,
                    "tool_calls": [
                        {
                            "name": tc.name,
                            "arguments": tc.arguments,
                            "result": tc.result,
                            "error": tc.error,
                        }
                        for tc in t.tool_calls
                    ],
                }
                for t in result.turns
            ],
            "final_response": result.final_response,
            "tools_called": list(result.tool_names_called),
        }


def generate_mermaid_sequence(result: AgentResult) -> str:
    """Generate Mermaid sequence diagram from agent result.

    Example output:
        sequenceDiagram
            participant User
            participant Agent
            participant Tools

            User->>Agent: Hello!
            Agent->>Tools: read_file(path="/tmp/test.txt")
            Tools-->>Agent: File contents...
            Agent->>User: Here is the file...
    """
    lines = [
        "sequenceDiagram",
        "    participant User",
        "    participant Agent",
        "    participant Tools",
        "",
    ]

    for turn in result.turns:
        if turn.role == "user":
            content = _sanitize_mermaid_text(turn.content, 80)
            lines.append(f'    User->>Agent: "{content}"')

        elif turn.role == "assistant":
            if turn.tool_calls:
                for tc in turn.tool_calls:
                    args_preview = _sanitize_mermaid_text(str(tc.arguments), 60)
                    lines.append(f'    Agent->>Tools: "{tc.name}({args_preview})"')
                    if tc.error:
                        err_preview = _sanitize_mermaid_text(str(tc.error), 60)
                        lines.append(f'    Tools--xAgent: "Error: {err_preview}"')
                    elif tc.result:
                        result_preview = _sanitize_mermaid_text(tc.result, 60)
                        lines.append(f'    Tools-->>Agent: "{result_preview}"')
            else:
                content = _sanitize_mermaid_text(turn.content, 80)
                lines.append(f'    Agent->>User: "{content}"')

    return "\n".join(lines)
