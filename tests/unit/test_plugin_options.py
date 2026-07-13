"""Tests for pytest CLI option registration."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from _pytest.config import Config
from _pytest.config.argparsing import Argument, Parser
from _pytest.pytester import Pytester

from pytest_skill_engineering.plugin_options import add_aitest_options

pytest_plugins = ["pytester"]


@dataclass(slots=True, frozen=True)
class OptionSpec:
    """Expected metadata for a registered pytest option."""

    name: str
    default: str | int | bool | None
    dest: str
    expected_type: type[int] | None = None
    action_name: str = "_StoreAction"
    metavar: str | None = None


OPTION_SPECS = [
    OptionSpec("--aitest-summary-model", None, "aitest_summary_model"),
    OptionSpec(
        "--aitest-analysis-prompt",
        None,
        "aitest_analysis_prompt",
        metavar="PATH",
    ),
    OptionSpec(
        "--aitest-summary-compact",
        False,
        "aitest_summary_compact",
        action_name="_StoreTrueAction",
    ),
    OptionSpec(
        "--aitest-print-analysis-prompt",
        False,
        "aitest_print_analysis_prompt",
        action_name="_StoreTrueAction",
    ),
    OptionSpec("--aitest-html", None, "aitest_html", metavar="PATH"),
    OptionSpec("--aitest-json", None, "aitest_json", metavar="PATH"),
    OptionSpec("--aitest-md", None, "aitest_md", metavar="PATH"),
    OptionSpec(
        "--aitest-min-pass-rate",
        None,
        "aitest_min_pass_rate",
        expected_type=int,
        metavar="N",
    ),
    OptionSpec(
        "--aitest-iterations",
        1,
        "aitest_iterations",
        expected_type=int,
        metavar="N",
    ),
    OptionSpec("--llm-model", "copilot/gpt-5.4-mini", "llm_model"),
    OptionSpec("--llm-vision-model", None, "llm_vision_model"),
]


def _registered_options() -> dict[str, Argument]:
    """Register the plugin options on a real parser and return them by name."""

    parser = Parser(_ispytest=True)
    group = parser.getgroup("aitest", "AI agent testing")
    add_aitest_options(group)
    return {option.names()[0]: option for option in group.options}


def _parse_config(pytester: Pytester, *args: str) -> Config:
    """Parse pytest config with only the aitest plugin explicitly loaded."""

    return pytester.parseconfig("-p", "no:aitest", "-p", "pytest_skill_engineering.plugin", *args)


class TestAddAitestOptionsRegistration:
    """Tests for direct option registration on a pytest OptionGroup."""

    def test_registers_all_expected_options_in_order(self) -> None:
        """All documented CLI options are registered exactly once."""

        registered = _registered_options()
        assert list(registered) == [spec.name for spec in OPTION_SPECS]

    @pytest.mark.parametrize("spec", OPTION_SPECS, ids=lambda spec: spec.name)
    def test_registers_expected_metadata(self, spec: OptionSpec) -> None:
        """Each option keeps its declared default, type, action, and dest."""

        option = _registered_options()[spec.name]

        assert option.default == spec.default
        assert option.dest == spec.dest
        assert option.type is spec.expected_type
        assert type(option._action).__name__ == spec.action_name
        assert option._action.metavar == spec.metavar


class TestAddAitestOptionsConfig:
    """Tests for option values on a real pytest Config object."""

    @pytest.mark.parametrize("spec", OPTION_SPECS, ids=lambda spec: spec.name)
    def test_defaults_flow_through_to_config(
        self,
        pytester: Pytester,
        spec: OptionSpec,
    ) -> None:
        """Omitted CLI flags resolve to the registered default values."""

        config = _parse_config(pytester)
        assert config.getoption(spec.name) == spec.default

    def test_cli_values_override_store_option_defaults(self, pytester: Pytester) -> None:
        """Explicit CLI values replace defaults for value-taking options."""

        config = _parse_config(
            pytester,
            "--aitest-summary-model=copilot/gpt-5.5",
            "--aitest-analysis-prompt=custom-analysis.md",
            "--aitest-html=report.html",
            "--aitest-json=results.json",
            "--aitest-md=report.md",
            "--aitest-min-pass-rate=80",
            "--aitest-iterations=3",
            "--llm-model=copilot/gpt-5.5",
            "--llm-vision-model=copilot/gpt-4.1",
        )

        assert config.getoption("--aitest-summary-model") == "copilot/gpt-5.5"
        assert config.getoption("--aitest-analysis-prompt") == "custom-analysis.md"
        assert config.getoption("--aitest-html") == "report.html"
        assert config.getoption("--aitest-json") == "results.json"
        assert config.getoption("--aitest-md") == "report.md"
        assert config.getoption("--aitest-min-pass-rate") == 80
        assert config.getoption("--aitest-iterations") == 3
        assert config.getoption("--llm-model") == "copilot/gpt-5.5"
        assert config.getoption("--llm-vision-model") == "copilot/gpt-4.1"

    @pytest.mark.parametrize(
        ("flag_name", "dest"),
        [
            ("--aitest-summary-compact", "aitest_summary_compact"),
            ("--aitest-print-analysis-prompt", "aitest_print_analysis_prompt"),
        ],
    )
    def test_boolean_flags_default_false_and_flip_true(
        self,
        pytester: Pytester,
        flag_name: str,
        dest: str,
    ) -> None:
        """store_true options stay False by default and turn True when passed."""

        default_config = _parse_config(pytester)
        enabled_config = _parse_config(pytester, flag_name)

        assert default_config.getoption(flag_name) is False
        assert getattr(default_config.option, dest) is False
        assert enabled_config.getoption(flag_name) is True
        assert getattr(enabled_config.option, dest) is True

    def test_integer_options_are_parsed_as_ints(self, pytester: Pytester) -> None:
        """Integer-valued options are typed as ints instead of strings."""

        config = _parse_config(
            pytester,
            "--aitest-min-pass-rate=80",
            "--aitest-iterations=3",
        )

        min_pass_rate = config.getoption("--aitest-min-pass-rate")
        iterations = config.getoption("--aitest-iterations")

        assert min_pass_rate == 80
        assert iterations == 3
        assert isinstance(min_pass_rate, int)
        assert isinstance(iterations, int)
