# Skill engineering

Tool descriptions, parameter schemas, system prompts, skills, custom agent
definitions, and task phrasing shape how Copilot uses an interface. Test that
interface with real tasks and independent output checks.

Static checks can establish valid schemas and files; they cannot establish that
a model will interpret the interface correctly. Conversely, model execution
does not replace tests of the tool implementation.

## The improvement loop

1. Define a representative user task and observable success criteria.
2. Execute it through `CopilotEval` and save native evidence.
3. Verify actual output, not just a model's claim or a call's presence.
4. Investigate failures alongside the source and environment.
5. Change one supported cause and rerun affected cases.
6. Check regressions and repeat cases when reliability is the question.

The framework supplies execution and evidence. The coding agent already working
in your repository supplies the investigation, assisted by the
[companion skill](../getting-started/companion-skill.md). There is no separate
automated adviser and no automatic free-text answer grading.

## Do not assume every failure is an instruction problem

Wrong fixture data, startup problems, permission denials, application bugs,
ambiguous tasks, and incorrect tests can look like skill failures. Read actual
arguments and returned operation results before rewriting a system prompt.

Keep criteria fixed across comparisons. If a criterion was wrong, explain its
replacement and establish a new baseline openly. A good-looking recommendation
or one passing run is not measured production reliability.

## What you are testing

An Agent Skill is a domain-knowledge package. A custom agent is a `.agent.md`
definition; custom agent dispatch is its runtime use. A system prompt configures
behavior, while a prompt is the user task. `CopilotEval` is the test harness,
not the thing under test.

Start with [a first test](../getting-started/index.md), then
[compare configurations](../getting-started/comparing.md) using fixed checks.
