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
4. Offer a concrete visual proposal before rendering: row/column hierarchy, comparison baseline, emphasis rule, precision, uncertainty encoding, and width target.
5. Create or revise a declarative table spec following `references/spec-schema.md`.
6. Render with `scripts/render_table.py SPEC --out-dir OUTPUT`.
7. Verify the artifact with `scripts/verify_table.py SPEC OUTPUT/table.tex`; verify that every claimed-used author answer changed its corresponding contract field or table encoding, treat numeric and semantic-contract checks as hard gates, then visually inspect the compiled PDF or HTML screenshot.
8. For benchmark work, follow `references/evaluation.md`, preserve the input tier, and freeze `y'` before inspecting `y`.
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

Use a conventional table when exact lookup and dense comparison matter. Use a code-generated table-chart only when direction, magnitude, or ranking is the primary message. Read `references/design-rules.md` for selection and styling rules.

Default to:

- booktabs-style horizontal rules and no vertical rules;
- grouped headers and whitespace instead of heavy borders;
- consistent decimals within a metric;
- bold best and underline second-best only within valid comparison groups;
- arrows in headers for metric direction;
- mean ± SD or confidence intervals when repeated measurements exist;
- restrained color that remains legible in grayscale.

Never use bolding to hide an unfavorable comparison, compare across incompatible settings, or calculate uncertainty from guessed sample sizes.

## Bundled resources

- `references/spec-schema.md`: read when authoring or debugging a table spec.
- `references/semantic-contract.md`: read before asking questions or declaring a table scientifically verified.
- `references/design-rules.md`: read when choosing layout, emphasis, and table-vs-chart form.
- `references/evaluation.md`: read when evaluating output quality or running the NeurIPS benchmark.
- `scripts/analyze_data.py`: profile inputs and produce author questions plus a draft design plan.
- `scripts/render_table.py`: deterministically render LaTeX and HTML from JSON.
- `scripts/verify_table.py`: check that rendered numeric tokens match the spec.
