# Agent Skills

Skills are domain-specific knowledge modules that enhance agent capabilities. They follow the [agentskills.io](https://agentskills.io/specification) specification.

## Why Skills?

MCP servers and CLIs have two problems nobody talks about:

1. **Design** — Your tool descriptions, parameter names, and error messages are the entire API for LLMs. Getting them right is hard.
2. **Testing** — Traditional tests can't verify if an LLM can actually understand and use your tools.

**Skills solve the knowledge gap.** They provide:
- Domain expertise the LLM needs to use tools effectively
- Structured guidelines for consistent behavior
- Reference documents for specific thresholds/rules

## Quick Example

```python
from pytest_aitest import Agent, Provider, Skill

# Load a skill
skill = Skill.from_path("skills/weather-expert")

# Create agent with skill
agent = Agent(
    provider=Provider(model="azure/gpt-5-mini"),
    skill=skill,
    mcp_servers=[weather_server],
)

# Test it
result = await aitest_run(agent, "What should I pack for Paris?")
assert result.tool_was_called("get_weather")  # Skill ensures tools are used
```

## Skill Structure

A skill is a directory containing:

```
my-skill/
├── SKILL.md           # Required: metadata + instructions
└── references/        # Optional: on-demand documents
    ├── guide.md
    └── thresholds.md
```

### SKILL.md Format

```markdown
---
name: my-skill
description: What this skill does (max 1024 chars)
version: 1.0.0
license: MIT
tags:
  - category1
  - category2
---

# Skill Title

Instructions that get prepended to the agent's system prompt.

## Guidelines

1. Always do X before Y
2. Use tool Z when...
3. Never assume...
```

### Metadata Requirements

| Field | Required | Constraints |
|-------|----------|-------------|
| `name` | Yes | Lowercase letters, numbers, hyphens. 1-64 chars. Must start with letter. |
| `description` | Yes | Max 1024 characters |
| `version` | No | Semantic version string |
| `license` | No | SPDX license identifier |
| `tags` | No | List of categorization tags |

## Reference Documents

When a skill has a `references/` directory, two virtual tools are automatically injected:

| Tool | Description |
|------|-------------|
| `list_skill_references` | Returns available reference filenames |
| `read_skill_reference` | Reads a specific reference file by name |

This allows the agent to look up specific information on-demand rather than having everything in the system prompt.

**Example: Weather clothing guide**

```
weather-expert/
├── SKILL.md
└── references/
    └── clothing-guide.md  # Temperature thresholds, UV guidelines
```

The skill can instruct the agent:
> "Use `read_skill_reference` to look up specific clothing recommendations based on temperature ranges."

## Using Skills

### Loading Skills

```python
from pytest_aitest import Skill, load_skill

# From directory
skill = Skill.from_path("skills/my-skill")

# Or using the helper function
skill = load_skill("skills/my-skill")

# Access metadata
print(skill.name)           # "my-skill"
print(skill.description)    # "What this skill does"
print(skill.has_references) # True if references/ exists
```

### With agent_factory Fixture

```python
async def test_with_skill(agent_factory, skill_factory, aitest_run):
    skill = skill_factory("skills/my-skill")
    agent = agent_factory(skill=skill, system_prompt="Additional instructions")
    
    result = await aitest_run(agent, "Do something")
    assert result.success
```

### Skill + System Prompt Combination

When both skill and system_prompt are provided:
1. Skill content is prepended first
2. Agent's system_prompt follows

```python
agent = Agent(
    provider=provider,
    skill=weather_skill,                    # This comes first
    system_prompt="Be extremely concise.",  # This comes second
)
```

## Testing Skills

Skills improve testability by making agent behavior **predictable**. Here's the pattern:

### 1. Baseline Test (without skill)

```python
async def test_baseline_behavior(weather_agent_factory, aitest_run):
    """Document what the LLM does WITHOUT skill guidance."""
    agent = weather_agent_factory(
        "gpt-5-mini",
        system_prompt="You are a helpful assistant.",  # Minimal guidance
    )
    
    result = await aitest_run(agent, "What should I pack for Paris?")
    
    # Baseline: LLM might or might not check weather
    print(f"Tool calls: {len(result.all_tool_calls)}")
    # Don't assert on specific behavior - just document it
```

### 2. Skilled Test (with skill)

```python
async def test_skilled_behavior(agent_factory, skill_factory, aitest_run):
    """Verify skill IMPROVES agent behavior."""
    skill = skill_factory("skills/weather-expert")
    
    agent = agent_factory(skill=skill)
    agent.mcp_servers = [weather_server]
    
    result = await aitest_run(agent, "What should I pack for Paris?")
    
    # WITH skill: Should ALWAYS check weather first
    assert result.tool_was_called("get_weather"), "Skilled agent checks weather"
    
    # Response should include specific advice (not generic)
    assert "°" in result.final_response or "degrees" in result.final_response.lower()
```

### 3. Comparison Test

```python
async def test_skill_comparison(weather_agent_factory, agent_factory, skill_factory, aitest_run):
    """Side-by-side comparison proving skill value."""
    prompt = "What should I wear in London today?"
    
    # Without skill
    baseline = weather_agent_factory("gpt-5-mini", system_prompt="Help the user.")
    baseline_result = await aitest_run(baseline, prompt)
    
    # With skill
    skill = skill_factory("skills/weather-expert")
    skilled = agent_factory(skill=skill, mcp_servers=[weather_server])
    skilled_result = await aitest_run(skilled, prompt)
    
    print(f"Baseline tool calls: {len(baseline_result.all_tool_calls)}")
    print(f"Skilled tool calls:  {len(skilled_result.all_tool_calls)}")
    
    # The skilled agent should be more consistent
    assert skilled_result.tool_was_called("get_weather")
```

## Built-in Test Skills

pytest-aitest includes example skills in `tests/integration/skills/`:

### weather-expert

Teaches agents to:
- Always check weather tools before giving advice
- Give specific temperature-based recommendations
- Reference clothing guide for UV thresholds

```
tests/integration/skills/weather-expert/
├── SKILL.md
└── references/
    └── clothing-guide.md
```

### todo-organizer

Teaches agents to:
- Always verify operations with `list_tasks` after modifications
- Use consistent list names (inbox, work, personal, shopping, someday)
- Assign smart priorities based on urgency keywords

```
tests/integration/skills/todo-organizer/
├── SKILL.md
└── references/
    └── priority-guide.md
```

## API Reference

### Skill Class

```python
@dataclass
class Skill:
    path: Path              # Directory containing SKILL.md
    metadata: SkillMetadata # Parsed frontmatter
    content: str            # Markdown body (instructions)
    references: dict[str, str]  # filename -> content
    
    @property
    def name(self) -> str: ...
    
    @property
    def description(self) -> str: ...
    
    @property
    def has_references(self) -> bool: ...
    
    @classmethod
    def from_path(cls, path: Path | str) -> Skill: ...
```

### SkillMetadata Class

```python
@dataclass
class SkillMetadata:
    name: str
    description: str
    version: str | None = None
    license: str | None = None
    tags: tuple[str, ...] = ()
```

### Exceptions

```python
class SkillError(Exception):
    """Raised when skill loading or validation fails."""
```

## Best Practices

### 1. Be Specific in Instructions

❌ Bad: "Use tools appropriately"
✅ Good: "ALWAYS call `get_weather` before giving clothing advice"

### 2. Use References for Complex Data

Don't put large tables in the skill instructions. Use references:

```markdown
# SKILL.md
When asked about clothing, use `read_skill_reference("clothing-guide.md")` 
to look up temperature-specific recommendations.
```

### 3. Include Anti-Patterns

Tell the agent what NOT to do:

```markdown
## Anti-Patterns to Avoid
- ❌ Never guess weather data - always call the tool
- ❌ Don't give generic advice like "dress in layers"
- ❌ Don't skip verification after modifications
```

### 4. Test Both Behaviors

Always write:
1. A baseline test showing default LLM behavior
2. A skilled test proving improvement
3. Assertions on specific, measurable outcomes

### 5. Keep Skills Focused

One skill = one domain. Don't combine weather advice and task management in one skill.
