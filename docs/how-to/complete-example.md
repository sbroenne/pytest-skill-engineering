---
description: "Complete end-to-end example demonstrating all pytest-skill-engineering capabilities in a banking scenario: multi-eval testing, sessions, skills, and AI analysis."
---

# Complete Example: Tying It All Together

This guide walks through the **hero test suite** — a comprehensive example demonstrating all pytest-skill-engineering capabilities in a single, cohesive banking scenario.

!!! tip "Generate the Report"
    Run `pytest tests/showcase/ -v --aitest-html=report.html` to generate the hero report.

## The Scenario: Personal Finance Assistant

The hero test uses a **Banking MCP server** that simulates a personal finance application with:

- **2 accounts**: checking ($1,500), savings ($3,000)
- **6 tools**: `get_balance`, `get_all_balances`, `transfer`, `deposit`, `withdraw`, `get_transactions`

This realistic scenario lets us test how well an LLM can understand and coordinate multiple tools.

## Project Structure

```
tests/showcase/
├── test_hero.py           # The comprehensive test suite
├── conftest.py            # Shared fixtures
├── agents/                # Agent instruction files for comparison
│   ├── concise.agent.md
│   ├── detailed.agent.md
│   └── friendly.agent.md
└── skills/
    └── financial-advisor/ # Domain knowledge skill
        ├── SKILL.md
        └── references/
            └── budgeting-guide.md
```

## Running the Hero Tests

```bash
# Run all showcase tests with HTML report
pytest tests/showcase/ -v --aitest-html=docs/demo/hero-report.html

# Run a specific test class
pytest tests/showcase/test_hero.py::TestModelComparison -v
```

## 1. Basic Tool Usage

The simplest tests verify the agent can use individual tools correctly.

```python
class TestBasicOperations:
    """Basic single-tool operations demonstrating core functionality."""

    async def test_check_single_balance(self, copilot_eval):
        """Check balance of one account - simplest possible test."""
        agent = CopilotEval(
            name="banking-v1",
            instructions=BANKING_PROMPT_BASE,
        )

        result = await copilot_eval(agent, "What's my checking account balance?")

        assert result.success
        assert result.tool_was_called("get_balance")
```

**What this tests:**

- Can the LLM understand the user's intent?
- Does it select the correct tool (`get_balance`)?
- Does it pass valid parameters?

## 2. Multi-Tool Workflows

Complex operations require coordinating multiple tools in sequence.

```python
class TestMultiToolWorkflows:
    """Complex workflows requiring coordination of multiple tools."""

    async def test_transfer_and_verify(self, copilot_eval, llm_assert):
        """Transfer money and verify the result with balance check."""
        agent = CopilotEval(
            name="banking-v1",
            instructions=BANKING_PROMPT_BASE,
        )

        result = await copilot_eval(
            agent,
            "Transfer $100 from checking to savings, then show me my new balances.",
        )

        assert result.success
        # Should use multiple tools
        assert result.tool_was_called("transfer")
        assert result.tool_was_called("get_all_balances") or result.tool_was_called("get_balance")
        assert llm_assert(
            result.final_response,
            "shows updated balances after transfer",
        )
```

**What this tests:**

- Can the LLM break down a complex request?
- Does it call the right tools in sequence?
- Does it synthesize information coherently?

## 3. Multi-Turn Context

Context across turns is provided naturally through the conversation history in the LLM session.
Each test is independent — use explicit context in your prompts to test multi-step scenarios.

```python
async def test_plan_then_execute(self, copilot_eval, llm_assert):
    """Test that the agent can plan and then execute a savings transfer."""
    agent = CopilotEval(
        name="savings-planner",
        instructions=BANKING_PROMPT_BASE,
    )

    result = await copilot_eval(
        agent,
        "Check my account balances, identify the best opportunity to save more "
        "money, then transfer $200 to my savings account.",
    )

    assert result.success
    assert result.tool_was_called("transfer")
    assert llm_assert(
        result.final_response,
        "shows updated balances after transfer",
    )
```

**What this tests:**

- Can the LLM handle a compound instruction?
- Does it use tools in the right order?
- Does it synthesize the result coherently?

## 4. Model Comparison

Compare how different LLMs perform on the same task.

```python
BENCHMARK_MODELS = ["gpt-5-mini", "gpt-4.1-mini"]

class TestModelComparison:
    """Compare how different models handle complex financial advice."""

    @pytest.mark.parametrize("model", BENCHMARK_MODELS)
    async def test_financial_advice_quality(self, copilot_eval, llm_assert, model: str):
        """Compare models on providing comprehensive financial advice."""
        agent = CopilotEval(
            name="banking-v1",
            model=model,
            instructions=BANKING_PROMPT_BASE,
        )

        result = await copilot_eval(
            agent,
            "I want to reach my vacation savings goal faster. Analyze my current "
            "financial situation and recommend a concrete savings plan.",
        )

        assert result.success
        assert len(result.all_tool_calls) >= 1
        assert llm_assert(
            result.final_response,
            "provides actionable savings recommendations based on financial data",
        )
```

**What this tests:**

- Which model gives better financial advice?
- Which model uses tools more efficiently?
- Cost vs quality tradeoffs

The report automatically generates a **model comparison table** showing:

- Pass/fail rates per model
- Token usage and costs
- AI-generated recommendations

## 5. Agent Instruction Comparison

Compare how different agent instruction styles affect behavior.

Store each style as an `.agent.md` file:

```
tests/showcase/
└── agents/
    ├── concise.agent.md
    ├── detailed.agent.md
    └── friendly.agent.md
```

