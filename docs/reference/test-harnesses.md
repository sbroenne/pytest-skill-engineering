# Test Harnesses

Built-in MCP servers for testing agent behavior without external dependencies.

## Available Servers

| Server | Use Case | State |
|--------|----------|-------|
| `WeatherStore` | Basic tool usage | Stateless |
| `TodoStore` | CRUD operations | Stateful |
| `BankingService` | Multi-turn sessions | Stateful |

## WeatherStore

Mock weather data for testing natural language → tool usage.

### Use Case

- "Hello world" tests
- Testing tool selection
- Simple prompt → response validation

### Tools

| Tool | Description |
|------|-------------|
| `get_weather` | Get current weather for a city |
| `get_forecast` | Get multi-day forecast |
| `compare_weather` | Compare weather between cities |
| `list_cities` | List available cities |

### Available Cities

Paris, Tokyo, New York, Berlin, London, Sydney

### Example

```python
import sys
from pytest_aitest import Agent, Provider, MCPServer, Wait
from pytest_aitest.testing import WeatherStore

@pytest.fixture(scope="module")
def weather_server():
    return MCPServer(
        command=[sys.executable, "-m", "pytest_aitest.testing.weather_mcp"],
        wait=Wait.for_tools(["get_weather", "get_forecast", "list_cities"]),
    )

@pytest.fixture
def weather_agent(weather_server):
    return Agent(
        name="weather",
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[weather_server],
    )

async def test_weather(aitest_run, weather_agent):
    result = await aitest_run(
        weather_agent,
        "What's the weather in Paris?"
    )
    
    assert result.success
    assert result.tool_was_called("get_weather")
```

### Direct Usage

```python
from pytest_aitest.testing import WeatherStore

store = WeatherStore()

result = store.get_weather("Paris")
assert result.success
print(result.value)  # {"city": "Paris", "temperature_celsius": 18, ...}

result = store.get_forecast("Tokyo", days=3)
assert result.success
```

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
from pytest_aitest import Agent, Provider, MCPServer, Wait
from pytest_aitest.testing import TodoStore

@pytest.fixture(scope="module")
def todo_server():
    return MCPServer(
        command=[sys.executable, "-m", "pytest_aitest.testing.todo_mcp"],
        wait=Wait.for_tools(["add_task", "list_tasks", "complete_task"]),
    )

@pytest.fixture
def todo_agent(todo_server):
    return Agent(
        name="todo",
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[todo_server],
        system_prompt="You are a task management assistant.",
    )

async def test_add_and_complete(aitest_run, todo_agent):
    result = await aitest_run(
        todo_agent,
        "Add a task: Buy groceries"
    )
    assert result.tool_was_called("add_task")
    
    result = await aitest_run(
        todo_agent,
        "Mark the groceries task as done"
    )
    assert result.tool_was_called("complete_task")
```

### Direct Usage

```python
from pytest_aitest.testing import TodoStore

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
from pytest_aitest import Agent, Provider, MCPServer, Wait

@pytest.fixture(scope="module")
def banking_server():
    return MCPServer(
        command=[sys.executable, "-m", "pytest_aitest.testing.banking_mcp"],
        wait=Wait.for_tools(["get_balance", "transfer", "get_transactions"]),
    )

@pytest.mark.session("banking-workflow")
class TestBankingWorkflow:
    """Tests share conversation context via session decorator."""

    async def test_check_balance(self, aitest_run, banking_server):
        agent = Agent(
            name="banking",
            provider=Provider(model="azure/gpt-5-mini"),
            mcp_servers=[banking_server],
            system_prompt="You are a banking assistant.",
        )
        
        result = await aitest_run(agent, "What's my checking balance?")
        assert result.tool_was_called("get_balance")

    async def test_transfer_funds(self, aitest_run, banking_server):
        agent = Agent(
            name="banking",
            provider=Provider(model="azure/gpt-5-mini"),
            mcp_servers=[banking_server],
            system_prompt="You are a banking assistant.",
        )
        
        result = await aitest_run(
            agent,
            "Transfer $500 from checking to savings"
        )
        assert result.tool_was_called("transfer")
```

### Direct Usage

```python
from pytest_aitest.testing.banking import BankingService

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
from pytest_aitest.testing.types import ToolResult

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

async def test_my_tool(aitest_run, agent_with_my_server):
    result = await aitest_run(agent_with_my_server, "Use my tool")
    assert result.tool_was_called("my_tool")
```

## Best Practices

| Server | Best For | Avoid |
|--------|----------|-------|
| `WeatherStore` | Quick tests, demos | State-dependent tests |
| `TodoStore` | CRUD workflows | Extremely complex logic |
