# Evaluation

Score each artifact from 0 to 2 on six axes: numeric faithfulness, comparison validity, hierarchy, readability at target width, claim salience, and editability/reproducibility. Numeric fidelity, metric semantics, uncertainty semantics, comparison validity, and provenance are hard gates; visual scores cannot compensate for a scientific violation.

Record `design_advisor.py` output as a diagnostic: recommended form, decision basis, warnings, questions, and alternatives. Do not score a system by agreement with its own recommendation. Validate form selection with blinded human comparisons or a separately annotated table-vs-chart benchmark.

Measure the natural tabular box with XeLaTeX and report target width, measured width, tabular body height, utilization, selected typography candidate, and fit status. Physical fit is a publication-readiness hard gate, but it is not a human aesthetic score. Inspect caption/notes in the compiled preview, reject silent whole-table scaling, and report structural redesign when bounded readable candidates all overflow.

For panelized output, require every metric exactly once and in canonical order, repeat identity columns only, and forbid mixing distinct nonempty metric groups. Automatically accept at most three stacked panels; route larger layouts to structural feedback or author review. Adjust rendered-token multiplicity only for the deliberately repeated identity columns; do not relax metric-number precision or hallucination checks.

Use `benchmarks/paperbench/` for `(x,y)` generation evaluation. Record whether `x` contains raw runs, a canonical table, or cells recovered from the publication; never compare these tiers as if they test the same capability. Use `blind_protocol.py` to separate public inputs from private gold, freeze every output hash before revealing `y`, split by paper, and keep scientific fidelity as a hard gate. Disable network access for leaderboard generators.

For per-run data, use `benchmarks/paperbench/aggregate_runs.py`. Preserve run IDs, reject duplicate seeds and groups with fewer than two independent runs, and retain the generated aggregation audit. Never manufacture per-seed values by inverting a published mean and uncertainty.

Use `benchmarks/neurips-tables/collect.py` only for candidate discovery. A captioned crop without structured `x` is not a generation pair and must not enter the PaperBench leaderboard.

Run PaperTable-Controlled to verify that an evaluator rejects wrong values, direction/unit swaps, SD/SE swaps, invalid ranking eligibility, emphasis-policy changes, and omitted rows. Prefer InquiryBench's executable simulated-author runner to self-reported traces. Report critical-question recall, question precision, weighted recall, unsupported inference, trace consistency, repeated/irrelevant questions, answer utilization, answer application to the output, and stop correctness. Reject a submission that declares an answer used without restoring the corresponding table/contract field. Use null—not zero—when a metric has no applicable gold item.
