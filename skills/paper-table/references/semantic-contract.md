# Semantic contract and inquiry state

Before rendering, represent the scientific meaning that must survive visual transformation:

- the intended claim;
- a stable row identity key;
- metric direction and units;
- valid comparison groups and excluded rows;
- uncertainty type, independent-run count, repeat unit, independence evidence, run-ID key, cross-row pairing, missing-run policy, and aggregation source;
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
