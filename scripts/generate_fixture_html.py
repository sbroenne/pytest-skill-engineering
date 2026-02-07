#!/usr/bin/env python3
"""Generate HTML reports from JSON test fixtures.

This script generates HTML reports from all JSON fixtures in tests/fixtures/reports/
to verify template rendering across different scenarios.

Usage:
    python scripts/generate_fixture_html.py              # Generate all
    python scripts/generate_fixture_html.py --open       # Generate and open in browser
    python scripts/generate_fixture_html.py --fixture 01 # Generate specific fixture
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Add src to path for imports
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from pytest_aitest.cli import load_suite_report  # noqa: E402
from pytest_aitest.reporting.generator import generate_html as _generate_html  # noqa: E402

FIXTURES_DIR = ROOT / "tests" / "fixtures" / "reports"
# Output to docs/reports for public viewing (tracked in git)
OUTPUT_DIR = ROOT / "docs" / "reports"


def generate_fixture_html(json_path: Path, output_dir: Path) -> Path:
    """Generate HTML from a JSON fixture.

    Args:
        json_path: Path to JSON fixture
        output_dir: Directory to write HTML

    Returns:
        Path to generated HTML file
    """
    # Load the fixture (returns 2-tuple: report, insights)
    report, insights = load_suite_report(json_path)

    # Generate HTML
    output_path = output_dir / f"{json_path.stem}.html"
    _generate_html(report, output_path, insights=insights)

    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate HTML reports from JSON test fixtures")
    parser.add_argument(
        "--open", "-o", action="store_true", help="Open generated HTML files in browser"
    )
    parser.add_argument(
        "--fixture",
        "-f",
        type=str,
        help="Generate specific fixture (e.g., '01' for 01_single_agent.json)",
    )
    parser.add_argument(
        "--output",
        "-d",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )

    args = parser.parse_args(argv)

    # Ensure output directory exists
    args.output.mkdir(parents=True, exist_ok=True)

    # Find fixtures to process
    if args.fixture:
        fixtures = list(FIXTURES_DIR.glob(f"{args.fixture}*.json"))
        if not fixtures:
            print(f"No fixture matching '{args.fixture}' found in {FIXTURES_DIR}")
            return 1
    else:
        fixtures = sorted(FIXTURES_DIR.glob("*.json"))

    if not fixtures:
        print(f"No JSON fixtures found in {FIXTURES_DIR}")
        return 1

    print(f"Generating HTML for {len(fixtures)} fixture(s)...")

    generated = []
    errors = []

    for json_path in fixtures:
        print(f"  {json_path.name}...", end=" ")
        try:
            html_path = generate_fixture_html(json_path, args.output)
            print(f"OK -> {html_path.name}")
            generated.append(html_path)
        except Exception as e:
            import traceback

            print(f"ERROR: {e}")
            traceback.print_exc()
            errors.append((json_path, e))

    print(f"\nGenerated: {len(generated)}, Errors: {len(errors)}")

    if errors:
        print("\nErrors:")
        for path, error in errors:
            print(f"  {path.name}: {error}")

    # Open in browser if requested
    if args.open and generated:
        print(f"\nOpening {len(generated)} file(s) in browser...")
        for html_path in generated:
            if sys.platform == "win32":
                subprocess.run(["start", str(html_path)])
            elif sys.platform == "darwin":
                subprocess.run(["open", str(html_path)])
            else:
                subprocess.run(["xdg-open", str(html_path)])

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
