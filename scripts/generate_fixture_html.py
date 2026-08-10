#!/usr/bin/env python3
"""Generate HTML and Markdown reports from JSON test fixtures.

This script generates HTML and Markdown reports from all JSON fixtures in
tests/fixtures/reports/ to verify template rendering across different scenarios.

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
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from pytest_skill_engineering.cli import load_suite_report  # noqa: E402
from pytest_skill_engineering.reporting.generator import (  # noqa: E402
    generate_html as _generate_html,
)
from pytest_skill_engineering.reporting.generator import generate_md as _generate_md  # noqa: E402
from tests.fixtures.report_fixtures import (  # noqa: E402
    ALL_REPORT_SPECS,
    DOCS_REPORTS_DIR,
    FIXTURE_JSON_DIR,
    write_fixture_json,
)

OUTPUT_DIR = DOCS_REPORTS_DIR


def generate_fixture_html(json_path: Path, output_dir: Path) -> list[Path]:
    """Generate HTML and Markdown from a JSON fixture.

    Args:
        json_path: Path to JSON fixture
        output_dir: Directory to write reports

    Returns:
        List of paths to generated files (HTML and MD)

    Raises:
        ValueError: If insights are missing from the JSON fixture
    """
    # Load the fixture (returns 2-tuple: report, insights)
    report, insights = load_suite_report(json_path)

    if not insights:
        msg = f"Fixture {json_path.name} has no AI insights — insights are mandatory for reports"
        raise ValueError(msg)

    generated = []

    # Generate HTML
    html_path = output_dir / f"{json_path.stem}.html"
    _generate_html(report, html_path, insights=insights)
    generated.append(html_path)

    # Generate Markdown
    md_path = output_dir / f"{json_path.stem}.md"
    _generate_md(report, md_path, insights=insights)
    generated.append(md_path)

    return generated


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate HTML reports from JSON test fixtures")
    parser.add_argument(
        "--open", "-o", action="store_true", help="Open generated HTML files in browser"
    )
    parser.add_argument(
        "--fixture",
        "-f",
        type=str,
        help="Generate specific fixture (e.g., '01', '04_agent_selector', or 'hero-report')",
    )
    parser.add_argument(
        "--output",
        "-d",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )

    args = parser.parse_args(argv)

    if args.fixture:
        specs = [
            spec
            for spec in ALL_REPORT_SPECS
            if spec.name == args.fixture or spec.name.startswith(args.fixture)
        ]
        if not specs:
            print(f"No fixture matching '{args.fixture}' found in manifest")
            return 1
    else:
        specs = list(ALL_REPORT_SPECS)

    print(f"Generating report artifacts for {len(specs)} fixture(s)...")

    generated = []
    errors = []

    for spec in specs:
        output_dir = args.output if args.output != OUTPUT_DIR else spec.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"  {spec.name} ({spec.generator_source})...", end=" ")
        try:
            json_path = write_fixture_json(spec)
            paths = generate_fixture_html(json_path, output_dir)
            names = ", ".join(p.name for p in paths)
            print(f"OK -> {names}")
            generated.extend(paths)
        except Exception as e:
            import traceback

            print(f"ERROR: {e}")
            traceback.print_exc()
            errors.append((spec.name, e))

    print(f"\nGenerated: {len(generated)}, Errors: {len(errors)}")
    print(f"JSON fixtures refreshed in {FIXTURE_JSON_DIR}")

    if errors:
        print("\nErrors:")
        for name, error in errors:
            print(f"  {name}: {error}")

    # Open in browser if requested (HTML files only)
    if args.open and generated:
        html_files = [p for p in generated if p.suffix == ".html"]
        print(f"\nOpening {len(html_files)} HTML file(s) in browser...")
        for html_path in html_files:
            if sys.platform == "win32":
                subprocess.run(["start", str(html_path)])
            elif sys.platform == "darwin":
                subprocess.run(["open", str(html_path)])
            else:
                subprocess.run(["xdg-open", str(html_path)])

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
