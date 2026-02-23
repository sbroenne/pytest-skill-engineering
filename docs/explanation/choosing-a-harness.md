---
description: "Choose between Eval + eval_run (synthetic) and CopilotEval + copilot_eval (real Copilot SDK). Understand the trade-offs for MCP server testing, skill testing, and end-to-end Copilot validation."
---

# Choosing a Test Harness

pytest-skill-engineering provides two test harnesses. Picking the right one upfront saves significant debugging time.

## The Two Harnesses

Both harnesses can test MCP servers, tools, and skills. The difference is **what runs the agent**.

| | `Eval` + `eval_run` | `CopilotEval` + `copilot_eval` |
|---|---|---|
| **What runs the agent** | PydanticAI synthetic loop | Real GitHub Copilot (CLI SDK) |
| **LLM** | Any provider (Azure, OpenAI, `copilot/...`) | GitHub Copilot only |
| **Model setup** | You configure provider, API keys, deployments | None — Copilot subscription is all you need |
| **MCP connections** | Made directly by the test process | Managed by Copilot CLI |
| **MCP auth** | You supply tokens (env vars / headers) | Copilot CLI handles OAuth automatically |
| **Skill loading** | Injected as virtual reference tools | Native Copilot skill loading (`SKILL.md`) |
| **Custom agent loading** | `Eval.from_agent_file()` (loads instructions as system prompt) | `load_custom_agent()` + `custom_agents=[]` (native Copilot dispatch) |
| **Cost tracking** | USD per test (via litellm pricing + `pricing.toml` overrides) | Premium requests (Copilot billing units) |
| **Model control** | Swap any model per test | Always Copilot's active model |
| **Per-call introspection** | Full (tool name, args, timing) | Summary (tool names, final response) |
| **Speed** | Fast (in-process) | Slower (~5–10s CLI startup per test) |
| **Install** | `uv add pytest-skill-engineering` | `uv add pytest-skill-engineering[copilot]` |
| **Copilot subscription** | Not required | Required (`gh auth login`) |

---

## Use `Eval` + `eval_run` when…

You want **full control** over the test loop — pick any model, compare variants, introspect every tool call. The test process owns the MCP connections directly.

```python
from pytest_skill_engineering import Eval, Provider, MCPServer

server = MCPServer(command=["python", "my_server.py"])

agent = Eval(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[server],
)

async def test_tool_is_called(eval_run):
    result = await eval_run(agent, "What's my checking balance?")
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

## Use `CopilotEval` + `copilot_eval` when…

You want to test **what users actually experience** — the real Copilot CLI drives the session, MCP OAuth is handled automatically, and skills are loaded natively. Any MCP server reachable by Copilot CLI (via `~/.copilot/mcp-config.json` or passed directly) is available.

```python
from pytest_skill_engineering.copilot import CopilotEval

async def test_skill_presents_scenarios(copilot_eval):
    agent = CopilotEval(
        name="with-skill",
        skill_directories=["skills/my-skill"],  # loads SKILL.md natively
        max_turns=10,
    )
    result = await copilot_eval(agent, "What can you help me with?")
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
    YES → CopilotEval + copilot_eval

Do your MCP servers use OAuth managed by Copilot CLI (Power BI, GitHub…)?
    YES → CopilotEval + copilot_eval

Are you loading a native Copilot skill (SKILL.md)?
    YES → CopilotEval + copilot_eval

Do you need to compare multiple models or prompt variants?
    YES → Eval + eval_run

Are you running in CI without a Copilot subscription?
    YES → Eval + eval_run

Do you need full per-call introspection (args, call count, timing)?
    YES → Eval + eval_run
```

---

## Can I use both in the same project?

Yes. A common pattern is:

- **`Eval` + `eval_run`** for fast, cheap unit-level MCP server tests
- **`CopilotEval` + `copilot_eval`** for integration/regression tests of the full skill

```
tests/
├── unit/
│   └── test_mcp_tools.py      # Eval + eval_run — fast, no Copilot needed
└── integration/
    └── test_skill.py          # CopilotEval + copilot_eval — full end-to-end
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

If you want `Eval` + `eval_run` (synthetic loop, direct MCP connections) but want to use a Copilot-accessible model instead of Azure/OpenAI, use the `copilot/` prefix:

```python
Eval(
    provider=Provider(model="copilot/claude-opus-4.6"),
    mcp_servers=[my_server],
)
```

This routes LLM calls through the Copilot SDK but keeps the PydanticAI agent loop and your own MCP connections. **This is not the same as `CopilotEval`** — the Copilot CLI does not manage MCP or skill loading. You still need to handle MCP auth yourself.

Use this when: you want synthetic-loop control + Copilot's model catalogue, without a separate Azure/OpenAI subscription.
