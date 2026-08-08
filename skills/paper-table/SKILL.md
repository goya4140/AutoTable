---
name: paper-table
description: Turn raw experimental results into accurate, publication-ready academic tables and table-like statistical graphics using code. Use when an author asks to design, generate, improve, audit, or benchmark a paper table from CSV/JSON data, especially for ML/CV/NLP papers, LaTeX submissions, ablations, leaderboards, robustness results, or uncertainty reporting.
---

# Paper Table

Build tables through a gated workflow. Preserve every observed value exactly; never invent an observation.

## Workflow

1. Inspect the supplied data, manuscript context, venue constraints, and target claim.
2. Read `references/semantic-contract.md`, then run `scripts/analyze_data.py INPUT --json` when input is CSV or JSON. If repeated runs are incomplete or the author requests a precision target, read `references/data-acquisition.md`. Run `scripts/plan_more_data.py` when the target is each group's mean; run `scripts/plan_paired_difference.py` when the target is the within-run candidate-minus-baseline mean difference. Repair existing pairs and rerun the selected plan before aggregation. For complete independent runs, declare the repeat unit, independence evidence, run-ID key, cross-row pairing, missing-run policy, and displayed uncertainty, then run `scripts/aggregate_runs.py INPUT --out AGGREGATED.json`. If the input contains per-example observations, run `scripts/aggregate_observations.py INPUT --out AGGREGATED.json` before design; never treat examples as independent seeds. If significance or confidence claims are requested, read `references/inference.md` and resolve its blocking fields. Run `scripts/analyze_multimethod.py` for three or more methods on common complete blocks; otherwise run `scripts/analyze_paired.py`.
3. Resolve the inquiry plan. Ask at most three compact questions per round, store answers in the semantic contract, apply them to the next table draft, and never claim `verified` while a blocking field is unresolved.
4. Run `scripts/design_advisor.py SPEC --case CASE` once a draft spec exists. Offer its evidence-backed form, hierarchy, comparison baseline, emphasis rule, precision, uncertainty encoding, width target, warnings, and alternatives before rendering.
5. Create or revise a declarative table spec following `references/spec-schema.md`.
6. Route by the accepted visual proposal. For a conventional, ablation, leaderboard, or semantic-panel table, run `scripts/optimize_layout.py SPEC --out-dir OUTPUT --target-width-pt WIDTH`. For a recommended one-metric `ranked_table_chart` or `diverging_table_chart`, run `scripts/render_table_chart.py SPEC --out-dir OUTPUT`; retain direct exact-value labels and the generated chart contract. Use `render_table.py` directly only when layout parameters are already fixed.
7. Verify the artifact with `scripts/verify_table.py OUTPUT/selected-spec.json OUTPUT/table.tex` for tables or `scripts/verify_table.py SPEC OUTPUT/table-chart.svg` for table-charts. Require the relevant physical/layout gate, verify that every claimed-used author answer changed its corresponding contract field or visual encoding, treat numeric and semantic-contract checks as hard gates, then visually inspect the final PDF or PNG for clipping, collisions, scale honesty, and grayscale-safe non-color distinctions.
8. When a published or earlier canonical snapshot is supplied for reconciliation, run `scripts/compare_snapshot.py CURRENT PUBLISHED --row-key KEY`; treat any displayed-cell or metric-semantic drift as blocking for `verified`. For benchmark work, follow `references/evaluation.md`, preserve the input tier, freeze `y'` before inspecting `y`, and keep weak discovery annotations separate from PaperBench generation pairs or aesthetic gold.
9. Return editable code, the rendered preview, the validation report, and any unresolved limitations.

## Inquiry gate

Ask for missing data when it could change the scientific interpretation:

- repeated seeds/runs, sample-level predictions, or confidence intervals;
- metric direction and units;
- evaluation-set size and paired/unpaired comparison design;
- baseline identity and whether deltas are absolute or relative;
- statistical test, correction method, and significance threshold;
- the single claim the table should make.

Do not block on cosmetic preferences. Choose conservative defaults and state them. Stop asking once all blocking fields are resolved and further answers would not change scientific interpretation.

If the author asks for plausible variation without repeated runs, label it **simulated**, keep it separate from observed results, record the assumed distribution and seed, and never use it for significance claims. Prefer requesting real repeats.

For per-example aggregation, freeze the observation universe before computing values. Record the observation identity key, exclusions, named denominator ID lists, metric formula, scale, precision, and missing-report policy. Preserve the generated cell-level audit—including operation, denominator, sufficient statistic, and observation-ID hash—through every visual transformation. A changed or missing audit is a scientific failure even when the displayed rounded value is unchanged.

For repeated-run aggregation, require the `paper-table-runs-v1` contract. Accept runs only when independence is explicitly supported; a seed-like column name is not evidence. Record what one repeat represents, preserve unique run identifiers, choose either a fixed run set across comparison groups or an explicitly group-specific design, and reject missing runs instead of imputing. Report means alone, mean ± SD, or mean ± SE only when that choice matches the author intent; always retain unrounded mean, sample SD, SE, run count, run-ID list, and run-ID hash in the cell-level audit. Do not silently convert SD to SE or infer confidence intervals.

