# Cost estimation

The framework estimates task-execution USD cost from reported tokens and
explicit per-million-token rates. Copilot premium-request accounting is a
separate measurement. Neither is a separate report-analysis charge.

```toml
[models]
"gpt-5.6-sol" = { input = 5.00, output = 30.00, cache_read = 0.50 }
```

These are explicit example rates, not a promise about current billing. Adjust
them for your billing basis.

`input` and `output` are required rates. `cache_read` is optional. Pricing is
searched upward from the process working directory and cached for the session.
The generated starter writes explicit rates without replacing existing ones.

## Missing pricing and usage

A missing model rate produces a placeholder zero estimate and a missing-pricing
warning. The suite saves `models_without_pricing` in native JSON evidence.
**This is not measured free usage.** Do not choose
a supposedly cheapest configuration from unavailable prices.

Missing SDK usage values remain `None`, not known zero. Estimates from available
input/output counts are not complete billing evidence; unknown cache reads
receive no cache discount. See [result evidence](../reference/result.md).
