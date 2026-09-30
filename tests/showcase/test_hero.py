"""Real outcome examples demonstrating core pytest-skill-engineering capabilities.

Run with:
    uv run python -m pytest tests/showcase/ -v \
        --aitest-json=aitest-reports/results.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pytest_skill_engineering.copilot import CopilotEval
from tests.integration.copilot.conftest import MODELS

pytestmark = [pytest.mark.copilot]

_SHOWCASE_DIR = Path(__file__).parent
_INSTRUCTION_FILES = sorted((_SHOWCASE_DIR / "instructions").glob("*.md"))
_FINANCIAL_SKILL = _SHOWCASE_DIR / "skills" / "financial-advisor"


def _banking_eval(
    *,
    name: str,
    system_prompt: str,
    mcp_servers: dict[str, Any],
    working_directory: Path,
    model: str | None = None,
    skill_directories: list[str] | None = None,
) -> CopilotEval:
    """Build a showcase eval connected to the banking MCP server."""
    return CopilotEval(
        name=name,
        model=model,
        instructions=system_prompt,
        mcp_servers=mcp_servers,
        working_directory=str(working_directory),
        skill_directories=skill_directories or [],
    )


def _operation_result(call) -> str:
    """Read the SDK's display-plus-structured representation of an MCP string."""
    assert call.evidence_complete
    assert call.result is not None
    display, structured = call.result.rsplit("\n\n", 1)
    assert json.loads(structured) == {"result": display}
    return display


class TestBasicOperations:
    """Demonstrate direct MCP tool selection."""

    async def test_check_single_balance(
        self,
        copilot_eval,
        tmp_path,
        banking_mcp_servers,
        banking_system_prompt,
    ):
        """Retrieve one account balance."""
        agent = _banking_eval(
            name="banking-basic",
            system_prompt=banking_system_prompt,
            mcp_servers=banking_mcp_servers,
            working_directory=tmp_path,
        )

        result = await copilot_eval(agent, "What's my checking account balance?")

        assert result.success
        assert result.tool_was_called("banking-get_balance")


class TestMultiToolWorkflows:
    """Demonstrate coordinated MCP tool calls."""

    async def test_transfer_and_verify(
        self,
        copilot_eval,
        tmp_path,
        banking_mcp_servers,
        banking_system_prompt,
    ):
        """Transfer money and verify the updated balances."""
        agent = _banking_eval(
            name="banking-workflow",
            system_prompt=banking_system_prompt,
            mcp_servers=banking_mcp_servers,
            working_directory=tmp_path,
        )

        result = await copilot_eval(
            agent,
            "Transfer $100 from checking to savings, then show my updated balances.",
        )

        assert result.success
        assert result.tool_was_called("banking-transfer")
        assert result.tool_was_called("banking-get_all_balances") or result.tool_was_called(
            "banking-get_balance"
        )
        transfers = result.tool_calls_for("banking-transfer")
        assert len(transfers) == 1
        assert transfers[0].arguments == {
            "from_account": "checking",
            "to_account": "savings",
            "amount": 100,
        }
        assert transfers[0].evidence_complete
        assert transfers[0].result is not None
        receipt = json.loads(_operation_result(transfers[0]))
        assert receipt["amount"] == 100
        balances = result.tool_calls_for("banking-get_all_balances")
        if balances:
            assert balances[-1].result is not None
            observed = json.loads(_operation_result(balances[-1]))
            assert observed["accounts"]["checking"]["balance"] == 1400
            assert observed["accounts"]["savings"]["balance"] == 3100
            assert observed["total"] == 4500
        else:
            calls = result.tool_calls_for("banking-get_balance")
            observed = {
                call.arguments["account"]: json.loads(_operation_result(call))["balance"]
                for call in calls
            }
            assert observed == {"checking": 1400, "savings": 3100}


