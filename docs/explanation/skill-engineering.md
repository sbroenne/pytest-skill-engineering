# Improving an AI-facing interface

An AI-facing interface is what Copilot sees when it decides how to act: tool
descriptions, parameter schemas, system prompts, skills, custom agent
definitions, and the user's task. Improving that interface is what this project
calls *skill engineering*. It is broader than editing a `SKILL.md` file.

Unit tests can show that a tool calculates the right answer. A Copilot test can
show whether the agent selects that tool and supplies the right inputs for a
real task. You need both: neither substitutes for the other.

## The improvement loop

1. Define a representative user task and observable success criteria.
2. Configure `CopilotEval`, execute the task with `copilot_eval`, and save JSON.
3. Verify actual output, not just a model's claim or a call's presence.
4. Investigate failures alongside the source and environment.
5. Change the source or instructions supported by that investigation and rerun affected cases.
6. Check regressions and repeat cases when reliability is the question.

The framework supplies execution and evidence. Your tests supply verification.
Your existing coding agent or a human investigates the evidence alongside the
source; the framework does not automatically grade free-text expectations.

## Do not assume every failure is an instruction problem

Wrong fixture data, startup problems, permission denials, application bugs,
ambiguous tasks, and incorrect tests can look like skill failures. Read actual
arguments and returned operation results before rewriting a system prompt.

Keep criteria fixed across comparisons. If the test's criterion was wrong,
correct it and establish a new baseline for both configurations. Do not count
the new result as an improvement against the old criterion.

One passing run establishes an observation, not production reliability.
Repeated, representative tasks are needed when reliability is the question.

## What you are testing

| Term | Meaning here |
| --- | --- |
| Skill | A domain-guidance package with a `SKILL.md` entry point |
| System prompt | Instructions configuring behavior, supplied through `CopilotEval.instructions` |
| Prompt | The user task sent to `copilot_eval` |
| Custom agent | A `.agent.md` definition |
| Custom agent dispatch | The runtime routing being tested |
| Subagent | An actual runtime invocation, recorded in `result.subagent_invocations` |
| Eval | The test harness, not the interface under test |

Start with [a first test](../getting-started/index.md), then
[compare configurations](../getting-started/comparing.md) using fixed checks.
