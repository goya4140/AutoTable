# Assumption-only variation scenarios

Prefer real independent repeats. Use `scripts/simulate_variation.py` only when the author explicitly requests an illustration of possible fluctuation and confirms that repeated-run evidence is unavailable or intentionally not being used.

Require, for every cell:

- the observed point anchor, metric direction, and unit;
- `normal` or `truncated_normal` as an explicit model family;
- a positive `scale_parameter`, its `scale_parameterization`, plus `author_assumption` or `external_domain_evidence` and a concrete source detail; use `distribution_sd` for an ordinary normal and `parent_normal_sd_before_truncation` for a truncated normal;
- scientific lower and upper bounds when using a truncated normal;
- `future_single_run`, or `future_mean_of_independent_runs` with the intended future run count;
- a scenario-level central interval mass, 1,000–100,000 draws, integer seed, author-request source, and illustrative-only purpose.

Do not infer scale from a lone point estimate, metric bounds, plot aesthetics, or another method. Do not add bounds to an ordinary normal and then clip draws; choose `truncated_normal`, whose parent normal is explicitly restricted to the declared interval. Its scale parameter is the parent-normal SD before truncation, not the realized SD of the bounded distribution. Reject bounds with negligible parent-normal probability or excessive expected rejection-sampling work.

Use a cell-specific stream derived from the global seed, stable cell identity, and metric so input row order cannot change the scenario. Simulate each future run independently and average within each draw when the target is a future mean. Retain the distribution, scale provenance, bounds, target, run count, draw count, seed, Monte Carlo SE of the simulated mean, and draw-order hash. Store summaries rather than raw draws.

Keep four layers visually and semantically distinct:

1. `observed_anchor`: the supplied point used only as the model location;
2. `assumed scale`: an ordinary-normal distribution SD or truncated-normal parent SD, never observed uncertainty;
3. `simulated range`: a Monte Carlo scenario interval, never a confidence interval;
4. `evidence status`: always `SIMULATED — not evidence`.

Set the table and every row to observed false and rank-ineligible. Use no best/second emphasis. Never compute or display p-values, stars, method-win probabilities, rankings, confidence claims, or verified status from this output. Never blend simulated draws with later observed runs; replace the scenario when real evidence arrives.

Reject contradictory provenance anywhere in the input when it claims `observed`, `verified`, inference eligibility, ranking eligibility, or significance eligibility. Prefix the stored scenario label with `SIMULATED SCENARIO` and overwrite output provenance with explicit `observed: false` and `verified: false` guards.

References: [NIST normal distribution](https://www.itl.nist.gov/div898/handbook/eda/section3/eda3661.htm) and [NIST truncated normal definition](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/tnrpdf.pdf).
