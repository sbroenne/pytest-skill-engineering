"""Unit tests for clarification detection."""

from __future__ import annotations

from pytest_skill_engineering.core.agent import (
    Agent,
    ClarificationDetection,
    ClarificationLevel,
    Provider,
)
from pytest_skill_engineering.core.result import AgentResult, ClarificationStats, Turn


class TestClarificationDetectionConfig:
    """Test ClarificationDetection configuration."""

    def test_default_disabled(self) -> None:
        """Default config has detection disabled."""
        config = ClarificationDetection()
        assert not config.enabled
        assert config.level == ClarificationLevel.WARNING
        assert config.judge_model is None

    def test_enabled_with_defaults(self) -> None:
        config = ClarificationDetection(enabled=True)
        assert config.enabled
        assert config.level == ClarificationLevel.WARNING
        assert config.judge_model is None

    def test_custom_judge_model(self) -> None:
        config = ClarificationDetection(
            enabled=True,
            level=ClarificationLevel.ERROR,
            judge_model="azure/gpt-5-mini",
        )
        assert config.enabled
        assert config.level == ClarificationLevel.ERROR
        assert config.judge_model == "azure/gpt-5-mini"

    def test_agent_default_no_detection(self) -> None:
        """Agent has detection disabled by default."""
        agent = Agent(provider=Provider(model="azure/gpt-5-mini"))
        assert not agent.clarification_detection.enabled

    def test_agent_with_detection(self) -> None:
        """Agent can be configured with clarification detection."""
        agent = Agent(
            provider=Provider(model="azure/gpt-5-mini"),
            clarification_detection=ClarificationDetection(enabled=True),
        )
        assert agent.clarification_detection.enabled


class TestClarificationStats:
    """Test ClarificationStats dataclass."""

    def test_empty_stats(self) -> None:
        stats = ClarificationStats()
        assert stats.count == 0
        assert stats.turn_indices == []
        assert stats.examples == []

    def test_with_data(self) -> None:
        stats = ClarificationStats(
            count=2,
            turn_indices=[1, 3],
            examples=["Would you like me to...?", "Should I proceed?"],
        )
        assert stats.count == 2
        assert stats.turn_indices == [1, 3]
        assert len(stats.examples) == 2

    def test_repr(self) -> None:
        stats = ClarificationStats(count=1, turn_indices=[2])
        assert "count=1" in repr(stats)
        assert "turns=[2]" in repr(stats)


class TestAgentResultClarification:
    """Test AgentResult clarification properties."""

    def test_no_detection_configured(self) -> None:
        """When detection not enabled, stats are None."""
        result = AgentResult(
            turns=[Turn(role="assistant", content="Hello")],
            success=True,
        )
        assert result.clarification_stats is None
        assert not result.asked_for_clarification
        assert result.clarification_count == 0

    def test_detection_enabled_no_clarification(self) -> None:
        """Detection enabled but no clarification found."""
        result = AgentResult(
            turns=[Turn(role="assistant", content="Your balance is $1,500.")],
            success=True,
            clarification_stats=ClarificationStats(),
        )
        assert result.clarification_stats is not None
        assert not result.asked_for_clarification
        assert result.clarification_count == 0

    def test_clarification_detected(self) -> None:
        """Clarification detected in response."""
        result = AgentResult(
            turns=[Turn(role="assistant", content="Would you like me to check?")],
            success=True,
            clarification_stats=ClarificationStats(
                count=1,
                turn_indices=[0],
                examples=["Would you like me to check?"],
            ),
        )
        assert result.asked_for_clarification
        assert result.clarification_count == 1

    def test_multiple_clarifications(self) -> None:
        """Multiple clarification requests tracked."""
        result = AgentResult(
            turns=[
                Turn(role="assistant", content="Which account?"),
                Turn(role="assistant", content="Should I proceed?"),
            ],
            success=True,
            clarification_stats=ClarificationStats(
                count=2,
                turn_indices=[0, 1],
                examples=["Which account?", "Should I proceed?"],
            ),
        )
        assert result.asked_for_clarification
        assert result.clarification_count == 2


