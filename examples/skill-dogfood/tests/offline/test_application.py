"""Free checks of the sample's fixtures and independent criteria."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from skill_dogfood.application import inspect_cli, seed_application
from skill_dogfood.workflow import prepare_historical_skill, validate_authored_test


def test_historical_guidance_is_exact_and_not_distributed_as_a_skill(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[4]
    fixture = root / "examples" / "skill-dogfood" / "fixtures" / "retired-companion"
    hashes = {
        "instructions.txt": "4654291384d760eecc26b3a00d901934a6da62e346c84702878e595147318f32",
        "references/test-patterns.txt": (
            "c7a0a3f29f77810e73302db3e16a05f520e686314d9557a05905bf41d8903549"
        ),
        "references/investigation.txt": (
            "4e63160356cb8be441136da8dbd18413784d8c9a1809cee5089a41f07344f727"
        ),
    }
    for name, expected in hashes.items():
        assert hashlib.sha256((fixture / name).read_bytes()).hexdigest() == expected
    assert not (fixture / "SKILL.md").exists()
    assert not (root / "skills" / "pytest-skill-engineering" / "SKILL.md").exists()
    skill = prepare_historical_skill(root, tmp_path)
    assert (
        hashlib.sha256((skill / "SKILL.md").read_bytes()).hexdigest() == hashes["instructions.txt"]
    )
    for name in ("test-patterns.md", "investigation.md"):
        assert (skill / "references" / name).read_bytes() == (
            fixture / "references" / Path(name).with_suffix(".txt")
        ).read_bytes()


def test_starting_application_exposes_the_rounding_fault(tmp_path: Path) -> None:
    project = tmp_path / "consumer"
    seed_application(project)
    observed = inspect_cli(project)
    assert [(case["subtotal"], case["tax_percent"]) for case in observed if not case["passed"]] == [
        ("0.05", "10"),
        ("0.25", "10"),
    ]


def test_fixed_checks_accept_correct_rounding_and_all_input_rules(tmp_path: Path) -> None:
    project = tmp_path / "consumer"
    seed_application(project)
    source = project / "invoice_cli.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace("ROUND_HALF_EVEN", "ROUND_HALF_UP"),
        encoding="utf-8",
    )
    assert all(case["passed"] for case in inspect_cli(project))


def test_authored_test_can_use_standard_future_annotations(tmp_path: Path) -> None:
    test = tmp_path / "test_invoice.py"
    test.write_text(
        "from __future__ import annotations\n\n"
        "async def test_invoice(copilot_eval, invoice_eval, invoice_task, invoice_output):\n"
        "    result = await copilot_eval(invoice_eval, invoice_task)\n"
        "    assert result.success\n"
        "    assert invoice_output()['total_cents'] == 6\n",
        encoding="utf-8",
    )
    validate_authored_test(test)


def test_authored_test_allows_fingerprint_checks_and_plain_assertion_helpers(
    tmp_path: Path,
) -> None:
    test = tmp_path / "test_checkout.py"
    test.write_text(
        "from hashlib import sha256\n\n"
        "def assert_money(actual, expected):\n"
        "    assert actual == expected\n\n"
        "async def test_checkout(copilot_eval, checkout_eval, checkout_task, checkout_inputs):\n"
        "    result = await copilot_eval(checkout_eval, checkout_task)\n"
        "    assert_money(result.success, True)\n"
        "    assert sha256(checkout_inputs['order.csv']['csv_text'].encode()).hexdigest()\n",
        encoding="utf-8",
    )
    validate_authored_test(test)


@pytest.mark.parametrize(
    "source",
    [
        "import pytest\n@pytest.mark.parametrize('amount', [1, 2])\n"
        "async def test_checkout(copilot_eval, checkout_eval, checkout_task, amount):\n"
        "    await copilot_eval(checkout_eval, checkout_task)\n",
        "from pathlib import Path\n"
        "async def test_checkout(copilot_eval, checkout_eval, checkout_task):\n"
        "    await copilot_eval(checkout_eval, checkout_task)\n"
        "    Path('order.csv').read_bytes()\n",
        "import pytest\n@pytest.fixture\n"
        "def checkout_eval():\n    return None\n"
        "async def test_checkout(copilot_eval, checkout_eval, checkout_task):\n"
        "    await copilot_eval(checkout_eval, checkout_task)\n",
    ],
)
def test_authored_tests_cannot_add_paid_cases_or_override_trusted_inputs(
    tmp_path: Path, source: str
) -> None:
    test = tmp_path / "test_checkout.py"
    test.write_text(source, encoding="utf-8")
    with pytest.raises(ValueError):
        validate_authored_test(test)


@pytest.mark.parametrize(
    "source",
    [
        "import copilot\nasync def test_invoice():\n    pass\n",
        "import subprocess\nasync def test_invoice():\n    pass\n",
        "import pytest\n@pytest.mark.skip\nasync def test_invoice():\n    pass\n",
        "async def test_invoice():\n    open('invoice_cli.py', 'w')\n",
        "async def test_invoice():\n    pass\n",
    ],
)
def test_authored_tests_cannot_replace_the_execution_boundary(
    tmp_path: Path,
    source: str,
) -> None:
    test = tmp_path / "test_invoice.py"
    test.write_text(source, encoding="utf-8")
    with pytest.raises(ValueError):
        validate_authored_test(test)
