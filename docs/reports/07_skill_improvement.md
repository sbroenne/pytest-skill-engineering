
# pytest-aitest

> **4** tests | **3** passed | **1** failed | **75%** pass rate  
> Duration: 72.1s | Cost: 🧪 $-0.010241 · 🤖 $0.0205 · 💰 $0.0102 | Tokens: 1,286–2,169  
> February 07, 2026 at 07:39 PM

*Skill improvement — baseline vs skilled agent.*


## Agent Leaderboard


|#|Agent|Tests|Pass Rate|Tokens|Cost|Duration|
| :---: | :--- | :---: | :---: | ---: | ---: | ---: |
|🥇|baseline 🏆|2/2|100%|3,455|$0.004625|37.7s|
|🥈|with-financial-skill|1/2|50%|3,975|$0.005622|34.4s|



## AI Analysis

## 🎯 Recommendation

**Deploy: baseline (gpt-5-mini + default system prompt)**

Achieves **100% pass rate** across tested scenarios at **~2% lower cost** than the skilled variant, while correctly invoking banking tools when required.

**Reasoning:**  
- **Pass rate:** Baseline passed all tests; the skilled agent failed a required tool-usage assertion.  
- **Cost:** Baseline total cost is lower ($0.002759 vs $0.002804 in the comparable allocation test, ~2% savings).  
- **Behavior:** Baseline reliably calls `get_all_balances` when asked for allocation advice, satisfying test expectations.

**Alternatives:**  
- **with-financial-skill (gpt-5-mini)** — **Disqualified** due to failing the allocation advice test (did not call any balance tool despite the test requiring it).

## ❌ Failure Analysis

### Ask for allocation advice — skilled agent should apply 50/30/20 rule (with-financial-skill)
- **Problem:** The agent provided high-level guidance and asked a clarifying question instead of fetching balances, causing the test assertion to fail.
- **Root Cause:** The **system prompt/skill lacks an explicit instruction to proactively call balance tools** when allocation advice is requested. The agent optimized for conversational clarification over tool usage.
- **Fix:** Add an explicit directive to the system prompt or skill to always fetch balances for allocation questions.

**Exact text to add to the Financial Advisor Skill (top section):**
```
When a user asks how to allocate money across accounts, always retrieve current balances first using get_all_balances (or get_balance if only one account is relevant) before giving advice. Do not ask clarifying questions before checking balances.
```

## 🔧 MCP Tool Feedback

### pytest_aitest.testing.banking_mcp
Overall, tools are clear and functional. The issue observed is **agent hesitation**, not tool failure.

| Tool | Status | Calls | Issues |
|------|--------|-------|--------|
| get_all_balances | ✅ | 1 | Working well |
| get_balance | ✅ | 0 | Not used in failures; acceptable |
| transfer | ✅ | 0 | Not exercised |
| deposit | ✅ | 0 | Not exercised |
| withdraw | ✅ | 0 | Not exercised |
| get_transactions | ✅ | 0 | Not exercised |

## 📝 System Prompt Feedback

### default (effective)
- **Token count:** ~14
- **Assessment:** Clear, concise, and effective. The prompt implicitly encourages tool use and resulted in correct behavior.
- **Suggested change:** None.

### Financial Advisor Skill prompt (mixed)
- **Token count:** ~350+ (skill content)
- **Problem:** Strong financial guidance, but **missing operational instructions** about when to use MCP tools. This caused a direct test failure.
- **Suggested change:** Add the explicit tool-usage instruction shown in the Failure Analysis section.

## 📚 Skill Feedback

### financial-advisor (mixed)
- **Usage rate:** High in savings-related responses; partial in allocation advice.
- **Token cost:** High relative to baseline.
- **Problem:** The skill emphasizes advisory principles but not **tool orchestration**, leading to non-compliant behavior in tool-dependent tests.
- **Suggested change:** Add a short “Tool Usage Rules” subsection at the top:
```
## Tool Usage Rules
- For allocation, budgeting, or balance-based advice: always call the relevant balance tool first.
- Prefer get_all_balances when multiple accounts exist.
```

## 💡 Optimizations

1. **Enforce proactive balance retrieval** (recommended)
   - Current: Skilled agent asks clarifying questions instead of calling tools.
   - Change: Add explicit tool-usage rules to the skill/system prompt.
   - Impact: **Eliminates test failures** and avoids re-runs, saving ~$0.0028 per failed test execution.

2. **Reduce skill verbosity** (suggestion)
   - Current: Long skill content increases token usage without affecting tool behavior.
   - Change: Move “Budget Categories” and “Red Flags” to a secondary section loaded only when explicitly needed.
   - Impact: **~20–30% cost reduction** for skilled runs due to fewer prompt tokens.

## 📦 Tool Response Optimization

### get_all_balances (from pytest_aitest.testing.banking_mcp)
- **Current response size:** ~55–65 tokens
- **Issues found:** Duplicate formatted fields (`formatted`, `total_formatted`) are not used by the agent in reasoning.
- **Suggested optimization:** Remove formatted strings or make them optional.

**Example current vs optimized:**
```json
// Current (~60 tokens)
{
  "accounts": {
    "checking": {"balance": 1500.0, "formatted": "$1,500.00"},
    "savings": {"balance": 3000.0, "formatted": "$3,000.00"}
  },
  "total": 4500.0,
  "total_formatted": "$4,500.00"
}

// Optimized (~30 tokens)
{
  "accounts": {
    "checking": 1500.0,
    "savings": 3000.0
  },
  "total": 4500.0
}
```
- **Estimated savings:** ~30 tokens per call (**~50% reduction**)




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

*Generated by [pytest-aitest](https://github.com/sbroenne/pytest-aitest) on February 07, 2026 at 07:39 PM*
