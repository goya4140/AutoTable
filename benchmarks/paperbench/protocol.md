# Evaluation protocol

## Pair construction

1. Record venue, year, paper URL, page, table number, and source hash.
2. Prefer author-released raw runs. Otherwise recover the exact published cells and mark the input tier.
3. Remove visual styling from `x`; retain semantic structure such as metric direction, valid comparison groups, uncertainty type, and notes.
4. Keep `y` as the published table crop. Do not use `y` or same-paper tables as retrieval references while generating `y'`.
5. Split by paper, not by table.

For raw runs, preserve immutable run IDs and reject duplicate seeds. Compute sample standard deviation with n-1 degrees of freedom; compute standard error as sd/sqrt(n) only when explicitly requested. Store the contributing run IDs and n for every output cell. Never invert a published mean/error pair into invented runs.

## Objective scoring

Compute exact normalized token coverage from `x` to editable generated code. Numeric fidelity is a hard gate: a single unexplained changed or hallucinated number fails the case. Metric semantics, uncertainty semantics, comparison validity, and provenance are also hard gates. For semantic panels, count identity-column tokens once per panel but every metric value exactly once; require canonical metric order and reject cross-group mixing. Report component metrics instead of hiding failures inside one average, and run the controlled perturbations to test evaluator sensitivity.

## Inquiry scoring

Hide contract fields before generation and log the full question/answer trace. Strip paper identity and retrieval metadata from the public request. Prefer `run_interaction.py` over a self-reported trace: reveal a hidden value only after the adapter asks for its field, then verify that the value appears in `resolved_fields` and changes the relevant final-table semantics. Distinguish an available answer from an explicit `unavailable` response; the latter leaves a blocking field unresolved. Report critical-question recall, question precision, importance-weighted recall, unsupported inference count, trace-consistency violations, repeated/irrelevant questions, answer utilization, answer application, output recovery, question-budget violations, and stop correctness. Mark metrics with no applicable gold item as null rather than zero. Use `blocked` for unavailable blocking evidence and `draft` for unavailable valuable evidence; never declare either verified.

## Subjective scoring

Show `y` and `y'` in randomized left/right order without method names. Ask at least three raters to score each output from 1 to 5 on typography, hierarchy, readability, claim salience, and overall aesthetics. Also collect a pairwise preference and a short reason. Repeat a hidden 10% subset to estimate intra-rater consistency.

Report majority preference, mean opinion score with bootstrap confidence intervals, Krippendorff's alpha, position-bias rate, and disagreement. Treat an automated VLM or image heuristic as a proxy only; validate it against human ratings before using it as a leaderboard metric.

Report the deterministic design advisor's recommended visual form, warnings, and unresolved questions as diagnostics, not as an aesthetic score. A recommendation is not proof that the chosen form is better; evaluate form selection through blinded human preference or a separately annotated form-selection set.

## Leakage policy

References, exemplars, and prompts must not contain the target `y`, its LaTeX source, or any table from the target paper. The evaluator may access `y` only after `y'` is frozen.

Use `blind_protocol.py` to enforce the artifact boundary and randomly remap request IDs for every episode. Distribute only the freshly prepared public directory—never the committed development JSONL; keep the private manifest and evaluator-only gold on a separate mount. Freeze all submission files before enabling that mount or inspecting references. Reject altered request hashes, extra or missing submission IDs, symlinks, and any post-freeze byte change. For an externally reported leaderboard, also run the generator without network access because method names or captions can be searchable even when paper identifiers are removed.