class TestModelComparison:
    """Compare the configured Copilot models on the same banking task."""

    @pytest.mark.parametrize("model", MODELS)
    async def test_financial_advice_quality(
        self,
        copilot_eval,
        tmp_path,
        banking_mcp_servers,
        banking_system_prompt,
        model,
    ):
        """Require every model to ground its advice in account data."""
        agent = _banking_eval(
            name=f"banking-{model}",
            model=model,
            system_prompt=banking_system_prompt,
            mcp_servers=banking_mcp_servers,
            working_directory=tmp_path,
        )

        result = await copilot_eval(
            agent,
            "Review my account balances and recommend one concrete savings action.",
        )

        assert result.success
        assert result.tool_was_called("banking-get_all_balances") or result.tool_was_called(
            "banking-get_balance"
        )


class TestSystemPromptComparison:
    """Compare concise, detailed, and friendly system prompts."""

    @pytest.mark.parametrize(
        "instruction_path",
        _INSTRUCTION_FILES,
        ids=lambda path: path.stem,
    )
    async def test_advice_style(
        self,
        copilot_eval,
        tmp_path,
        banking_mcp_servers,
        banking_system_prompt,
        instruction_path,
    ):
        """Apply each system prompt style to the same account review."""
        style = instruction_path.read_text(encoding="utf-8")
        agent = _banking_eval(
            name=f"banking-{instruction_path.stem}",
            system_prompt=f"{banking_system_prompt}\n\n{style}",
            mcp_servers=banking_mcp_servers,
            working_directory=tmp_path,
        )

        result = await copilot_eval(
            agent,
            "Check my accounts and advise me on managing my money better.",
        )

        assert result.success
        assert result.tool_was_called("banking-get_all_balances") or result.tool_was_called(
            "banking-get_balance"
        )


class TestSkillEnhancement:
    """Demonstrate domain guidance supplied by a skill."""

    async def test_financial_advisor_skill(
        self,
        copilot_eval,
        tmp_path,
        banking_mcp_servers,
        banking_system_prompt,
    ):
        """Verify an explicit emergency-fund calculation with account data."""
        agent = _banking_eval(
            name="banking-with-skill",
            system_prompt=banking_system_prompt,
            mcp_servers=banking_mcp_servers,
            working_directory=tmp_path,
            skill_directories=[str(_FINANCIAL_SKILL)],
        )

        result = await copilot_eval(
            agent,
            "Review my balances. Use monthly expenses of $1000 and exactly three months "
            "of expenses as the emergency-fund target. Write plan.json with numeric fields "
            "target and shortfall, using my savings balance to calculate the shortfall. "
            "Do not move any money.",
        )

        assert result.success
        assert result.tool_was_called("banking-get_all_balances")
        calls = result.tool_calls_for("banking-get_all_balances")
        assert calls[-1].evidence_complete
        assert calls[-1].result is not None
        balances = json.loads(_operation_result(calls[-1]))
        savings = balances["accounts"]["savings"]["balance"]
        plan = json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))
        assert plan == {"target": 3 * 1000, "shortfall": max(0, 3 * 1000 - savings)}
        assert not result.tool_was_called("banking-transfer")


class TestErrorHandling:
    """Demonstrate recovery from a rejected banking operation."""

    async def test_insufficient_funds(
        self,
        copilot_eval,
        tmp_path,
        banking_mcp_servers,
        banking_system_prompt,
    ):
        """Observe the tool's rejected transfer, not a subjective explanation grade."""
        agent = _banking_eval(
            name="banking-error-handling",
            system_prompt=(
                f"{banking_system_prompt}\n"
                "For transfer requests, call the transfer tool with the exact requested amount. "
                "If the tool rejects the operation, explain the failure and suggest an alternative."
            ),
            mcp_servers=banking_mcp_servers,
            working_directory=tmp_path,
        )

        result = await copilot_eval(
            agent,
            "Attempt to transfer exactly $50,000 from checking to savings. "
            "Call the transfer tool even though the amount may exceed the balance.",
        )

        assert result.success
        assert result.tool_was_called("banking-transfer")
        calls = result.tool_calls_for("banking-transfer")
        assert len(calls) == 1
        assert calls[0].arguments["amount"] == 50_000
        assert calls[0].evidence_complete
        assert _operation_result(calls[0]) == (
            "Error: Insufficient funds. checking has $1,500.00, but transfer requires $50,000.00."
        )
