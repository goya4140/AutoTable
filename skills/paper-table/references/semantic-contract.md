# Semantic contract and inquiry state

Before rendering, represent the scientific meaning that must survive visual transformation:

- the intended claim;
- a stable row identity key;
- metric direction and units;
- valid comparison groups and excluded rows;
- uncertainty type, independent-run count, repeat unit, independence evidence, run-ID key, cross-row pairing, missing-run policy, and aggregation source;
- expected run grid, target estimand, confidence level, per-metric CI half-width targets, minimum pilot size, maximum run budget, pilot-variance assumption, interval-distribution assumption, and leave-one-run-out sensitivity when additional data are requested; for paired differences also record the baseline, candidate family, contexts, difference orientation, and exact paired ID set; retain influential IDs and their provenance resolution without post-hoc deletion;
- hyperparameter selection metric, validation tie-break, rank tie policy, Z-score denominator, and win policy when reporting cross-dataset summaries;
- inferential unit, cluster/block structure, pairing, exchangeability rationale, predeclared baseline and family, tie policy, omnibus gate, effect orientation, test, confidence-interval method, correction, alpha, and randomization seeds when significance is requested;
- unit of observation, fixed denominator population, exclusions, and missing-observation policy;
- allowed transformations and forbidden inferences;
- target width and accessibility constraints.

Treat observed values and semantics as immutable. Layout, ordering, precision display, and restrained styling may change only when the contract permits them.

## Inquiry state machine

Use `scripts/analyze_data.py INPUT --json` to construct the first question batch. Classify missing fields as:

- `blocking`: an unanswered item could make a number, unit, ranking, comparison, or statistical statement false;
- `valuable_nonblocking`: it materially improves the table but a clearly labeled conservative draft remains possible;
- `cosmetic`: it affects appearance only and should receive a default.

Ask at most three questions per round. Order blocking questions first, then by expected scientific value. Do not repeat answered questions. Record each answer in the contract and use it in the next draft.

Stop asking when all blocking fields are resolved and no remaining question would materially change interpretation. If a blocking answer remains unavailable, return a clearly labeled draft or blocked status—never `verified`. Cosmetic uncertainty never blocks rendering.

Record answer availability separately from its value. An author response such as “the run count is unavailable” confirms absence; it does not resolve a blocking run-count requirement. Use `blocked` for unavailable blocking evidence and `draft` for unavailable valuable nonblocking evidence.

Never infer metric direction, units, comparison eligibility, independence of runs, uncertainty type, or statistical significance. Simulated variation is allowed only when explicitly requested, labeled simulated, and excluded from inferential claims.

Distinguish repeated runs from per-example records. Runs support between-run uncertainty only when they are genuinely independent. A column named `seed` does not establish independence: ask what was independently randomized and whether run IDs are paired across compared rows. Reject duplicates and undeclared missing-run handling. Use `paper-table-runs-v1` and retain unrounded means, sample SD, SE, counts, run IDs, and run-ID hashes even when the paper displays means only. Examples support deterministic dataset metrics but do not become repeated trials. For per-example inputs, bind each reported cell to a declared formula and denominator and retain a cell-level aggregation audit. Ask the author when exclusions, missing reports, or denominator changes could alter the claim.

Treat data-version identity as part of provenance. A current author artifact that nearly reproduces a paper is not interchangeable with the paper-time snapshot. Compare at the published display precision, report every drifted cell, and withhold `verified` status until the exact snapshot or an author-confirmed reconciliation is available. For hyperparameter trials, selection must use a declared validation metric; ties need an explicit deterministic rule, and test-set selection is forbidden.

Significance is a scientific claim, not decoration. Do not infer independent units from row count: folds, frames, prompts, examples, and repeated measurements may be nested within a shared dataset, subject, or run. Aggregate to the independent paired unit or use the clustered route in `inference.md`. When cluster sizes differ, explicitly choose equal-cluster or equal-unit weighting because the scientific estimand—and even its direction—can change. A marker is eligible only when the paired unit set is complete, independence/exchangeability is justified, the baseline and planned family are fixed, multiplicity is handled, and the exact test/interval configuration is retained in provenance. A confidence interval must name its target estimand, level, method, resampling unit, resample count, and seed.

Never render a positive p-value as numeric zero. Choose enough decimals for the minimum attainable exact or Monte Carlo p-value, or use a truthful inequality such as `<0.0001` while retaining the unrounded value in the inference audit.
