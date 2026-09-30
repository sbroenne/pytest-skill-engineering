# Investigating captured evidence

Read the pytest failure, full saved JSON trace, and source relevant to the failing
requirement. The framework records outcomes and execution; you interpret them.
There are no HTML/Markdown reports, rankings, or automatically chosen winners.

| Observation | Investigate before changing instructions |
| --- | --- |
| No relevant call | Discovery, tool descriptions, exposed schemas, permissions, task ambiguity |
| Wrong arguments | Parameter descriptions, examples, units, enum values, fixture identifiers |
| Tool rejects a valid request | Tool implementation, startup, authentication, application state |
| Session completes but artifact is wrong | Output checks, tool results, incomplete work, incorrect model claims |
| Calls or usage are incomplete | Correlation identifiers, completion events, capture errors, request audit |
| Comparison differs | Shared pytest outcomes, isolated state, changed conditions, sample size |
| Cost appears zero | Saved missing-pricing models and the explicit pricing configuration |

A framework failure, an environment problem, a wrong test, and an interface
problem need different fixes. Prefer a source-backed explanation over a generic
"improve the system prompt" suggestion.

Do not widen accepted answers after seeing a failure. If the original criterion
was wrong, document why, change it openly, and establish a new baseline.
Do not skip a failing case, invent missing output, or retrofit report evidence.

For evidence persistence changes, use offline serialization and control checks.
For execution or tool changes, run the smallest relevant authorized live cases sequentially and avoid
repeating already-passing expensive tests without a reason.

End with a short evidence-backed result: what changed, the exact observable
requirement checked, remaining uncertainty, and where the native report is saved.
A single passing run is not proof of production reliability.