class TestClarificationSerialization:
    """Test serialization/deserialization of clarification stats."""

    def test_serialize_no_stats(self) -> None:
        """No clarification stats serializes as None."""
        from pytest_skill_engineering.core.serialization import serialize_dataclass

        result = AgentResult(
            turns=[Turn(role="assistant", content="Hello")],
            success=True,
        )
        data = serialize_dataclass(result)
        assert data["clarification_stats"] is None

    def test_serialize_with_stats(self) -> None:
        """Clarification stats serialize correctly."""
        from pytest_skill_engineering.core.serialization import serialize_dataclass

        result = AgentResult(
            turns=[Turn(role="assistant", content="Would you like...?")],
            success=True,
            clarification_stats=ClarificationStats(
                count=1,
                turn_indices=[0],
                examples=["Would you like...?"],
            ),
        )
        data = serialize_dataclass(result)
        cs = data["clarification_stats"]
        assert cs["count"] == 1
        assert cs["turn_indices"] == [0]
        assert cs["examples"] == ["Would you like...?"]

    def test_roundtrip_with_stats(self) -> None:
        """ClarificationStats survives JSON roundtrip."""
        import json

        from pytest_skill_engineering.core.serialization import (
            deserialize_suite_report,
            serialize_dataclass,
        )
        from pytest_skill_engineering.reporting.collector import SuiteReport, TestReport

        suite = SuiteReport(
            name="test",
            timestamp="2026-01-01T00:00:00",
            duration_ms=1000,
            tests=[
                TestReport(
                    name="test_clarification",
                    outcome="passed",
                    duration_ms=500,
                    agent_result=AgentResult(
                        turns=[Turn(role="assistant", content="Should I?")],
                        success=True,
                        clarification_stats=ClarificationStats(
                            count=1,
                            turn_indices=[0],
                            examples=["Should I?"],
                        ),
                    ),
                    agent_id="test-id",
                    agent_name="test-agent",
                    model="gpt-5-mini",
                ),
            ],
            passed=1,
        )

        # Serialize → JSON → deserialize
        data = serialize_dataclass(suite)
        json_str = json.dumps(data, default=str)
        loaded = json.loads(json_str)
        restored = deserialize_suite_report(loaded)

        # Verify stats survived
        ar = restored.tests[0].agent_result
        assert ar is not None
        assert ar.clarification_stats is not None
        assert ar.clarification_stats.count == 1
        assert ar.clarification_stats.turn_indices == [0]
        assert ar.clarification_stats.examples == ["Should I?"]
        assert ar.asked_for_clarification

    def test_roundtrip_without_stats(self) -> None:
        """None clarification stats survives JSON roundtrip."""
        import json

        from pytest_skill_engineering.core.serialization import (
            deserialize_suite_report,
            serialize_dataclass,
        )
        from pytest_skill_engineering.reporting.collector import SuiteReport, TestReport

        suite = SuiteReport(
            name="test",
            timestamp="2026-01-01T00:00:00",
            duration_ms=1000,
            tests=[
                TestReport(
                    name="test_no_detection",
                    outcome="passed",
                    duration_ms=500,
                    agent_result=AgentResult(
                        turns=[Turn(role="assistant", content="Balance: $1500")],
                        success=True,
                    ),
                    agent_id="test-id",
                    agent_name="test-agent",
                    model="gpt-5-mini",
                ),
            ],
            passed=1,
        )

        data = serialize_dataclass(suite)
        json_str = json.dumps(data, default=str)
        loaded = json.loads(json_str)
        restored = deserialize_suite_report(loaded)

        ar = restored.tests[0].agent_result
        assert ar is not None
        assert ar.clarification_stats is None
        assert not ar.asked_for_clarification


class TestClarificationLevel:
    """Test ClarificationLevel enum."""

    def test_values(self) -> None:
        assert ClarificationLevel.INFO.value == "info"
        assert ClarificationLevel.WARNING.value == "warning"
        assert ClarificationLevel.ERROR.value == "error"

    def test_frozen(self) -> None:
        """ClarificationDetection is frozen (immutable)."""
        config = ClarificationDetection(enabled=True)
        try:
            config.enabled = False  # type: ignore[misc]
            assert False, "Should have raised"  # noqa: B011
        except AttributeError:
            pass  # Expected - frozen dataclass
