
# pytest-skill-engineering

> **6** tests | **5** passed | **1** failed | **83%** pass rate  
> Duration: 75.7s | Cost: 🧪 $-0.016951 · 🤖 $0.0261 · 💰 $0.009104 | Tokens: 377–3,235  
> February 07, 2026 at 07:22 PM

*Three agents for testing the agent selector UI.*


## Agent Leaderboard


|#|Agent|Tests|Pass Rate|Tokens|Cost|Duration|
| :---: | :--- | :---: | :---: | ---: | ---: | ---: |
|🥇|gpt-5-mini 🏆|2/2|100%|3,448|$0.003737|31.1s|
|🥈|gpt-5-mini + financial-advisor|2/2|100%|4,908|$0.004823|33.3s|
|🥉|gpt-4.1-mini|1/2|50%|1,113|$0.000544|11.3s|



## AI Analysis

<div class="winner-card">
<div class="winner-title">Recommended for Deploy</div>
<div class="winner-name">gpt-5-mini</div>
<div class="winner-summary">Delivers a perfect pass rate with reliable tool usage and the lowest total cost among agents that handled multi-step financial queries correctly.</div>
<div class="winner-stats">
<div class="winner-stat"><span class="winner-stat-value green">100%</span><span class="winner-stat-label">Pass Rate</span></div>
<div class="winner-stat"><span class="winner-stat-value blue">$0.003737</span><span class="winner-stat-label">Total Cost</span></div>
<div class="winner-stat"><span class="winner-stat-value amber">3,448</span><span class="winner-stat-label">Tokens</span></div>
</div>
</div>

<div class="metric-grid">
<div class="metric-card green">
<div class="metric-value green">6</div>
<div class="metric-label">Total Tests</div>
</div>
<div class="metric-card red">
<div class="metric-value red">1</div>
<div class="metric-label">Failures</div>
</div>
<div class="metric-card blue">
<div class="metric-value blue">3</div>
<div class="metric-label">Agents</div>
</div>
<div class="metric-card amber">
<div class="metric-value amber">2.8</div>
<div class="metric-label">Avg Turns</div>
</div>
</div>

## Comparative Analysis

### Why the winner wins
- **100% pass rate at lower realized cost** than the skill-augmented variant while still correctly chaining `get_all_balances` for advice.
- **Decisive tool usage**: immediately fetches balances without asking permission, avoiding extra turns and failures.
- **Balanced verbosity**: provides actionable guidance without the token bloat seen in the skill variant.

### Notable patterns
- **Skill increases quality but costs more**: `gpt-5-mini + financial-advisor` adds structured advice and options, but at higher cost and tokens.
- **Permission-seeking hurts reliability**: `gpt-4.1-mini` asked the user to provide balances or permission instead of calling tools, causing the only failure.
- **Tool descriptions were clear enough**: failures stemmed from agent behavior, not tool ambiguity.

### Alternatives
- **gpt-5-mini + financial-advisor**: Same pass rate with richer financial guidance; trade-off is higher cost and tokens.
- **gpt-4.1-mini**: Lowest cost per run, but unreliable due to permission-seeking behavior; not recommended for autonomous tool-first workflows.

## ❌ Failure Analysis

### Failure Summary

**gpt-4.1-mini** (1 failure)

| Test | Root Cause | Fix |
|------|------------|-----|
| Financial advice — tests differentiation between agents (skill vs no skill). | Agent asked for user-provided balances instead of calling available tools. | Instruct the agent to proactively fetch balances when advice depends on account data. |

### Financial advice — tests differentiation between agents (skill vs no skill). (gpt-4.1-mini)
- **Problem:** The agent did not call `get_all_balances` or `get_balance`, causing the assertion failure.
- **Root Cause:** The system prompt allowed or encouraged deference to the user for data retrieval.
- **Behavioral Mechanism:** Language implying optionality (“If you want, I can retrieve…”) primed the model into permission-seeking mode, delaying action and skipping tool calls.
- **Fix:** Add explicit instruction:  
  > “When a user asks for advice that depends on account data, always call the appropriate balance tool immediately without asking for permission.”

## 🔧 MCP Tool Feedback

### banking_server
Overall, tools are discoverable and consistently used by compliant agents.

| Tool | Status | Calls | Issues |
|------|--------|-------|--------|
| get_balance | ✅ | 3 | Working well |
| get_all_balances | ✅ | 2 | Working well |

## 📝 System Prompt Feedback

