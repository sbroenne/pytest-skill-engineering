"""Bridge between Anthropic's skill-creator eval format and pytest-skill-engineering.

Loads evals/evals.json from skill directories and converts them to test cases
that can be parametrized with pytest and validated with llm_assert.

Example:
    cases = load_skill_evals("skills/my-skill/")

    @pytest.mark.parametrize("case", cases, ids=lambda c: c.name)
    async def test_skill(eval_run, llm_assert, mcp_server, case):
        agent = Eval.from_plugin("skills/my-skill/", ...)
        result = await eval_run(agent, case.prompt)
        for expectation in case.expectations:
            assert llm_assert(result.final_response, expectation)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class SkillEvalCase:
    """A single eval case from skill-creator's evals/evals.json.

    Attributes:
        id: Numeric identifier from the eval file
        name: Human-readable name derived from the prompt
        prompt: The user prompt to send to the agent
        expected_output: Description of expected result (for documentation)
        expectations: Semantic assertions to validate against the response
        files: Paths to files referenced by this eval case
    """

    id: int
    name: str
    prompt: str
    expected_output: str | None = None
    expectations: tuple[str, ...] = ()
    files: tuple[str, ...] = ()


def load_skill_evals(skill_path: Path | str) -> list[SkillEvalCase]:
    """Load eval cases from a skill-creator compatible skill directory.

    Looks for evals/evals.json in the skill directory and parses it
    into SkillEvalCase objects for use with pytest parametrize.

    Args:
        skill_path: Path to skill directory containing evals/evals.json,
            or direct path to evals.json

    Returns:
        List of eval cases

    Raises:
        FileNotFoundError: If evals/evals.json doesn't exist
        ValueError: If the JSON format is invalid
    """
    evals_file = _resolve_evals_path(skill_path)

    raw = evals_file.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {evals_file}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {evals_file}, got {type(data).__name__}")
    if "evals" not in data:
        raise ValueError(f"Missing required 'evals' array in {evals_file}")
    if not isinstance(data["evals"], list):
        raise ValueError(f"'evals' must be an array in {evals_file}")

    cases: list[SkillEvalCase] = []
    for i, entry in enumerate(data["evals"]):
        cases.append(_parse_eval_entry(entry, i, evals_file))

    return cases


def has_skill_evals(skill_path: Path | str) -> bool:
    """Check if a skill directory has skill-creator evals."""
    path = Path(skill_path)
    if path.is_file():
        path = path.parent
    return (path / "evals" / "evals.json").exists()


def _resolve_evals_path(skill_path: Path | str) -> Path:
    """Resolve skill_path to the evals/evals.json file."""
    path = Path(skill_path)

    if path.is_file() and path.name == "evals.json":
        evals_file = path
    elif path.is_dir():
        evals_file = path / "evals" / "evals.json"
    else:
        raise FileNotFoundError(f"Invalid skill path: {path}")

    if not evals_file.exists():
        raise FileNotFoundError(f"evals/evals.json not found: {evals_file}")

    return evals_file


def _parse_eval_entry(entry: dict, index: int, source: Path) -> SkillEvalCase:
    """Parse a single eval entry from the JSON array."""
    if not isinstance(entry, dict):
        raise ValueError(f"Eval entry {index} must be an object in {source}")

    # Required fields
    eval_id = entry.get("id")
    if eval_id is None:
        raise ValueError(f"Eval entry {index} missing required field 'id' in {source}")

    prompt = entry.get("prompt")
    if not prompt or not isinstance(prompt, str):
        raise ValueError(f"Eval entry {index} missing required field 'prompt' in {source}")

    # Optional fields
    expected_output = entry.get("expected_output")
    expectations_raw = entry.get("expectations", [])
    files_raw = entry.get("files", [])

    if not isinstance(expectations_raw, list):
        raise ValueError(f"Eval entry {index}: 'expectations' must be an array in {source}")
    if not isinstance(files_raw, list):
        raise ValueError(f"Eval entry {index}: 'files' must be an array in {source}")

    name = _slugify_prompt(prompt, eval_id)

    return SkillEvalCase(
        id=int(eval_id),
        name=name,
        prompt=prompt,
        expected_output=expected_output if isinstance(expected_output, str) else None,
        expectations=tuple(str(e) for e in expectations_raw),
        files=tuple(str(f) for f in files_raw),
    )


def _slugify_prompt(prompt: str, eval_id: int) -> str:
    """Generate a human-readable test name from a prompt.

    Takes the first 50 characters, lowercases, replaces non-alphanumeric
    with hyphens, and prepends the eval id.
    """
    slug = prompt[:50].lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    if not slug:
        return f"eval-{eval_id}"
    return f"{eval_id}-{slug}"