```markdown title="agents/concise.agent.md"
---
name: AGENT_CONCISE
description: Brief, to-the-point financial advice
---

You are a personal finance assistant. Be concise and direct.
Give specific numbers and actionable advice in 2-3 sentences.
```

```markdown title="agents/detailed.agent.md"
---
name: AGENT_DETAILED
description: Thorough financial analysis with explanations
---

You are a personal finance assistant. Provide comprehensive analysis.
Explain your reasoning, show calculations, and consider multiple scenarios.
```

Then parametrize tests over them:

```python
from pathlib import Path
from pytest_skill_engineering.copilot import CopilotEval
from pytest_skill_engineering.core.evals import load_custom_agent

AGENT_PATHS = list((Path(__file__).parent / "agents").glob("*.agent.md"))

class TestPromptComparison:
    """Compare how different agent instruction styles affect financial advice."""

    @pytest.mark.parametrize("agent_path", AGENT_PATHS, ids=lambda p: p.stem.replace(".agent", ""))
    async def test_advice_style_comparison(self, copilot_eval, llm_assert, agent_path):
        """Compare concise vs detailed vs friendly advisory styles."""
        agent = CopilotEval(
            name=agent_path.stem,
            custom_agents=[load_custom_agent(agent_path)],
        )

        result = await copilot_eval(
            agent,
            "I'm worried about my spending. Can you check my accounts "
            "and give me advice on managing my money better?",
        )

        assert result.success
        assert result.tool_was_called("get_all_balances") or result.tool_was_called("get_balance")
```

**What this tests:**

- Which prompt style produces better advice?
- How does verbosity affect user experience?
- Are there quality vs token tradeoffs?

## 6. Skill Integration

Skills inject domain knowledge into the agent's context.

First, create a skill:

```markdown title="skills/financial-advisor/SKILL.md"
---
name: financial-advisor
description: Financial planning and budgeting expertise
version: 1.0.0
---

# Financial Advisor Skill

You are an expert financial advisor with deep knowledge of:

## Emergency Fund Guidelines
- Minimum: 3 months of expenses
- Recommended: 6 months of expenses
- High-risk professions: 9-12 months

## Budget Allocation (50/30/20 Rule)
- 50% Needs: rent, utilities, groceries, minimum debt payments
- 30% Wants: entertainment, dining out, subscriptions
- 20% Savings: emergency fund, retirement, goals
```

Then use it in tests:

```python
class TestSkillEnhancement:
    """Test how skills improve financial advice quality."""

    async def test_with_financial_skill(
        self, copilot_eval, llm_assert, financial_advisor_skill
    ):
        """Eval with financial advisor skill should give better advice."""
        agent = CopilotEval(
            name="banking-v1",
            instructions=BANKING_PROMPT_BASE,
            skill_directories=["tests/showcase/skills/financial-advisor"],
        )

        result = await copilot_eval(
            agent,
            "I have $1500 in checking. Should I keep it there or move some to savings? "
            "What's a good emergency fund target for someone like me?",
        )

        assert result.success
        assert llm_assert(
            result.final_response,
            "provides financial advice about emergency funds or savings allocation",
        )
```

**What this tests:**

- Does domain knowledge improve advice quality?
- Does the agent apply the skill's guidelines?
- Are recommendations more concrete with skills?

## 7. Error Handling

Test graceful recovery from invalid operations.

```python
class TestErrorHandling:
    """Test graceful handling of edge cases and errors."""

    async def test_insufficient_funds_recovery(self, copilot_eval, llm_assert):
        """Eval should handle insufficient funds gracefully."""
        instructions = BANKING_PROMPT_BASE + " If an operation fails, explain why and suggest alternatives."
        agent = CopilotEval(
            name="banking-v1",
            instructions=instructions,
        )

        result = await copilot_eval(
            agent,
            "Transfer $50,000 from my checking to savings.",  # Way more than available!
        )

        assert result.success
        assert result.tool_was_called("transfer")
        assert llm_assert(
            result.final_response,
            "explains insufficient funds or suggests an alternative amount",
        )
```

**What this tests:**

- Does the agent attempt the operation?
- Does it handle tool errors gracefully?
- Does it provide helpful error messages?

## Key Takeaways

### Test Structure Best Practices

1. **One scenario, many tests** — Reuse the same test scenario across test classes
2. **Named agents for sessions** — Use `name="session-01"` to track multi-turn state
3. **Semantic assertions** — Use `llm_assert` for behavior verification
4. **Parametrize for comparisons** — Use `@pytest.mark.parametrize` for model/prompt grids

### Assertion Patterns

| Assertion | Purpose |
|-----------|---------|
| `result.success` | Eval completed without errors |
| `result.tool_was_called("name")` | Specific tool was invoked |
| `result.tool_call_count("name") >= N` | Tool called at least N times |
| `len(result.all_tool_calls) >= N` | Total tool calls threshold |
| `llm_assert(response, condition)` | Semantic response validation |

### Report Features

The generated report includes:

- **Model comparison tables** with cost/quality analysis
- **Prompt comparison** showing style differences
- **Session flow diagrams** for multi-turn tests
- **AI-powered insights** suggesting improvements
- **Failure analysis** with root cause identification

## Next Steps

- **[Test MCP Servers](test-mcp-servers.md)** — Deep dive into MCP server configuration
- **[Generate Reports](generate-reports.md)** — Customize report output
- **[Configuration Reference](../reference/configuration.md)** — All available options
