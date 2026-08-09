
# pytest-skill-engineering

> **6** tests | **5** passed | **1** failed | **83%** pass rate  
> Duration: 75.7s | Cost: 🧪 $0.009104 · 🤖 $0.0179 · 💰 $0.0270 | Tokens: 377–3,235  
> February 07, 2026 at 07:22 PM

*Three agents for testing the agent selector UI.*


## Eval Leaderboard


|#|Eval|Tests|Pass Rate|Tokens|Cost|Duration|
| :---: | :--- | :---: | :---: | ---: | ---: | ---: |
|🥇|gpt-5-mini 🏆|2/2|100%|3,448|$0.003737|31.1s|
|🥈|gpt-5-mini + financial-advisor|2/2|100%|4,908|$0.004823|33.3s|
|🥉|gpt-4.1-mini|1/2|50%|1,113|$0.000544|11.3s|



## AI Analysis

## 🎯 Recommendation

**Deploy: gpt-5-mini (default system prompt, no skill)**

Achieves **100% pass rate** on required behaviors at **~55% lower total cost** than the skill-augmented variant, while correctly using MCP tools.

**Reasoning:**  
- **Pass rate:** gpt-5-mini (default) passed both tests it was eligible for, including correct tool usage for financial advice. gpt-4.1-mini failed a required tool call and is disqualified.  
- **Cost:**  
  - gpt-5-mini (default): $0.003738 total across tests shown  
  - gpt-5-mini + financial-advisor: $0.004824 total (**~29% higher cost**)  
- **Response quality:** The default prompt produced cautious, compliant advice (asking for more info) while still grounding responses in real balances via tools. The skill adds richer advice but at significantly higher cost and token usage.

**Alternatives:**  
- **gpt-5-mini + financial-advisor:** Higher-quality financial guidance, but **~29% higher cost** and nearly **2× token usage**. Suitable only if advisory depth is a product requirement.  
- **gpt-4.1-mini:** **Disqualified** — failed required tool usage in the financial advice test.

## ❌ Failure Analysis

### Financial advice — tests differentiation between agents (skill vs no skill) (gpt-4.1-mini)
- **Problem:** The agent asked the user for balances instead of retrieving them.
- **Root Cause:** The system prompt instruction “Always use tools” was not strong enough to force proactive balance retrieval for advisory questions.
- **Fix:** Update the system prompt to explicitly require balance lookup for advice:
  ```
  Always retrieve relevant account balances using tools before giving any financial advice or recommendations.
  ```

## 🔧 MCP Tool Feedback

### pytest_skill_engineering.testing.banking_mcp
Overall, tools are well-defined and correctly used by compliant agents. Tool selection is intuitive.

| Tool | Status | Calls | Issues |
|------|--------|-------|--------|
| get_balance | ✅ | 3 | Working well |
| get_all_balances | ✅ | 2 | Working well |
| transfer | ⚠️ | 0 | Not exercised in tests |
| deposit | ⚠️ | 0 | Not exercised in tests |
| withdraw | ⚠️ | 0 | Not exercised in tests |
| get_transactions | ⚠️ | 0 | Not exercised in tests |

## 📝 System Prompt Feedback

### default (mixed)
- **Token count:** ~20
- **Problem:** The instruction “Always use tools” is underspecified for advisory scenarios, leading one model to ask the user instead of calling tools.
- **Suggested change:** Replace the last line with:
  ```
  Always retrieve required account data with tools before answering questions about balances, allocations, or financial advice. Never ask the user for information that tools can provide.
  ```

## 📚 Skill Feedback

### financial-advisor (positive but expensive)
- **Usage rate:** High — principles and structure clearly reflected in responses
- **Token cost:** ~700–900 extra tokens per test
- **Problem:** Overkill for simple balance queries; skill content is injected even when not needed.
- **Suggested change:** Split into two skills:
  - `financial-advisor-core` (principles + priorities only)
  - `financial-advisor-budgeting` (detailed categories and red flags)

## 💡 Optimizations

1. **Conditional Skill Injection** (recommended)
   - Current: Financial advisor skill is always loaded.
   - Change: Only attach the skill for tests or routes involving “advice”, “budget”, or “allocation”.
   - Impact: **25–35% cost reduction** on non-advisory queries (~700–900 fewer tokens per call).

2. **Stronger Tool-Use Directive** (recommended)
   - Current: Models interpret “Always use tools” inconsistently.
   - Change: Add explicit requirement to fetch balances before advice (see prompt fix above).
   - Impact: Prevents tool-miss failures, eliminating retries and failed tests (saves ~$0.0002 per failure).


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
    participant Eval
    participant Tools

    User->>Eval: "What's my checking account balance?"
    Eval->>Tools: "get_balance({'account': 'checking'})"
    Tools-->>Eval: "{'account': 'checking', 'balance': 1500.0, 'formatted': '$1,"
    Eval->>User: "Your checking account balance is $1,500.00. Would you like to do anything else w"
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
    participant Eval
    participant Tools

    User->>Eval: "What's my checking account balance?"
    Eval->>Tools: "get_balance({'account': 'checking'})"
    Tools-->>Eval: "{'account': 'checking', 'balance': 1500.0, 'formatted': '$1,"
    Eval->>User: "Your checking account balance is $1,500.00. Is there anything else you would lik"
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
    participant Eval
    participant Tools

    User->>Eval: "What's my checking account balance?"
    Eval->>Tools: "get_balance({'account': 'checking'})"
    Tools-->>Eval: "{'account': 'checking', 'balance': 1500.0, 'formatted': '$1,"
    Eval->>User: "Your checking account balance is $1,500.00. Would you like me to: - Show your sa"
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
    participant Eval
    participant Tools

    User->>Eval: "I have money in checking and savings. How should I allocate my funds?"
    Eval->>Tools: "get_all_balances({})"
    Tools-->>Eval: "{'accounts': {'checking': {'balance': 1500.0, 'formatted': '"
    Eval->>User: "I pulled your balances: checking $1,500 and savings $3,000 (total $4,500). I can"
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
    participant Eval
    participant Tools

    User->>Eval: "I have money in checking and savings. How should I allocate my funds?"
    Eval->>User: "To provide you with a recommendation on how to allocate your funds between check"
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
    participant Eval
    participant Tools

    User->>Eval: "I have money in checking and savings. How should I allocate my funds?"
    Eval->>Tools: "get_all_balances({})"
    Tools-->>Eval: "{'accounts': {'checking': {'balance': 1500.0, 'formatted': '"
    Eval->>User: "Thanks — I checked your accounts: you have $1,500 in checking and $3,000 in savi"
```

</details>

*Generated by [pytest-skill-engineering](https://github.com/sbroenne/pytest-skill-engineering) on February 07, 2026 at 07:22 PM*
