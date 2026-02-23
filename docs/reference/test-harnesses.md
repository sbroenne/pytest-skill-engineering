---
description: "Built-in Todo and Banking MCP test servers for validating LLM behavior without external dependencies."
---

# Test Harnesses

Built-in MCP servers for testing LLM behavior without external dependencies.

## Available Servers

| Server | Use Case | State |
|--------|----------|-------|
| `TodoStore` | CRUD operations | Stateful |
| `BankingService` | Multi-turn sessions, financial workflows | Stateful |

## TodoStore

Stateful task management for testing CRUD operations.

### Use Case

- Testing state changes across calls
- Multi-step workflows (add → complete → delete)
- Testing agent's ability to track IDs

### Tools

| Tool | Description |
|------|-------------|
| `add_task` | Create a new task |
| `complete_task` | Mark task as done |
| `delete_task` | Remove a task |
| `list_tasks` | List tasks (optional filtering) |
| `get_task` | Get task by ID |
| `update_task` | Update task properties |

### Example

```python
import sys
from pytest_skill_engineering import Eval, Provider, MCPServer, Wait
from pytest_skill_engineering.testing import TodoStore

@pytest.fixture(scope="module")
def todo_server():
    return MCPServer(
        command=[sys.executable, "-m", "pytest_skill_engineering.testing.todo_mcp"],
        wait=Wait.for_tools(["add_task", "list_tasks", "complete_task"]),
    )

@pytest.fixture
def todo_agent(todo_server):
    return Eval.from_instructions(
        "todo",
        "You are a task management assistant.",
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[todo_server],
    )

async def test_add_and_complete(eval_run, todo_agent):
    result = await eval_run(
        todo_agent,
        "Add a task: Buy groceries"
    )
    assert result.tool_was_called("add_task")
    
    result = await eval_run(
        todo_agent,
        "Mark the groceries task as done"
    )
    assert result.tool_was_called("complete_task")
```

### Direct Usage

```python
from pytest_skill_engineering.testing import TodoStore

store = TodoStore()

result = store.add_task("Buy groceries", priority="high")
task_id = result.value["id"]

result = store.complete_task(task_id)
assert result.success

result = store.list_tasks()
print(result.value["tasks"])
```

## BankingService

Stateful banking service for multi-turn session testing.

### Use Case

- Multi-turn conversations with state changes
- Session-based workflows (check balance → transfer → verify)
- Testing context retention across conversation turns
- Complex prompts requiring multiple tool calls

### Tools

| Tool | Description |
|------|-------------|
| `get_balance` | Get balance for one account |
| `get_all_balances` | Get balances for all accounts |
| `transfer` | Move money between accounts |
| `deposit` | Deposit money into an account |
| `withdraw` | Withdraw money from an account |
| `get_transactions` | View transaction history |

### Initial State

| Account | Balance |
|---------|---------|
| Checking | $1,500.00 |
| Savings | $3,000.00 |

### Example

```python
import sys
from pytest_skill_engineering import Eval, Provider, MCPServer, Wait

@pytest.fixture(scope="module")
def banking_server():
    return MCPServer(
        command=[sys.executable, "-m", "pytest_skill_engineering.testing.banking_mcp"],
        wait=Wait.for_tools(["get_balance", "transfer", "get_transactions"]),
    )

@pytest.mark.session("banking-workflow")
class TestBankingWorkflow:
    """Tests share conversation context via session decorator."""

    async def test_check_balance(self, eval_run, banking_server):
        agent = Eval.from_instructions(
            "banking",
            "You are a banking assistant.",
            provider=Provider(model="azure/gpt-5-mini"),
            mcp_servers=[banking_server],
        )
        
        result = await eval_run(agent, "What's my checking balance?")
        assert result.tool_was_called("get_balance")

    async def test_transfer_funds(self, eval_run, banking_server):
        agent = Eval.from_instructions(
            "banking",
            "You are a banking assistant.",
            provider=Provider(model="azure/gpt-5-mini"),
            mcp_servers=[banking_server],
        )
        
        result = await eval_run(
            agent,
            "Transfer $500 from checking to savings"
        )
        assert result.tool_was_called("transfer")
```

### Direct Usage

```python
from pytest_skill_engineering.testing.banking import BankingService

service = BankingService()

result = service.get_balance("checking")
print(result.value)  # {"account": "checking", "balance": 1500.0, ...}

result = service.transfer("checking", "savings", 500.0)
assert result.success

result = service.get_all_balances()
print(result.value["total_formatted"])  # "$4,500.00"
```

## Creating Custom Test Servers

### 1. Create a Store Class

```python
from dataclasses import dataclass
from pytest_skill_engineering.testing.types import ToolResult

@dataclass
class MyStore:
    state: dict = None
    
    def __post_init__(self):
        self.state = self.state or {}
    
    def my_tool(self, arg: str) -> ToolResult:
        """Do something."""
        return ToolResult(
            success=True,
            value={"result": arg.upper()},
        )
```

### 2. Create MCP Server Wrapper

```python
from mcp.server import Server
from mcp.types import Tool, TextContent

def create_my_server(store: MyStore | None = None):
    store = store or MyStore()
    server = Server("my-server")
    
    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name="my_tool",
                description="Do something with input",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "arg": {"type": "string"},
                    },
                    "required": ["arg"],
                },
            ),
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        if name == "my_tool":
            result = store.my_tool(arguments["arg"])
            return [TextContent(type="text", text=str(result.value))]
        raise ValueError(f"Unknown tool: {name}")
    
    return server
```

### 3. Use in Tests

```python
@pytest.fixture(scope="module")
def my_server():
    return create_my_server()

async def test_my_tool(eval_run, agent_with_my_server):
    result = await eval_run(agent_with_my_server, "Use my tool")
    assert result.tool_was_called("my_tool")
```

## Best Practices

| Server | Best For | Avoid |
|--------|----------|-------|
| `TodoStore` | CRUD workflows | Extremely complex logic |
| `BankingService` | Financial workflows, sessions | Stateless tests |
