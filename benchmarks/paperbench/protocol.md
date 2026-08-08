# Evaluation protocol

## Pair construction

1. Record venue, year, paper URL, page, table number, and source hash.
2. Prefer author-released raw runs. Otherwise recover the exact published cells and mark the input tier.
3. Remove visual styling from `x`; retain semantic structure such as metric direction, valid comparison groups, uncertainty type, and notes.
4. Keep `y` as the published table crop. Do not use `y` or same-paper tables as retrieval references while generating `y'`.
5. Split by paper, not by table.

For raw runs, preserve immutable run IDs and reject duplicate seeds. Compute sample standard deviation with n-1 degrees of freedom; compute standard error as sd/sqrt(n) only when explicitly requested. Store the contributing run IDs and n for every output cell. Never invert a published mean/error pair into invented runs.

## Objective scoring

Compute exact normalized token coverage from `x` to editable generated code. Numeric fidelity is a hard gate: a single unexplained changed or hallucinated number fails the case. Metric semantics, uncertainty semantics, comparison validity, and provenance are also hard gates. Report component metrics instead of hiding failures inside one average, and run the controlled perturbations to test evaluator sensitivity.

## Inquiry scoring

Hide contract fields before generation and log the full question/answer trace. Report critical-question recall, question precision, importance-weighted recall, unsupported inference count, over-questioning count, answer utilization, question-budget violations, and stop correctness. A system may produce a labeled draft when a blocking field is unavailable, but it must not declare the artifact verified.

## Subjective scoring

Show `y` and `y'` in randomized left/right order without method names. Ask at least three raters to score each output from 1 to 5 on typography, hierarchy, readability, claim salience, and overall aesthetics. Also collect a pairwise preference and a short reason. Repeat a hidden 10% subset to estimate intra-rater consistency.

Report majority preference, mean opinion score with bootstrap confidence intervals, Krippendorff's alpha, position-bias rate, and disagreement. Treat an automated VLM or image heuristic as a proxy only; validate it against human ratings before using it as a leaderboard metric.

## Leakage policy

References, exemplars, and prompts must not contain the target `y`, its LaTeX source, or any table from the target paper. The evaluator may access `y` only after `y'` is frozen.
