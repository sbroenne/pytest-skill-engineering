---
description: "Choose between Agent + aitest_run (synthetic) and CopilotAgent + copilot_run (real Copilot SDK). Understand the trade-offs for MCP server testing, skill testing, and end-to-end Copilot validation."
---

# Choosing a Test Harness

pytest-skill-engineering provides two test harnesses. Picking the right one upfront saves significant debugging time.

## The Two Harnesses

Both harnesses can test MCP servers, tools, and skills. The difference is **what runs the agent**.

| | `Agent` + `aitest_run` | `CopilotAgent` + `copilot_run` |
|---|---|---|
| **What runs the agent** | PydanticAI synthetic loop | Real GitHub Copilot (CLI SDK) |
| **LLM** | Any provider (Azure, OpenAI, `copilot/...`) | GitHub Copilot only |
| **Model setup** | You configure provider, API keys, deployments | None — Copilot subscription is all you need |
| **MCP connections** | Made directly by the test process | Managed by Copilot CLI |
| **MCP auth** | You supply tokens (env vars / headers) | Copilot CLI handles OAuth automatically |
| **Skill loading** | Injected as virtual reference tools | Native Copilot skill loading (`SKILL.md`) |
| **Custom agent loading** | `Agent.from_agent_file()` (prompt as system_prompt) | `load_custom_agent()` + `custom_agents=[]` (native subagent dispatch) |
| **Model control** | Swap any model per test | Always Copilot's active model |
| **Per-call introspection** | Full (tool name, args, timing) | Summary (tool names, final response) |
| **Speed** | Fast (in-process) | Slower (~5–10s CLI startup per test) |
| **Install** | `pip install pytest-skill-engineering` | `pip install pytest-skill-engineering[copilot]` |
| **Copilot subscription** | Not required | Required (`gh auth login`) |

---

## Use `Agent` + `aitest_run` when…

You want **full control** over the test loop — pick any model, compare variants, introspect every tool call. The test process owns the MCP connections directly.

```python
from pytest_skill_engineering import Agent, Provider, MCPServer

server = MCPServer(command=["python", "my_server.py"])

agent = Agent(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[server],
)

async def test_tool_is_called(aitest_run):
    result = await aitest_run(agent, "What's my checking balance?")
    assert result.tool_was_called("get_balance")
```

**Best for:**
- Iterating on tool descriptions, schemas, and custom agent instructions
- A/B testing: compare models, prompt variants, or server versions against each other
- Fast, cheap unit-level tests in CI/CD
- Full per-call introspection (tool name, args, call count)

**Limitations:**
- MCP servers that require OAuth (e.g. Power BI) need explicit token management
- Does not test how Copilot itself loads or prioritises skills
- Synthetic loop differs from how a real Copilot session behaves

---

## Use `CopilotAgent` + `copilot_run` when…

You want to test **what users actually experience** — the real Copilot CLI drives the session, MCP OAuth is handled automatically, and skills are loaded natively. Any MCP server reachable by Copilot CLI (via `~/.copilot/mcp-config.json` or passed directly) is available.

```python
from pytest_skill_engineering.copilot import CopilotAgent

async def test_skill_presents_scenarios(copilot_run):
    agent = CopilotAgent(
        name="with-skill",
        skill_directories=["skills/my-skill"],  # loads SKILL.md natively
        max_turns=10,
    )
    result = await copilot_run(agent, "What can you help me with?")
    assert result.success
    assert "scenario-a" in result.final_response.lower()
```

**Best for:**
- Testing the exact experience your users get in Copilot
- **Zero model setup** — no API keys, no Azure deployments, no provider config; just `gh auth login`
- All MCP servers configured in Copilot CLI — OAuth handled automatically where needed
- Native Copilot skill loading (`SKILL.md`, `skill_directories`)
- Multi-turn agent routing, memory, and subagent dispatch
- End-to-end regression testing before publishing a skill

**Limitations:**
- Requires a GitHub Copilot subscription and `gh auth login`
- Slower to start (CLI process startup ~5-10s per test)
- Less control over individual tool call assertions (no per-turn introspection)
- Cannot swap LLM provider — always uses Copilot's active model

---

## Quick Decision Flowchart

```
Do you want to test the exact experience your users get in Copilot?
    YES → CopilotAgent + copilot_run

Do your MCP servers use OAuth managed by Copilot CLI (Power BI, GitHub…)?
    YES → CopilotAgent + copilot_run

Are you loading a native Copilot skill (SKILL.md)?
    YES → CopilotAgent + copilot_run

Do you need to compare multiple models or prompt variants?
    YES → Agent + aitest_run

Are you running in CI without a Copilot subscription?
    YES → Agent + aitest_run

Do you need full per-call introspection (args, call count, timing)?
    YES → Agent + aitest_run
```

---

## Can I use both in the same project?

Yes. A common pattern is:

- **`Agent` + `aitest_run`** for fast, cheap unit-level MCP server tests
- **`CopilotAgent` + `copilot_run`** for integration/regression tests of the full skill

```
tests/
├── unit/
│   └── test_mcp_tools.py      # Agent + aitest_run — fast, no Copilot needed
└── integration/
    └── test_skill.py          # CopilotAgent + copilot_run — full end-to-end
```

Run them separately in CI:

```bash
# Fast unit tests (no Copilot subscription needed)
pytest tests/unit/

# Integration tests (requires gh auth login or GITHUB_TOKEN)
pytest tests/integration/
```

---

## The `copilot/` model prefix — a third option

If you want `Agent` + `aitest_run` (synthetic loop, direct MCP connections) but want to use a Copilot-accessible model instead of Azure/OpenAI, use the `copilot/` prefix:

```python
Agent(
    provider=Provider(model="copilot/claude-opus-4.6"),
    mcp_servers=[my_server],
)
```

This routes LLM calls through the Copilot SDK but keeps the PydanticAI agent loop and your own MCP connections. **This is not the same as `CopilotAgent`** — the Copilot CLI does not manage MCP or skill loading. You still need to handle MCP auth yourself.

Use this when: you want synthetic-loop control + Copilot's model catalogue, without a separate Azure/OpenAI subscription.
