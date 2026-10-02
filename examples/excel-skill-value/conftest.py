from __future__ import annotations

import pytest
from checks import budget


def pytest_addoption(parser):
    parser.addoption("--run-live", action="store_true")
    parser.addoption("--prove-excel", action="store_true")
    parser.addoption("--paid-limit", type=int, default=4)
    parser.addoption("--prior-attempts", type=int, default=0)
    parser.addoption("--receipt-dir")
    parser.addoption("--skill-profile", choices=("broad", "formatting"), default="broad")


def pytest_collection_modifyitems(config, items):
    live = [item for item in items if item.get_closest_marker("copilot")]
    if not config.getoption("--run-live"):
        for item in live:
            item.add_marker(pytest.mark.skip(reason="Paid comparison requires --run-live"))
        return
    if config.getoption("--aitest-iterations", default=1) != 1:
        raise pytest.UsageError("This example permits one attempt per case; do not add iterations")
    budget(
        len(live),
        config.getoption("--prior-attempts"),
        config.getoption("--paid-limit"),
    )
