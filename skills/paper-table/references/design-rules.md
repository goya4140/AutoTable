# Design rules

## Choose the form

- Use a LaTeX table for exact multi-metric lookup, many methods, ablations, or camera-ready copy.
- Use an HTML table for rapid review and accessible sharing.
- Use a table-chart for one dominant metric, meaningful deltas, or comparisons against a threshold.
- Split a table when it requires more than two header levels or mixes unrelated claims.

Run `scripts/design_advisor.py` before committing to a form. A ranked or diverging table-chart requires exactly one resolved metric, 2–16 comparable rows, and direct exact-value labels. Preserve author-defined row order unless the author confirms that ranking order is semantically safe. For signed values, show a zero baseline, explicit +/− labels, and tone or fill differences so color is not the only sign cue. Keep the conventional table when multiple outcomes require exact lookup.

## Organize

Place independent variables and method identity on the left. Place outcomes on the right. Group columns by dataset, task, or metric family; group rows by model family, supervision, or experimental condition. Put the most important comparison nearest the method names.

## Encode

Use typographic hierarchy before color. Reserve bold for the best valid result and underline for second-best. Use teal/red only for signed improvements when color adds information, and pair color with arrows or signs. Shade the proposed method lightly only when row identity is otherwise hard to scan.

## Precision

Use the same decimals within a metric. Do not show more decimals than experimental stability supports. Prefer `85.4 ± 0.3` over separate mean and SD columns unless readers must compare uncertainty directly.

## Accessibility

Require meaningful headers, sufficient contrast, grayscale readability, and no color-only semantics. Keep captions self-contained: metric, direction, split, repeats, and uncertainty meaning.

For static table-charts, export SVG as the editable source plus PDF and PNG. Use a neutral descriptive title, a subtitle/caption containing the comparison baseline and unit, a zero-origin scale for absolute bars, and a visible zero reference for signed deltas. Inspect the exported PNG; code execution alone is not visual QA.

## Physical fit

Measure the actual tabular box against the venue width; do not estimate fit from character counts. Search readable font size, column padding, and row stretch with `scripts/optimize_layout.py`. Treat tabular width/body-height fit as a hard publication-readiness gate, separate from scientific fidelity and subjective aesthetics; visually inspect caption and notes in the compiled preview.

Prefer structural remedies over whole-table scaling: split at coherent metric-family boundaries, preserve the row-identity column in each panel, wrap long identity labels without abbreviation, shorten repeated headers, move units/directions into grouped headers, or use full text width. Pack adjacent groups together only when every included group is complete; never detach one member of a paired outcome merely to balance width. Automatically accept no more than three stacked panels; four or more require author review or a wider placement because physical fit alone does not imply a readable page. Do not reduce below `scriptsize`, padding below 1.5 pt, or row stretch below 0.8. If every bounded candidate fails, report `needs_structural_redesign` instead of inserting `\resizebox`.