### default prompt (mixed)
- **Token count:** Not provided
- **Behavioral impact:** Neutral wording allows model discretion; with `gpt-4.1-mini` this led to permission-seeking.
- **Problem:** Lacks a hard requirement to act autonomously.
- **Suggested change:**  
  > “Do not ask the user to provide information that can be retrieved via tools. Fetch required data first, then respond.”

### financial-advisor (effective with gpt-5-mini)
- **Token count:** Not provided
- **Behavioral impact:** Encourages structured, proactive financial guidance.
- **Problem:** Higher verbosity than necessary for tests.
- **Suggested change:** Remove optional exploratory prompts unless user asks for deeper planning.

## 📚 Skill Feedback

### financial-advisor (positive)
- **Usage rate:** High in advice responses
- **Token cost:** Increased vs no-skill agent
- **Problem:** Some boilerplate suggestions not required for test success.
- **Suggested change:** Split skill into “core rules” and “extended guidance” and load extended guidance only when requested.

## 💡 Optimizations

| # | Optimization | Priority | Estimated Savings |
|---|-------------|----------|-------------------|
| 1 | Enforce autonomous tool-first behavior | recommended | Avoids failures; fewer retries |
| 2 | Trim skill verbosity | suggestion | ~15% cost reduction |
| 3 | Compact tool responses | info | ~10–20 tokens per call |

#### 1. Enforce autonomous tool-first behavior (recommended)
- Current: Some agents ask permission before calling tools.
- Change: Add explicit system instruction to always fetch required data first.
- Impact: Reliability improvement; prevents test failures.

#### 2. Trim skill verbosity (suggestion)
- Current: Financial-advisor skill includes optional planning prompts.
- Change: Remove or gate extended advice.
- Impact: ~15% cost reduction.

#### 3. Compact tool responses (info)
- Current: Tool responses include both raw and formatted fields.
- Change: Return only one representation where possible.
- Impact: ~10–20 token savings per call.

## 📦 Tool Response Optimization

### get_all_balances (from banking_server)
- **Current response size:** Includes duplicate numeric and formatted strings.
- **Issues found:** Redundant `formatted` fields increase tokens.
- **Suggested optimization:** Return numeric balances only; format in the assistant.
- **Estimated savings:** ~20 tokens per call

**Example current vs optimized:**
```json
// Current
{
  "accounts": {
    "checking": {"balance": 1500.0, "formatted": "$1,500.00"},
    "savings": {"balance": 3000.0, "formatted": "$3,000.00"}
  },
  "total": 4500.0,
  "total_formatted": "$4,500.00"
}

// Optimized
{
  "accounts": {
    "checking": 1500.0,
    "savings": 3000.0
  },
  "total": 4500.0
}
```


## Test Results


### tests/fixtures/scenario_04_agent_selector.py


#### ✅ Basic balance query — all agents should pass.

<details>
<summary>✅ gpt-5-mini — 11.1s · 922 tokens · 3 turns · $0.000320</summary>

**Assertions:**

- ✅ `llm`: provides the current checking account balance amount

**Tool Calls:**


|Tool|Status|Args|
| :--- | :---: | :--- |
|`get_balance`|✅|account='checking'|


**Response:**

> Your checking account balance is $1,500.00. Would you like to do anything else with this account?

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant Tools

    User->>Agent: "What's my checking account balance?"
    Agent->>Tools: "get_balance({'account': 'checking'})"
    Tools-->>Agent: "{'account': 'checking', 'balance': 1500.0, 'formatted': '$1,"
    Agent->>User: "Your checking account balance is $1,500.00. Would you like to do anything else w"
```

</details>

<details>
<summary>✅ gpt-4.1-mini — 6.9s · 736 tokens · 3 turns · $0.000341</summary>

**Assertions:**

- ✅ `llm`: provides the current checking account balance amount

**Tool Calls:**


|Tool|Status|Args|
| :--- | :---: | :--- |
|`get_balance`|✅|account='checking'|


**Response:**

> Your checking account balance is $1,500.00. Is there anything else you would like to do?

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant Tools

    User->>Agent: "What's my checking account balance?"
    Agent->>Tools: "get_balance({'account': 'checking'})"
    Tools-->>Agent: "{'account': 'checking', 'balance': 1500.0, 'formatted': '$1,"
    Agent->>User: "Your checking account balance is $1,500.00. Is there anything else you would lik"
```

</details>

<details>
<summary>✅ gpt-5-mini + financial-advisor — 8.5s · 1,673 tokens · 3 turns · $0.000905</summary>

**Assertions:**

- ✅ `llm`: provides the current checking account balance amount

**Tool Calls:**


