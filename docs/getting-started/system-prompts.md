# System Prompts

System prompts define agent behavior. Test different prompts to find what works.

## Adding a System Prompt

```python
agent = Agent(
    provider=Provider(model="azure/gpt-5-mini"),
    mcp_servers=[weather_server],
    system_prompt="You are a weather assistant. Be concise and direct.",
)
```

## How Prompts Affect Behavior

Different system prompts produce different behaviors:

| System Prompt | Behavior |
|---------------|----------|
| "Be concise." | Short, direct answers |
| "Explain your reasoning." | Verbose, step-by-step responses |
| "Use bullet points." | Structured output format |
| "If unsure, ask clarifying questions." | More cautious, interactive |

The system prompt affects both the *quality* of responses and the *cost* (longer prompts → more tokens).

## System Prompt vs Agent Skill

| Aspect | System Prompt | Agent Skill |
|--------|---------------|-------------|
| Purpose | Define behavior | Provide domain knowledge |
| Content | Instructions | Reference material |
| Example | "Be concise" | "Temperature chart..." |
| Parameter | `system_prompt=` | `skill=` |

You can use both together. The skill content is prepended to the system prompt.

## Loading System Prompts from Files

Store prompts as plain `.md` files for easier management:

```
prompts/
├── concise.md      # "Be brief. One sentence max."
├── detailed.md     # "Explain your reasoning step by step."
└── structured.md   # "Use bullet points for clarity."
```

Load them with `load_system_prompts()`:

```python
from pathlib import Path
from pytest_aitest import load_system_prompts

# Returns dict[str, str]: {"concise": "Be brief...", "detailed": "Explain..."}
PROMPTS = load_system_prompts(Path("prompts/"))
```

## Comparing Prompts

Test different prompts to find what works best:

```python
from pathlib import Path
from pytest_aitest import Agent, Provider, load_system_prompts

PROMPTS = load_system_prompts(Path("prompts/"))

@pytest.mark.parametrize("name,system_prompt", PROMPTS.items())
async def test_weather_query(aitest_run, weather_server, name, system_prompt):
    agent = Agent(
        provider=Provider(model="azure/gpt-5-mini"),
        mcp_servers=[weather_server],
        system_prompt=system_prompt,
    )
    result = await aitest_run(agent, "What's the weather in Paris?")
    assert result.success
```

The report auto-detects that system prompts vary and shows a comparison.

## Next Steps

- [Agent Skills](skills.md) — Add domain knowledge
- [Comparing Configurations](comparing.md) — Systematic comparison patterns
