# Cost estimation

Add explicit model rates to `pricing.toml` to estimate USD cost from captured
token usage. These estimates are separate from Copilot's premium-request
accounting and are not an invoice or a comparison of output quality.

```toml title="pricing.toml"
[models]
"gpt-5.6-sol" = { input = 5.00, output = 30.00, cache_read = 0.50 }
```

These are explicit example rates, not a promise about current billing. Adjust
them for your billing basis and every model your suite can use.

Supply both `input` and `output`. Also supply `cache_read` when your billing
basis includes cached-input tokens. The current estimator treats an omitted
rate as zero; that is not evidence that those tokens were free.

Pricing is searched upward from the process working directory, using the first
`pricing.toml` found. Tables are cached by file identity and modification time.
The generated starter writes explicit rates without replacing existing ones.

## Missing pricing and usage

A missing model rate produces a placeholder zero estimate and a missing-pricing
warning. The suite saves `models_without_pricing` in native JSON evidence.
Warnings cover every captured usage model, including earlier models and
framework-owned child sessions, not just the test's final display model.
They are calculated for the current suite and current pricing file.
**This is not measured free usage.** Do not choose
a supposedly cheapest configuration from unavailable prices.

Missing SDK usage values remain `None`, not known zero. Usage records missing
input or output counts do not contribute a token cost estimate. Unknown
cache-read counts contribute no cache-read estimate. A partial estimate is not
complete billing evidence. See [result evidence](../reference/result.md).

Parent cost and premium-request totals include framework-owned child work once;
the saved child records remain separately inspectable. Do not sum inclusive
parent and child totals together.

## Plan a live run

Count configurations, cases, and repetitions before authorizing the suite.
Two A/B sides are two executions even though they share one pytest outcome.
The harness does not retry failures automatically; an explicit rerun consumes
additional usage.

Inspect saved usage and missing-pricing warnings before comparing costs. A
lower estimate alone does not establish that a configuration completed the
task correctly. See [Inspect execution evidence](inspect-evidence.md).