For additional experiments, first resolve whether precision targets a group mean or a paired baseline difference. Request author-chosen CI half-width targets, a run cap, and confirmation that the interval method fits the relevant repeat or paired-difference distribution. Use the matching planner to complete existing paired IDs before provisionally requesting new IDs across every required method and context. Present its leave-one-run-out range beside the point plan; route potential extreme runs, one-run-dependent variance, cap-sensitive projections, and target-status reversals to provenance review without deleting observations. Treat pilot-SD projections as planning estimates, flag zero pilot variance, and recompute after each acquisition round. Follow `references/data-acquisition.md`.

For multi-method cross-validation summaries, require a complete paired method × dataset × fold grid and use `scripts/aggregate_crossfold.py`. Resolve validation-based hyperparameter selection and its tie-break before aggregation; never choose a trial using test performance. Preserve the exact rank tie policy, Z-score denominator, dispersion definition, and win policy. If a pinned author snapshot does not reproduce the published cells at their displayed precision, label it a version-drift reconstruction and block `verified` status—do not introduce a tolerance merely to make it pass.

For inference, preserve the true sampling hierarchy. Use paired v1 for independent units, paired v2 for units nested in independent clusters, and the multi-method route for three or more methods on common complete blocks; reject unsupported cross-classified dependence. Never add stars from an unpaired, incomplete, uncorrected, simulated, post-hoc-selected, or omnibus-bypassing comparison. Follow `references/inference.md` for exchangeability, estimand weighting, resampling, gatekeeping, and provenance rules.

## Visual strategy

Use a conventional table when exact lookup and dense comparison matter. Use a code-generated table-chart only when direction, magnitude, or ranking is the primary message and one metric dominates. Keep 2–16 comparable rows, direct exact-value labels, a visible zero baseline for signed values, and a resolved metric direction and unit. Read `references/design-rules.md` for selection and styling rules.

Default to:

- booktabs-style horizontal rules and no vertical rules;
- grouped headers and whitespace instead of heavy borders;
- consistent decimals within a metric;
- bold best and underline second-best only within valid comparison groups;
- arrows in headers for metric direction;
- mean ± SD or confidence intervals when repeated measurements exist;
- restrained color that remains legible in grayscale.

Never use bolding to hide an unfavorable comparison, compare across incompatible settings, or calculate uncertainty from guessed sample sizes.

Never silently scale an overflowing table. Let the optimizer split only at coherent metric-family boundaries while repeating identity columns and preserving every metric once. It may pack adjacent complete groups into one panel, but must not separate a paired group or combine a partial group with another family. Automatically accept at most three stacked panels; a fourth panel is a page-design decision that requires structural feedback or author review. If bounded typography, semantic panels, and lossless text wrapping all fail, return structural feedback and prefer a wider placement or redesigned claim.

## Bundled resources

- `references/spec-schema.md`: read when authoring or debugging a table spec.
- `references/semantic-contract.md`: read before asking questions or declaring a table scientifically verified.
- `references/data-acquisition.md`: read when requesting missing runs or planning additional repeats for a precision target.
- `references/design-rules.md`: read when choosing layout, emphasis, and table-vs-chart form.
- `references/evaluation.md`: read when evaluating output quality or running the NeurIPS benchmark.
- `scripts/analyze_data.py`: profile inputs and produce author questions plus a draft design plan.
- `scripts/aggregate_runs.py`: aggregate genuinely independent repeated runs under an explicit pairing and missing-run contract, retaining unrounded SD/SE and hashed run audits.
- `scripts/plan_more_data.py`: audit repeated-run grids and emit repair-first, Student-t precision acquisition requests without simulating outcomes.
- `scripts/plan_paired_difference.py`: align baseline and candidate observations by fixed run ID, then emit repair-first Student-t precision requests for mean paired improvements.
- `scripts/pilot_stability.py`: compute descriptive skewness, modified-Z potential-extreme labels, and leave-one-run-out planning sensitivity without declaring normality or deleting observations.
- `scripts/aggregate_crossfold.py`: aggregate complete paired method-by-dataset-fold grids into mean score, average rank, fold-level Z-score summaries, and strict wins.
- `scripts/aggregate_observations.py`: deterministically aggregate per-example observations with fixed denominators and a cell-level provenance audit.
- `scripts/compare_snapshot.py`: compare a reconstruction with a publication at declared display precision and block false exact-gold or `verified` claims.
- `scripts/analyze_paired.py`: run audited unit- or cluster-level sign-flip comparisons with deterministic bootstrap intervals and Holm family correction; reject incomplete pairs and undeclared dependence.
- `scripts/analyze_multimethod.py`: run a ties-aware Friedman block-permutation omnibus followed by a predeclared, gated baseline-vs-all sign-flip family.
- `scripts/design_advisor.py`: derive a structured visual form, proposal, alternatives, warnings, and bounded follow-up questions from the table spec and semantic contract.
- `scripts/optimize_layout.py`: search measured typography, semantic panel, and lossless text-wrap candidates; emit structural feedback when none fit.
- `scripts/render_table.py`: deterministically render LaTeX and HTML from JSON.
- `scripts/render_table_chart.py`: render a one-metric ranked or diverging table-chart to editable SVG plus PDF/PNG and `chart-spec.json`.
- `scripts/verify_table.py`: check that rendered numeric tokens match the spec.
