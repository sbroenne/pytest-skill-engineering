
# pytest-skill-engineering

> **4** tests | **3** passed | **1** failed | **75%** pass rate  
> Duration: 72.1s | Cost: 🧪 $-0.011550 · 🤖 $0.0218 · 💰 $0.0102 | Tokens: 1,286–2,169  
> February 07, 2026 at 07:39 PM

*Skill improvement — baseline vs skilled agent.*


## Agent Leaderboard


|#|Agent|Tests|Pass Rate|Tokens|Cost|Duration|
| :---: | :--- | :---: | :---: | ---: | ---: | ---: |
|🥇|baseline 🏆|2/2|100%|3,455|$0.004625|37.7s|
|🥈|with-financial-skill|1/2|50%|3,975|$0.005622|34.4s|



## AI Analysis

<div class="winner-card">
<div class="winner-title">Recommended for Deploy</div>
<div class="winner-name">baseline</div>
<div class="winner-summary">Delivers a perfect pass rate at lower cost while reliably calling account tools when needed. Avoids permission-seeking behavior that caused missed tool usage in the skilled variant.</div>
<div class="winner-stats">
<div class="winner-stat"><span class="winner-stat-value green">100%</span><span class="winner-stat-label">Pass Rate</span></div>
<div class="winner-stat"><span class="winner-stat-value blue">$0.004625</span><span class="winner-stat-label">Total Cost</span></div>
<div class="winner-stat"><span class="winner-stat-value amber">3,455</span><span class="winner-stat-label">Tokens</span></div>
</div>
</div>

<div class="metric-grid">
<div class="metric-card green">
<div class="metric-value green">4</div>
<div class="metric-label">Total Tests</div>
</div>
<div class="metric-card red">
<div class="metric-value red">1</div>
<div class="metric-label">Failures</div>
</div>
<div class="metric-card blue">
<div class="metric-value blue">2</div>
<div class="metric-label">Agents</div>
</div>
<div class="metric-card amber">
<div class="metric-value amber">2.2</div>
<div class="metric-label">Avg Turns</div>
</div>
</div>

## Comparative Analysis

### Why the winner wins

- Achieves **100% pass rate** at **~18% lower total cost** than the alternative while handling the same scenarios.
- Correctly **initiates balance lookup tools without asking permission**, satisfying tests that require immediate tool usage.
- Uses fewer tokens overall, indicating more direct task execution rather than extended preambles.

### Notable patterns

- Adding the financial skill increased verbosity and introduced **permission-seeking behavior** (“do you want general guidance, or do you want me to look up your balances”) that delayed or prevented tool calls.
- The baseline agent implicitly followed the expected flow: retrieve balances first, then reason about allocation.
- The skill content helped with qualitative advice (emergency fund, prioritization) but conflicted with tests that expect **action-first behavior**.

### Alternatives

- **with-financial-skill**: Close in cost but failed allocation advice due to not calling tools. The root cause is not missing knowledge, but a **prompt/skill interaction that encourages asking clarifying questions before acting**.

## ❌ Failure Analysis

### Failure Summary

**with-financial-skill** (1 failure)

| Test | Root Cause | Fix |
|------|------------|-----|
| Ask for allocation advice — skilled agent should apply 50/30/20 rule | Permission-seeking response prevented required tool call | Instruct agent to fetch balances immediately when allocation is requested |

### Ask for allocation advice — skilled agent should apply 50/30/20 rule (with-financial-skill)
- **Problem:** The agent provided high-level guidance and asked for confirmation instead of retrieving balances.
- **Root Cause:** The agent never called `get_all_balances` or `get_balance`, violating the test’s expectation of tool usage.
- **Behavioral Mechanism:** The skill and system context emphasize phrases like “to give specific transfers I’ll need a little info” and “Quick question first,” which primes the model into a cautious, consultative mode. This shifts behavior from acting to **seeking user permission**, even when sufficient context exists to proceed.
- **Fix:** Add an explicit instruction to the system prompt or skill:
  > “When a user asks how to allocate money across accounts, immediately retrieve current balances using the appropriate account tools before asking any clarifying questions.”

## 🔧 MCP Tool Feedback

### accounts_server
Overall, tools are simple and discoverable. Failures were not due to tool design but to agent hesitation.

| Tool | Status | Calls | Issues |
|------|--------|-------|--------|
| get_all_balances | ✅ | 1 | Working well |
| get_balance | ✅ | 0 | Not used; no test required it explicitly |

## 📝 System Prompt Feedback

### baseline (effective)
- **Token count:** Low
- **Behavioral impact:** Encourages direct action and tool usage without excessive framing.
- **Problem:** None observed.
- **Suggested change:** None.

### with-financial-skill prompt (mixed — ineffective with gpt-5-mini in allocation task)
- **Token count:** Higher due to skill injection
- **Behavioral impact:** Language around “guidance,” “priorities,” and “quick questions” encourages explanation before execution.
- **Problem:** Lacks a clear directive on **when to act vs. ask**.
- **Suggested change:** Append:
  > “Default to action: if the user asks for advice that depends on account data, call the relevant tools immediately and explain after.”

## 📚 Skill Feedback

### financial-skill (mixed)
- **Usage rate:** High in advisory responses
- **Token cost:** Moderate
- **Problem:** Overemphasizes planning and prioritization, which can override test expectations for immediate tool calls.
- **Suggested change:** Split skill into two sections:
  - “Action rules” (tool-first behaviors)
  - “Advisory principles” (50/30/20, emergency fund guidance)

## 💡 Optimizations

