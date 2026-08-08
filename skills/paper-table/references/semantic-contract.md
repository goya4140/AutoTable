# Semantic contract and inquiry state

Before rendering, represent the scientific meaning that must survive visual transformation:

- the intended claim;
- a stable row identity key;
- metric direction and units;
- valid comparison groups and excluded rows;
- uncertainty type, independent-run count, and aggregation source;
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
