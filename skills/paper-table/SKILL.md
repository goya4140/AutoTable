---
name: paper-table
description: Turn raw experimental results into accurate, publication-ready academic tables and table-like statistical graphics using code. Use when an author asks to design, generate, improve, audit, or benchmark a paper table from CSV/JSON data, especially for ML/CV/NLP papers, LaTeX submissions, ablations, leaderboards, robustness results, or uncertainty reporting.
---

# Paper Table

Build tables through a gated workflow. Preserve every observed value exactly; never invent an observation.

## Workflow

1. Inspect the supplied data, manuscript context, venue constraints, and target claim.
2. Read `references/semantic-contract.md`, then run `scripts/analyze_data.py INPUT --json` when input is CSV or JSON.
3. Resolve the inquiry plan. Ask at most three compact questions per round, store answers in the semantic contract, apply them to the next table draft, and never claim `verified` while a blocking field is unresolved.
4. Run `scripts/design_advisor.py SPEC --case CASE` once a draft spec exists. Offer its evidence-backed form, hierarchy, comparison baseline, emphasis rule, precision, uncertainty encoding, width target, warnings, and alternatives before rendering.
5. Create or revise a declarative table spec following `references/spec-schema.md`.
6. Route by the accepted visual proposal. For a conventional, ablation, leaderboard, or semantic-panel table, run `scripts/optimize_layout.py SPEC --out-dir OUTPUT --target-width-pt WIDTH`. For a recommended one-metric `ranked_table_chart` or `diverging_table_chart`, run `scripts/render_table_chart.py SPEC --out-dir OUTPUT`; retain direct exact-value labels and the generated chart contract. Use `render_table.py` directly only when layout parameters are already fixed.
7. Verify the artifact with `scripts/verify_table.py OUTPUT/selected-spec.json OUTPUT/table.tex` for tables or `scripts/verify_table.py SPEC OUTPUT/table-chart.svg` for table-charts. Require the relevant physical/layout gate, verify that every claimed-used author answer changed its corresponding contract field or visual encoding, treat numeric and semantic-contract checks as hard gates, then visually inspect the final PDF or PNG for clipping, collisions, scale honesty, and grayscale-safe non-color distinctions.
8. For benchmark work, follow `references/evaluation.md`, preserve the input tier, freeze `y'` before inspecting `y`, and keep weak discovery annotations separate from PaperBench generation pairs or aesthetic gold.
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

Never silently scale an overflowing table. Let the optimizer split only at coherent metric-family boundaries while repeating identity columns and preserving every metric once. Automatically accept at most three stacked panels; a fourth panel is a page-design decision that requires structural feedback or author review. If bounded typography, semantic panels, and lossless text wrapping all fail, return structural feedback and prefer a wider placement or redesigned claim.

## Bundled resources

- `references/spec-schema.md`: read when authoring or debugging a table spec.
- `references/semantic-contract.md`: read before asking questions or declaring a table scientifically verified.
- `references/design-rules.md`: read when choosing layout, emphasis, and table-vs-chart form.
- `references/evaluation.md`: read when evaluating output quality or running the NeurIPS benchmark.
- `scripts/analyze_data.py`: profile inputs and produce author questions plus a draft design plan.
- `scripts/design_advisor.py`: derive a structured visual form, proposal, alternatives, warnings, and bounded follow-up questions from the table spec and semantic contract.
- `scripts/optimize_layout.py`: search measured typography, semantic panel, and lossless text-wrap candidates; emit structural feedback when none fit.
- `scripts/render_table.py`: deterministically render LaTeX and HTML from JSON.
- `scripts/render_table_chart.py`: render a one-metric ranked or diverging table-chart to editable SVG plus PDF/PNG and `chart-spec.json`.
- `scripts/verify_table.py`: check that rendered numeric tokens match the spec.
