from __future__ import annotations

from typing import NoReturn

import copilot
import pytest

import pytest_skill_engineering.copilot.client as framework_client


@pytest.fixture(autouse=True)
def forbid_model_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("Offline checks must not create a Copilot client")

    monkeypatch.setattr(copilot, "CopilotClient", forbidden)
    monkeypatch.setattr(framework_client, "CopilotClient", forbidden)
