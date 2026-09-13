"""Report-only identities shared by rendered reports and analysis statistics."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_skill_engineering.reporting.collector import TestReport


@dataclass(slots=True, frozen=True)
class ReportIdentity:
    agent_id: str
    display_name: str


def build_report_identities(tests: list[TestReport]) -> dict[int, ReportIdentity]:
    """Map test objects to configuration groups without changing recorded identity."""
    groups: dict[str, dict[str, list[TestReport]]] = defaultdict(lambda: defaultdict(list))
    for test in tests:
        for field in ("agent_id", "eval_name", "model"):
            if not getattr(test, field):
                raise ValueError(f"Test {test.name!r} missing '{field}'")
        result = test.eval_result
        key = json.dumps(
            {
                "agent_id": test.agent_id,
                "eval_name": test.eval_name,
                "model": test.model,
                "system_prompt_name": test.system_prompt_name,
                "skill_name": test.skill_name,
                "configuration": result.configuration if result is not None else None,
                "system_prompt": result.effective_system_prompt if result is not None else None,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        groups[test.agent_id][key].append(test)

    identities: dict[int, ReportIdentity] = {}
    for runtime_id, variants in groups.items():
        labels: dict[str, list[str]] = defaultdict(list)
        for key, cases in sorted(variants.items()):
            test = cases[0]
            label = test.eval_name
            if len(variants) > 1:
                label = f"{label} [{test.model}]"
            labels[label].append(key)
        for label, keys in labels.items():
            for index, key in enumerate(keys, start=1):
                display_name = label
                if len(keys) > 1:
                    display_name = f"{label} (configuration {index})"
                report_id = runtime_id
                if len(variants) > 1:
                    report_id = "report-" + hashlib.sha256(key.encode("utf-8")).hexdigest()
                identity = ReportIdentity(agent_id=report_id, display_name=display_name)
                for test in variants[key]:
                    identities[id(test)] = identity
    return identities
