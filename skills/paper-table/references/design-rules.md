# Design rules

## Choose the form

- Use a LaTeX table for exact multi-metric lookup, many methods, ablations, or camera-ready copy.
- Use an HTML table for rapid review and accessible sharing.
- Use a table-chart for one dominant metric, meaningful deltas, or comparisons against a threshold.
- Split a table when it requires more than two header levels or mixes unrelated claims.

## Organize

Place independent variables and method identity on the left. Place outcomes on the right. Group columns by dataset, task, or metric family; group rows by model family, supervision, or experimental condition. Put the most important comparison nearest the method names.

## Encode

Use typographic hierarchy before color. Reserve bold for the best valid result and underline for second-best. Use teal/red only for signed improvements when color adds information, and pair color with arrows or signs. Shade the proposed method lightly only when row identity is otherwise hard to scan.

## Precision

Use the same decimals within a metric. Do not show more decimals than experimental stability supports. Prefer `85.4 ± 0.3` over separate mean and SD columns unless readers must compare uncertainty directly.

## Accessibility

Require meaningful headers, sufficient contrast, grayscale readability, and no color-only semantics. Keep captions self-contained: metric, direction, split, repeats, and uncertainty meaning.

## Physical fit

Measure the actual tabular box against the venue width; do not estimate fit from character counts. Search readable font size, column padding, and row stretch with `scripts/optimize_layout.py`. Treat tabular width/body-height fit as a hard publication-readiness gate, separate from scientific fidelity and subjective aesthetics; visually inspect caption and notes in the compiled preview.

Prefer structural remedies over whole-table scaling: split unrelated metric families, preserve the row-identity column in each panel, shorten repeated headers, move units/directions into grouped headers, or use full text width. Do not reduce below `scriptsize`, padding below 1.5 pt, or row stretch below 0.8. If every bounded candidate fails, report `needs_structural_redesign` instead of inserting `\resizebox`.
