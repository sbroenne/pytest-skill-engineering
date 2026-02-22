---
description: "The system_prompt parameter on Eval — what it is and when to use it."
---

# System Prompts

The `system_prompt=` parameter on `Eval` directly sets the instructions passed to the LLM for a synthetic test. Use it when you want to write instructions inline rather than loading them from a file.

```python
agent = Eval(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[banking_server],
    system_prompt="You are a banking assistant. Be concise and direct.",
)
```

## When to use `system_prompt=`

Use `system_prompt=` directly when you're doing a quick synthetic test and don't have a custom agent file yet.

For anything more structured — a specialist agent with defined tools, description, and instructions — define a **custom agent file** instead. The file body is the system prompt, and you get versioning, reuse, and A/B testing for free.

```python
# Prefer this for real agents:
agent = Eval.from_agent_file(
    ".github/agents/banking-assistant.agent.md",
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[banking_server],
)
```

See [Custom Agents](custom-agents.md) for the full guide, including A/B testing agent instructions and real Copilot dispatch testing.

## System Prompt vs Eval Skill

| Aspect | System Prompt | Eval Skill |
|--------|---------------|-------------|
| Purpose | Define behavior | Provide domain knowledge |
| Content | Instructions | Reference material |
| Example | "Be concise" | "Account fee schedule..." |
| Parameter | `system_prompt=` | `skill=` |

You can use both together. The skill content is injected alongside the system prompt.

