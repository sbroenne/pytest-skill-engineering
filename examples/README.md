# Examples

Start with **[quickstart](quickstart/)**. It runs one real Copilot task against
the bundled Todo MCP server, checks the returned task state, and saves JSON.
The other examples demonstrate comparison methods and have offline defaults.

| Project | What it demonstrates | Requirements for live execution |
| --- | --- | --- |
| [Quickstart](quickstart/) | One task, ordinary assertions, and saved evidence | Python, uv, and Copilot access |
| [Write-run-fix-rerun workflow](skill-dogfood/) | An agent authors a test, observes a real failure, repairs a CLI, and reruns unchanged checks | Copilot access and approved isolation for generated code |
| [Excel skill comparison](excel-skill-value/) | MCP and CLI tasks with/without skills, checked through saved workbooks | Windows, desktop Excel, ExcelMcp executables, and Copilot access |

Live runs may consume premium requests. Follow each project's README: the
workflow sample has its own environment and lock, while the Excel example uses
the repository-root environment.

## Historical experiments

The workflow sample preserves the guidance from our
[companion-skill study](../docs/use-cases/companion-skill.md) as frozen test data.
That study did not demonstrate a benefit, so no framework companion skill ships.
Testing your own domain skills remains supported.

The [Excel study](../docs/use-cases/excel-skill-value.md) recorded equal
correctness and higher token usage with broad skills on its selected tasks.
The smaller runnable example demonstrates the method; it does not reproduce
the full historical workload or establish a benefit for new formatting skills.

Do not edit the historical guidance under either project's `fixtures`
directory. Those files are inputs to the experiments, not current product docs.

## Advanced framework scenarios

The repository's `tests/integration/copilot/` files cover model comparisons
(`test_02_models.py`), system prompts (`test_03_instructions.py`), skills
(`test_05_skills.py`), CLI workflows (`test_09_cli.py`), and custom agent dispatch
(`test_12_custom_agents.py`).

Those tests validate the framework itself. Use the quickstart as your first
consumer project rather than running the repository's integration suite.