| # | Optimization | Priority | Estimated Savings |
|---|-------------|----------|-------------------|
| 1 | Enforce tool-first rule for allocation queries | recommended | Avoid 100% of similar failures |
| 2 | Trim advisory preambles in skilled agent | suggestion | ~10% cost reduction |

#### 1. Enforce tool-first rule for allocation queries (recommended)
- Current: Skilled agent asks clarifying questions before fetching balances.
- Change: Add an explicit system/skill rule to always fetch balances first.
- Impact: Prevents test failures; reduces retries and wasted turns.

#### 2. Trim advisory preambles in skilled agent (suggestion)
- Current: Long high-level explanations precede any action.
- Change: Move explanations after tool results.
- Impact: ~10% cost reduction through fewer tokens and turns.


## Test Results


### tests/fixtures/scenario_07_skill_improvement.py


#### ❌ Ask for allocation advice — skilled agent should apply 50/30… ⚡

<details>
<summary>✅ baseline — 23.9s · 2,169 tokens · 3 turns · $0.002759</summary>

**Assertions:**

- ✅ `llm`: provides financial advice about fund allocation

**Tool Calls:**


|Tool|Status|Args|
| :--- | :---: | :--- |
|`get_all_balances`|✅||


**Response:**

> Right now you have $4,500 total: $1,500 in checking and $3,000 in savings. How you should split it depends on your goals and monthly cash flow. A few quick questions that will let me give a specific plan:
> - How much are your typical monthly living expenses (rent/mortgage, bills, food, transport)?
> - Any upcoming large expenses in the next 6–12 months (car repair, vacation, tuition, down payment)?
> - Do you have high‑interest debt (credit cards) you’re paying down?
> - Do you feel comfortable with th

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant Tools

    User->>Agent: "How should I allocate the money across my accounts?"
    Agent->>Tools: "get_all_balances({})"
    Tools-->>Agent: "{'accounts': {'checking': {'balance': 1500.0, 'formatted': '"
    Agent->>User: "Right now you have $4,500 total: $1,500 in checking and $3,000 in savings. How y"
```

</details>

<details>
<summary>❌ with-financial-skill — 17.7s · 1,983 tokens · 2 turns · $0.002804</summary>

**Error:** `      AssertionError: assert (False or False)
       +  where False = tool_was_called('get_all_balances')
       +    where tool_was_called = AgentResult(SUCCESS)\n  Turns: 2\n  Tools called: none\n  Duration: 11112ms\n  Tokens: 1983 | Cost: $0.002804\n  Final: 'I can help — to give specific transfers I’ll need a little info. Quick question first: do you want g'....tool_was_called
       +  and   False = tool_was_called('get_balance')
       +    where tool_was_called = AgentResult(SUCCESS)\n  Turns: 2\n  Tools called: none\n  Duration: 11112ms\n  Tokens: 1983 | Cost: $0.002804\n  Final: 'I can help — to give specific transfers I’ll need a little info. Quick question first: do you want g'....tool_was_called`

**Response:**

> I can help — to give specific transfers I’ll need a little info. Quick question first: do you want general guidance, or do you want me to look up your current balances and suggest exact transfers now?
> 
> Below is a short, practical plan you can use right away plus what I’ll do if you want me to check your accounts.
> 
> High-level rules (my priorities)
> - Emergency fund first: build 3–6 months of essential expenses in savings before other big goals.
> - Follow 50/30/20 as a baseline: 50% needs, 30% wants

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant Tools

    User->>Agent: "How should I allocate the money across my accounts?"
    Agent->>User: "I can help — to give specific transfers I’ll need a little info. Quick question "
```

</details>


#### ✅ Ask about savings — skilled agent should mention emergency f…

<details>
<summary>✅ baseline — 13.8s · 1,286 tokens · 2 turns · $0.001865</summary>

**Assertions:**

- ✅ `llm`: provides savings recommendations

**Response:**

> Great — here are practical, high-impact ways to save more, plus a couple quick options I can help with right away.
> 
> High-level principles
> - Automate it: set up automatic transfers to savings right after payday so you “pay yourself first.”
> - Make goals specific: name the goal, amount, and date (e.g., $3,600 in 12 months = $300/month).
> - Reduce friction: simplify accounts and automate categorization so saving feels effortless.
> 
> Concrete steps you can start today
> 1. Set a clear goal
>    - Emergency 

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant Tools

    User->>Agent: "I want to save more money. What do you recommend?"
    Agent->>User: "Great — here are practical, high-impact ways to save more, plus a couple quick o"
```

</details>

<details>
<summary>✅ with-financial-skill — 16.7s · 1,992 tokens · 2 turns · $0.002818</summary>

**Assertions:**

- ✅ `llm`: provides savings recommendations

**Response:**

> Great — want practical, doable steps. Here’s a short, actionable plan you can start today plus specific tactics to speed up saving.
> 
> Top priorities (in order)
> 1. Build an emergency fund equal to 3–6 months of your essential monthly expenses. This comes first.
> 2. After your emergency fund, pay down any high‑interest debt (credit cards, payday, some personal loans).
> 3. Make sure you’re getting any employer retirement match (this is “free money”).
> 4. Then save for other goals (house, vacation) and 

```mermaid
sequenceDiagram
    participant User
    participant Agent
    participant Tools

    User->>Agent: "I want to save more money. What do you recommend?"
    Agent->>User: "Great — want practical, doable steps. Here’s a short, actionable plan you can st"
```

</details>

*Generated by [pytest-skill-engineering](https://github.com/sbroenne/pytest-skill-engineering) on February 07, 2026 at 07:39 PM*
