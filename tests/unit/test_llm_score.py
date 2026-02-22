"""Tests for LLMScore fixture and scoring utilities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pytest_skill_engineering.fixtures.llm_score import (
    LLMScore,
    ScoreResult,
    ScoringDimension,
    _build_scoring_prompt,
    _DimensionScore,
    _JudgeOutput,
    assert_score,
)

# ---------------------------------------------------------------------------
# ScoringDimension
# ---------------------------------------------------------------------------


class TestScoringDimension:
    """Tests for the ScoringDimension dataclass."""

    def test_defaults(self) -> None:
        """Default max_score is 5 and weight is 1.0."""
        dim = ScoringDimension("accuracy", "Factually correct")
        assert dim.name == "accuracy"
        assert dim.description == "Factually correct"
        assert dim.max_score == 5
        assert dim.weight == 1.0

    def test_custom_values(self) -> None:
        """Custom max_score and weight are stored."""
        dim = ScoringDimension("clarity", "Easy to read", max_score=10, weight=2.0)
        assert dim.max_score == 10
        assert dim.weight == 2.0


# ---------------------------------------------------------------------------
# ScoreResult
# ---------------------------------------------------------------------------


class TestScoreResult:
    """Tests for the ScoreResult dataclass."""

    def test_repr_includes_total(self) -> None:
        """Repr shows total, max, percentage, and dimension breakdown."""
        result = ScoreResult(
            scores={"a": 4, "b": 3},
            total=7,
            max_total=10,
            weighted_score=0.7,
            reasoning="Good overall",
        )
        r = repr(result)
        assert "7/10" in r
        assert "70%" in r
        assert "a=4" in r
        assert "b=3" in r

    def test_weighted_score_stored(self) -> None:
        """Weighted score is accessible."""
        result = ScoreResult(
            scores={"x": 5},
            total=5,
            max_total=5,
            weighted_score=1.0,
            reasoning="Perfect",
        )
        assert result.weighted_score == 1.0


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


class TestBuildScoringPrompt:
    """Tests for the internal prompt builder."""

    def test_includes_dimensions(self) -> None:
        """Prompt contains each dimension name and description."""
        rubric = [
            ScoringDimension("accuracy", "Is it correct?"),
            ScoringDimension("tone", "Is the tone professional?"),
        ]
        prompt = _build_scoring_prompt("Hello world", rubric)
        assert "accuracy" in prompt
        assert "tone" in prompt
        assert "Is it correct?" in prompt

    def test_includes_content(self) -> None:
        """Prompt contains the content to evaluate."""
        rubric = [ScoringDimension("quality", "Overall quality")]
        prompt = _build_scoring_prompt("Test content here", rubric)
        assert "Test content here" in prompt

    def test_includes_context(self) -> None:
        """Optional context appears in the prompt."""
        rubric = [ScoringDimension("quality", "Overall quality")]
        prompt = _build_scoring_prompt("Content", rubric, context="The task was to write a poem")
        assert "The task was to write a poem" in prompt

    def test_custom_content_label(self) -> None:
        """Content label customizes how content is described."""
        rubric = [ScoringDimension("quality", "Overall quality")]
        prompt = _build_scoring_prompt("Content", rubric, content_label="implementation plan")
        assert "implementation plan" in prompt


# ---------------------------------------------------------------------------
# assert_score
# ---------------------------------------------------------------------------


class TestAssertScore:
    """Tests for the assert_score helper."""

    @pytest.fixture
    def sample_result(self) -> ScoreResult:
        return ScoreResult(
            scores={"accuracy": 4, "completeness": 3, "clarity": 5},
            total=12,
            max_total=15,
            weighted_score=0.8,
            reasoning="Solid work",
        )

    def test_passes_when_above_min_total(self, sample_result: ScoreResult) -> None:
        """No error when total is at or above the minimum."""
        assert_score(sample_result, min_total=10)

    def test_fails_when_below_min_total(self, sample_result: ScoreResult) -> None:
        """AssertionError when total is below the minimum."""
        with pytest.raises(AssertionError, match="below minimum"):
            assert_score(sample_result, min_total=14)

    def test_passes_when_above_min_pct(self, sample_result: ScoreResult) -> None:
        """No error when weighted score meets minimum percentage."""
        assert_score(sample_result, min_pct=0.7)

    def test_fails_when_below_min_pct(self, sample_result: ScoreResult) -> None:
        """AssertionError when weighted score is below minimum percentage."""
        with pytest.raises(AssertionError, match="below minimum"):
            assert_score(sample_result, min_pct=0.9)

    def test_passes_dimension_minimums(self, sample_result: ScoreResult) -> None:
        """No error when all dimension minimums are met."""
        assert_score(sample_result, min_dimensions={"accuracy": 3, "clarity": 4})

    def test_fails_dimension_minimum(self, sample_result: ScoreResult) -> None:
        """AssertionError when a dimension is below its minimum."""
        with pytest.raises(AssertionError, match="completeness.*scored 3.*minimum is 4"):
            assert_score(sample_result, min_dimensions={"completeness": 4})

    def test_combined_thresholds(self, sample_result: ScoreResult) -> None:
        """All threshold types can be checked simultaneously."""
        assert_score(
            sample_result,
            min_total=10,
            min_pct=0.7,
            min_dimensions={"accuracy": 3},
        )

    def test_no_thresholds_always_passes(self, sample_result: ScoreResult) -> None:
        """Calling with no thresholds is a no-op."""
        assert_score(sample_result)


# ---------------------------------------------------------------------------
# JudgeOutput model
# ---------------------------------------------------------------------------


class TestJudgeOutput:
    """Tests for the structured output Pydantic model."""

    def test_parses_valid_output(self) -> None:
        """Can parse a well-formed judge response."""
        data = {
            "dimensions": [
                {"name": "accuracy", "score": 4, "justification": "Mostly correct"},
                {"name": "tone", "score": 5, "justification": "Professional"},
            ],
            "reasoning": "Good work overall",
        }
        output = _JudgeOutput.model_validate(data)
        assert len(output.dimensions) == 2
        assert output.dimensions[0].score == 4
        assert output.reasoning == "Good work overall"


# ---------------------------------------------------------------------------
# LLMScore callable
# ---------------------------------------------------------------------------


class TestLLMScore:
    """Tests for the LLMScore fixture callable."""

    def test_returns_score_result(self) -> None:
        """__call__ returns a ScoreResult with correct structure."""
        rubric = [
            ScoringDimension("accuracy", "Correct", max_score=5),
            ScoringDimension("completeness", "Thorough", max_score=5),
        ]

        mock_output = _JudgeOutput(
            dimensions=[
                _DimensionScore(name="accuracy", score=4, justification="Good"),
                _DimensionScore(name="completeness", score=3, justification="OK"),
            ],
            reasoning="Decent overall",
        )

        mock_run_result = MagicMock()
        mock_run_result.output = mock_output

        with patch("pydantic_ai.Agent") as MockAgent:
            mock_agent_instance = AsyncMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_run_result)
            MockAgent.return_value = mock_agent_instance

            scorer = LLMScore(model="test-model")
            result = scorer("Some content", rubric)

        assert isinstance(result, ScoreResult)
        assert result.scores["accuracy"] == 4
        assert result.scores["completeness"] == 3
        assert result.total == 7
        assert result.max_total == 10
        assert result.reasoning == "Decent overall"

    def test_clamps_scores_to_valid_range(self) -> None:
        """Scores beyond max_score or below 1 are clamped."""
        rubric = [
            ScoringDimension("dim", "Test", max_score=5),
        ]

        mock_output = _JudgeOutput(
            dimensions=[
                _DimensionScore(name="dim", score=8, justification="Way too high"),
            ],
            reasoning="Overscored",
        )

        mock_run_result = MagicMock()
        mock_run_result.output = mock_output

        with patch("pydantic_ai.Agent") as MockAgent:
            mock_agent_instance = AsyncMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_run_result)
            MockAgent.return_value = mock_agent_instance

            scorer = LLMScore(model="test-model")
            result = scorer("Content", rubric)

        assert result.scores["dim"] == 5  # Clamped to max_score

    def test_missing_dimension_defaults_to_1(self) -> None:
        """If a rubric dimension is missing from judge output, it gets score 1."""
        rubric = [
            ScoringDimension("present", "Exists", max_score=5),
            ScoringDimension("absent", "Missing", max_score=5),
        ]

        mock_output = _JudgeOutput(
            dimensions=[
                _DimensionScore(name="present", score=4, justification="Here"),
            ],
            reasoning="Partial",
        )

        mock_run_result = MagicMock()
        mock_run_result.output = mock_output

        with patch("pydantic_ai.Agent") as MockAgent:
            mock_agent_instance = AsyncMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_run_result)
            MockAgent.return_value = mock_agent_instance

            scorer = LLMScore(model="test-model")
            result = scorer("Content", rubric)

        assert result.scores["present"] == 4
        assert result.scores["absent"] == 1  # Clamped from 0 to 1

    def test_weighted_score_calculation(self) -> None:
        """Weighted composite score accounts for dimension weights."""
        rubric = [
            ScoringDimension("heavy", "Important", max_score=5, weight=3.0),
            ScoringDimension("light", "Minor", max_score=5, weight=1.0),
        ]

        mock_output = _JudgeOutput(
            dimensions=[
                _DimensionScore(name="heavy", score=5, justification="Perfect"),
                _DimensionScore(name="light", score=1, justification="Minimal"),
            ],
            reasoning="Mixed",
        )

        mock_run_result = MagicMock()
        mock_run_result.output = mock_output

        with patch("pydantic_ai.Agent") as MockAgent:
            mock_agent_instance = AsyncMock()
            mock_agent_instance.run = AsyncMock(return_value=mock_run_result)
            MockAgent.return_value = mock_agent_instance

            scorer = LLMScore(model="test-model")
            result = scorer("Content", rubric)

        # heavy: 5/5 * 3.0 = 3.0, light: 1/5 * 1.0 = 0.2
        # total_weight = 4.0, weighted = 3.2 / 4.0 = 0.8
        assert abs(result.weighted_score - 0.8) < 0.01
