"""Save and load native execution evidence without interpreting it."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

from pytest_skill_engineering.core.serialization import (
    deserialize_suite_report,
    serialize_dataclass,
)
from pytest_skill_engineering.reporting.schema import REPORT_SCHEMA_VERSION

if TYPE_CHECKING:
    from pytest_skill_engineering.reporting.collector import SuiteReport


def generate_json(report: SuiteReport, output_path: str | Path) -> None:
    """Atomically save recorded evidence and pytest outcomes as JSON.

    Property values must be JSON-compatible. Unsupported values are errors,
    not opportunities to replace evidence with string representations.
    """
    data = serialize_dataclass(report)
    data["schema_version"] = REPORT_SCHEMA_VERSION
    content = json.dumps(data, indent=2)
    destination = Path(output_path)
    with NamedTemporaryFile(
        dir=destination.parent, prefix=f".{destination.name}.", delete=False
    ) as stream:
        temporary = Path(stream.name)
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def load_suite_report(path: str | Path) -> SuiteReport:
    """Load current-schema native evidence; never infer results or grade answers."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Execution evidence must be a JSON object")
    if data.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported schema version: {data.get('schema_version')!r}. "
            f"Only {REPORT_SCHEMA_VERSION} is supported. Re-run the producer "
            "with the current package to save new evidence."
        )
    if "insights" in data:
        raise ValueError("AI insights are not part of execution evidence")
    return deserialize_suite_report(data)
