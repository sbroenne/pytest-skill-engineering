"""Registration of the execution-only plugin options."""

from __future__ import annotations

from _pytest.config.argparsing import Parser

from pytest_skill_engineering.plugin_options import add_aitest_options


def test_only_execution_evidence_options_are_registered() -> None:
    parser = Parser()
    group = parser.getgroup("aitest")
    add_aitest_options(group)
    assert [option.names()[0] for option in group.options] == [
        "--aitest-json",
        "--aitest-min-pass-rate",
        "--aitest-iterations",
    ]
