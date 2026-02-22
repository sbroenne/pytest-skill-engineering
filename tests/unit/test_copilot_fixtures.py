"""Unit tests for the ab_run fixture."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from pytest_aitest.copilot.agent import CopilotAgent
from pytest_aitest.copilot.result import CopilotResult


def _make_result(success: bool = True) -> CopilotResult:
    return CopilotResult(success=success)


class TestAbRunFixture:
    """Tests for the ab_run fixture."""

    @pytest.fixture(autouse=True)
    def _no_stash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Prevent ab_run from registering test reports in the plugin stash."""
        monkeypatch.setattr("pytest_aitest.copilot.fixtures.stash_on_item", lambda *a: None)

    @pytest.fixture
    def baseline_agent(self) -> CopilotAgent:
        return CopilotAgent(name="baseline", instructions="Write plain Python.")

    @pytest.fixture
    def treatment_agent(self) -> CopilotAgent:
        return CopilotAgent(name="treatment", instructions="Write Python with docstrings.")

    async def test_returns_tuple_of_two_results(
        self, ab_run, baseline_agent, treatment_agent, tmp_path
    ):
        """ab_run returns a 2-tuple of CopilotResult."""
        baseline_result = _make_result(success=True)
        treatment_result = _make_result(success=True)

        with patch(
            "pytest_aitest.copilot.fixtures.run_copilot",
            new=AsyncMock(side_effect=[baseline_result, treatment_result]),
        ):
            b, t = await ab_run(baseline_agent, treatment_agent, "Write math.py")

        assert isinstance(b, CopilotResult)
        assert isinstance(t, CopilotResult)
        assert b is baseline_result
        assert t is treatment_result

    async def test_creates_isolated_directories(
        self, ab_run, baseline_agent, treatment_agent, tmp_path
    ):
        """ab_run creates baseline/ and treatment/ under tmp_path."""
        captured_agents = []

        async def _capture(agent, task):
            captured_agents.append(agent)
            return _make_result()

        with patch("pytest_aitest.copilot.fixtures.run_copilot", side_effect=_capture):
            await ab_run(baseline_agent, treatment_agent, "some task")

        baseline_dir = tmp_path / "baseline"
        treatment_dir = tmp_path / "treatment"
        assert baseline_dir.exists()
        assert treatment_dir.exists()

    async def test_overrides_working_directory_on_both_agents(self, ab_run, tmp_path):
        """ab_run overrides working_directory regardless of original value."""
        original_baseline = CopilotAgent(name="b", working_directory="/original/b")
        original_treatment = CopilotAgent(name="t", working_directory="/original/t")

        captured: list[CopilotAgent] = []

        async def _capture(agent, task):
            captured.append(agent)
            return _make_result()

        with patch("pytest_aitest.copilot.fixtures.run_copilot", side_effect=_capture):
            await ab_run(original_baseline, original_treatment, "task")

        assert captured[0].working_directory == str(tmp_path / "baseline")
        assert captured[1].working_directory == str(tmp_path / "treatment")

    async def test_agents_without_working_directory_get_isolated_dirs(self, ab_run, tmp_path):
        """Agents with no working_directory still get isolated dirs."""
        baseline = CopilotAgent(name="b")
        treatment = CopilotAgent(name="t")

        captured: list[CopilotAgent] = []

        async def _capture(agent, task):
            captured.append(agent)
            return _make_result()

        with patch("pytest_aitest.copilot.fixtures.run_copilot", side_effect=_capture):
            await ab_run(baseline, treatment, "task")

        assert captured[0].working_directory == str(tmp_path / "baseline")
        assert captured[1].working_directory == str(tmp_path / "treatment")

    async def test_runs_baseline_before_treatment(self, ab_run, tmp_path):
        """ab_run runs baseline first, then treatment (sequential)."""
        call_order: list[str] = []

        async def _capture(agent, task):
            call_order.append(agent.name)
            return _make_result()

        baseline = CopilotAgent(name="baseline")
        treatment = CopilotAgent(name="treatment")

        with patch("pytest_aitest.copilot.fixtures.run_copilot", side_effect=_capture):
            await ab_run(baseline, treatment, "task")

        assert call_order == ["baseline", "treatment"]

    async def test_does_not_mutate_original_agents(self, ab_run, tmp_path):
        """ab_run does not mutate the original CopilotAgent objects."""
        original_baseline = CopilotAgent(name="b", working_directory=None)
        original_treatment = CopilotAgent(name="t", working_directory=None)

        with patch(
            "pytest_aitest.copilot.fixtures.run_copilot",
            new=AsyncMock(return_value=_make_result()),
        ):
            await ab_run(original_baseline, original_treatment, "task")

        # Frozen dataclasses cannot be mutated — but verify the originals are unchanged
        assert original_baseline.working_directory is None
        assert original_treatment.working_directory is None

    async def test_stashes_treatment_result_for_aitest(self, ab_run, request, tmp_path):
        """ab_run stashes treatment result on the test node for aitest."""
        treatment_result = _make_result(success=True)
        treatment = CopilotAgent(name="treatment")

        with (
            patch(
                "pytest_aitest.copilot.fixtures.run_copilot",
                new=AsyncMock(side_effect=[_make_result(), treatment_result]),
            ),
            patch("pytest_aitest.copilot.fixtures.stash_on_item") as mock_stash,
        ):
            await ab_run(CopilotAgent(name="baseline"), treatment, "task")

        # stash_on_item called once with treatment result
        mock_stash.assert_called_once()
        _, _, stashed_result = mock_stash.call_args[0]
        assert stashed_result is treatment_result

    async def test_passes_task_to_both_agents(self, ab_run, tmp_path):
        """ab_run passes the same task string to both agents."""
        captured_tasks: list[str] = []

        async def _capture(agent, task):
            captured_tasks.append(task)
            return _make_result()

        with patch("pytest_aitest.copilot.fixtures.run_copilot", side_effect=_capture):
            await ab_run(CopilotAgent(), CopilotAgent(), "my specific task")

        assert captured_tasks == ["my specific task", "my specific task"]
