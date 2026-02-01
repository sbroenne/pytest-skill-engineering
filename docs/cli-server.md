# CLI Server

Wrap command-line tools as MCP-like servers for testing CLI-based interfaces.

## Quick Start

```python
from pytest_aitest import CLIServer

@pytest.fixture(scope="module")
def git_server():
    return CLIServer(
        name="git-cli",
        command="git",
        tool_prefix="git",  # Creates "git_execute" tool
    )
```

## How It Works

The CLI server wraps any command-line tool and exposes it as a single tool that accepts arguments:

1. **Creates a tool**: `{tool_prefix}_execute` that accepts an `args` parameter
2. **Discovers usage**: Runs `--help` automatically to include in tool description
3. **Returns structured output**: JSON with `exit_code`, `stdout`, `stderr`

```python
# The LLM calls the tool like this:
git_execute(args="status --porcelain")
git_execute(args="log -n 5 --oneline")
```

## Configuration Options

```python
CLIServer(
    name="git-cli",             # Server identifier (required)
    command="git",              # CLI executable (required)
    tool_prefix="git",          # Tool name prefix (default: command name)
    shell="bash",               # Shell to use (optional)
    cwd="/path/to/repo",        # Working directory (optional)
    env={"KEY": "value"},       # Environment variables (optional)
    discover_help=True,         # Run help flag for description (default: True)
    help_flag="--help",         # Flag to get help text (default: --help)
    description=None,           # Custom description (overrides help discovery)
)
```

| Option | Description | Default |
|--------|-------------|---------|
| `name` | Server identifier | Required |
| `command` | CLI executable to wrap | Required |
| `tool_prefix` | Prefix for generated tool name | Command name |
| `shell` | Shell to run commands in | Auto-detect |
| `cwd` | Working directory | Current directory |
| `env` | Environment variables | `{}` |
| `discover_help` | Run help flag for tool description | `True` |
| `help_flag` | Flag to get help text | `--help` |
| `description` | Custom tool description | `None` |

## Shell Selection

The shell is auto-detected based on platform:

| Platform | Default | Available |
|----------|---------|-----------|
| Linux/macOS | `bash` | `bash`, `sh`, `zsh` |
| Windows | `powershell` | `powershell`, `pwsh`, `cmd` |

```python
# Explicit shell selection
CLIServer(
    name="dir-cli",
    command="dir",
    tool_prefix="dir",
    shell="cmd",  # Use cmd.exe on Windows
)
```

## Help Discovery

By default, the CLI server runs `{command} --help` at startup and includes the output in the tool description. This helps the LLM understand how to use the CLI.

```python
# Help text included automatically (default)
CLIServer(
    name="kubectl",
    command="kubectl",
    tool_prefix="k8s",
)

# Custom help flag for CLIs that use -h instead of --help
CLIServer(
    name="custom-cli",
    command="my-tool",
    tool_prefix="tool",
    help_flag="-h",
)

# Disable help discovery for faster startup
CLIServer(
    name="fast-cli",
    command="fast-tool",
    tool_prefix="fast",
    discover_help=False,
)
```

Help text is truncated to 2000 characters to avoid token bloat.

## Custom Description

For CLIs where auto-discovery doesn't work well, provide a custom description:

```python
# Custom description overrides help discovery
CLIServer(
    name="legacy-cli",
    command="legacy-tool",
    tool_prefix="legacy",
    description="""
    Manages legacy data files.
    
    Commands:
    - list: List all records
    - get <id>: Get a specific record
    - delete <id>: Delete a record
    - export <format>: Export data (json, csv)
    """,
    discover_help=False,  # Skip help discovery when using custom description
)

## Tool Output Format

Tool results are JSON with structured output:

```json
{
  "exit_code": 0,
  "stdout": "M README.md\nA new-file.txt",
  "stderr": ""
}
```

This allows the LLM to:
- Check if the command succeeded (`exit_code == 0`)
- Parse the output (`stdout`)
- Handle errors (`stderr`)

## Complete Examples

### Testing Git CLI

```python
import pytest
from pytest_aitest import Agent, CLIServer, Provider

@pytest.fixture(scope="module")
def git_server():
    return CLIServer(
        name="git-cli",
        command="git",
        tool_prefix="git",
        cwd="/path/to/repo",
    )

@pytest.fixture
def git_agent(git_server):
    return Agent(
        provider=Provider(model="azure/gpt-5-mini"),
        cli_servers=[git_server],
        system_prompt="You are a git assistant.",
        max_turns=5,
    )

@pytest.mark.asyncio
async def test_git_status(aitest_run, git_agent):
    result = await aitest_run(git_agent, "What's the repo status?")
    
    assert result.success
    assert result.tool_was_called("git_execute")

@pytest.mark.asyncio
async def test_git_log(aitest_run, git_agent):
    result = await aitest_run(git_agent, "Show me the last 3 commits")
    
    assert result.success
    assert result.tool_was_called("git_execute")
    assert "commit" in result.final_response.lower()
```

### Testing with Environment Variables

```python
@pytest.fixture(scope="module")
def docker_server():
    return CLIServer(
        name="docker-cli",
        command="docker",
        tool_prefix="docker",
        env={
            "DOCKER_HOST": "unix:///var/run/docker.sock",
            "DOCKER_CONFIG": "/home/user/.docker",
        },
    )
```

### Windows CLI with PowerShell

```python
@pytest.fixture(scope="module")
def excel_server():
    return CLIServer(
        name="excel-cli",
        command="excel-cli",
        tool_prefix="excel",
        shell="powershell",
        cwd="C:\\Workbooks",
    )
```

### Combining with MCP Servers

```python
@pytest.fixture(scope="module")
def filesystem_server():
    return MCPServer(
        command=["npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        wait=Wait.for_tools(["read_file", "write_file"]),
    )

@pytest.fixture(scope="module")
def grep_server():
    return CLIServer(
        name="grep-cli",
        command="grep",
        tool_prefix="search",
    )

@pytest.fixture
def hybrid_agent(filesystem_server, grep_server):
    return Agent(
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[filesystem_server],
        cli_servers=[grep_server],
        system_prompt="You can read/write files and search content.",
        max_turns=10,
    )
```

## Asserting on CLI Results

### Basic Assertions

```python
@pytest.mark.asyncio
async def test_cli_workflow(aitest_run, cli_agent):
    result = await aitest_run(cli_agent, "List all Python files")
    
    assert result.success
    assert result.tool_was_called("ls_execute")
    assert ".py" in result.final_response
```

### Using AI Judge

For semantic validation of CLI output:

```python
@pytest.mark.asyncio
async def test_cli_with_judge(aitest_run, cli_agent, judge):
    result = await aitest_run(cli_agent, "Show the git log")
    
    assert result.success
    assert judge(result.final_response, """
        - Shows commit hashes
        - Shows commit messages
        - Lists multiple commits
    """)
```

## Troubleshooting

### Command Not Found

Ensure the CLI is in the PATH or use the full path:

```python
CLIServer(
    name="my-cli",
    command="/usr/local/bin/my-tool",  # Full path
    tool_prefix="tool",
)
```

### Help Discovery Fails

If `--help` doesn't work for your CLI, disable it:

```python
CLIServer(
    name="my-cli",
    command="my-tool",
    tool_prefix="tool",
    discover_help=False,
)
```

### Working Directory Issues

Use absolute paths for `cwd`:

```python
from pathlib import Path

CLIServer(
    name="my-cli",
    command="my-tool",
    tool_prefix="tool",
    cwd=str(Path(__file__).parent / "workspace"),
)
```