|Tool|Status|Args|
| :--- | :---: | :--- |
|`get_balance`|✅|account='checking'|


**Response:**

> Your checking account balance is $1,500.00.
> 
> Would you like me to:
> - Show your savings balance or recent transactions?
> - Transfer money between accounts or deposit/withdraw?
> - Help set up a budget or savings plan (emergency fund recommendations)?

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant Tools

    User->>Agent: "What's my checking account balance?"
    Agent->>Tools: "get_balance({'account': 'checking'})"
    Tools-->>Agent: "{'account': 'checking', 'balance': 1500.0, 'formatted': '$1,"
    Agent->>User: "Your checking account balance is $1,500.00. Would you like me to: - Show your sa"
```

</details>


#### ❌ Financial advice — tests differentiation between agents (ski… ⚡

<details>
<summary>✅ gpt-5-mini — 20.1s · 2,526 tokens · 3 turns · $0.003418</summary>

**Assertions:**

- ✅ `llm`: provides financial advice about fund allocation

**Tool Calls:**


|Tool|Status|Args|
| :--- | :---: | :--- |
|`get_all_balances`|✅||


**Response:**

> I pulled your balances: checking $1,500 and savings $3,000 (total $4,500).
> 
> I can give a useful recommendation, but to tailor it I need a couple quick facts:
> - Rough monthly living expenses (rent/mortgage, utilities, food, transport)
> - Any upcoming big payments (car, vacation, home down payment) in the next 12 months
> - Whether you have high‑interest debt or want to invest/retire sooner
> 
> Until then, here are clear, practical options you can choose from (I won’t move any money unless you ask me to

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant Tools

    User->>Agent: "I have money in checking and savings. How should I allocate my funds?"
    Agent->>Tools: "get_all_balances({})"
    Tools-->>Agent: "{'accounts': {'checking': {'balance': 1500.0, 'formatted': '"
    Agent->>User: "I pulled your balances: checking $1,500 and savings $3,000 (total $4,500). I can"
```

</details>

<details>
<summary>❌ gpt-4.1-mini — 4.5s · 377 tokens · 2 turns · $0.000202</summary>

**Error:** `      AssertionError: assert (False or False)
       +  where False = tool_was_called('get_all_balances')
       +    where tool_was_called = AgentResult(SUCCESS)\n  Turns: 2\n  Tools called: none\n  Duration: 1180ms\n  Tokens: 377 | Cost: $0.000202\n  Final: 'To provide you with a recommendation on how to allocate your funds between checking and savings, cou'....tool_was_called
       +  and   False = tool_was_called('get_balance')
       +    where tool_was_called = AgentResult(SUCCESS)\n  Turns: 2\n  Tools called: none\n  Duration: 1180ms\n  Tokens: 377 | Cost: $0.000202\n  Final: 'To provide you with a recommendation on how to allocate your funds between checking and savings, cou'....tool_was_called`

**Response:**

> To provide you with a recommendation on how to allocate your funds between checking and savings, could you please share your current balances in each account? If you want, I can retrieve your current balances for you.

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant Tools

    User->>Agent: "I have money in checking and savings. How should I allocate my funds?"
    Agent->>User: "To provide you with a recommendation on how to allocate your funds between check"
```

</details>

<details>
<summary>✅ gpt-5-mini + financial-advisor — 24.8s · 3,235 tokens · 3 turns · $0.003919</summary>

**Assertions:**

- ✅ `llm`: provides financial advice about fund allocation

**Tool Calls:**


|Tool|Status|Args|
| :--- | :---: | :--- |
|`get_all_balances`|✅||


**Response:**

> Thanks — I checked your accounts: you have $1,500 in checking and $3,000 in savings for a total of $4,500.
> 
> High-level recommendations (priority order)
> 1. Emergency fund first — 3–6 months of your essential expenses kept in savings (separate, ideally in a high‑yield savings account).
> 2. Pay down any high‑interest debt (credit cards, payday loans) once you have at least a small emergency buffer.
> 3. Contribute to retirement, at least enough to get any employer match.
> 4. Other goals (vacation, home

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant Tools

    User->>Agent: "I have money in checking and savings. How should I allocate my funds?"
    Agent->>Tools: "get_all_balances({})"
    Tools-->>Agent: "{'accounts': {'checking': {'balance': 1500.0, 'formatted': '"
    Agent->>User: "Thanks — I checked your accounts: you have $1,500 in checking and $3,000 in savi"
```

</details>

*Generated by [pytest-skill-engineering](https://github.com/sbroenne/pytest-skill-engineering) on February 07, 2026 at 07:22 PM*
