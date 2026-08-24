---
name: main-experiment-table
description: Design and generate publication-ready main experimental tables and captions from CSV, TSV, JSON, or JSONL results using patterns derived from ICLR, NeurIPS, ICML, ACL, NAACL, and CVPR papers. Use for claim-aware schema planning, method-family grouping, scoped ranking, auxiliary deltas, benchmark orientation, quality-efficiency comparisons, and LaTeX/HTML output; not for figures or PDF table extraction.
metadata:
  short-description: Design research-backed main experiment tables
---

# Main Experiment Table

Turn experimental evidence into one main-paper table whose structure makes the paper's central comparison easy to read. Preserve observed values and comparison semantics; do not invent runs, uncertainty, significance, or missing cells.

## Workflow

1. Inspect the result files and the intended main claim. Resolve metric direction/unit, repeat identity, uncertainty meaning, valid comparison groups, and which fields change scientific comparability.
2. Read [references/design-grammar.md](references/design-grammar.md) to define the comparison contract, row/column topology, value grammar, and emphasis scope. Then use [references/template-selection.md](references/template-selection.md) and inspect only the relevant examples in [references/pattern-catalog.md](references/pattern-catalog.md).
3. When input columns are ambiguous or heterogeneous, read [references/input-contract.md](references/input-contract.md). Normalize method identity separately from model, budget, data, protocol, source, or regime fields.
4. List the bundled designs:

   ```bash
   python scripts/generate_main_table.py list-templates
   ```

5. Create a small JSON config that declares metric semantics and any template-specific row fields. For custom layouts, read [references/template-schema.md](references/template-schema.md).
6. Generate the table and caption:

   ```bash
   python scripts/generate_main_table.py generate RESULTS.csv \
     --template benchmark-wide --config table.json --out output/main-table
   ```

7. Require `manifest.json.verification.valid = true`. Review `warnings` and `omitted_columns`; an omitted main-result column is a design decision, never a silent formatting side effect. Inspect `table.html` or compile `preview.tex` before returning the result.
8. Return the editable `table.tex`, `table.html`, `caption.txt`, `table-spec.json`, and manifest. State unresolved scientific assumptions separately from cosmetic choices.

## Design invariants

- Put stable identity/protocol fields on the left and measured evidence on the right.
- Keep `Model`, `Method`, `Budget`, `Pre-train Data`, `Protocol`, and `Source` separate when any of them changes comparability; do not concatenate them into a decorative method name.
- Choose methods-as-rows when systems outnumber benchmark groups. Choose datasets-as-rows when benchmarks outnumber the small set of focal systems.
- Use multi-level headers for genuine dimensions such as dataset × metric or metric family × dataset. Do not create hierarchy only to fill space.
- Compare best/second only inside a valid column or row group. Render missing evidence as `--`, never as zero, and exclude it from ranking.
- Treat row bands, separators, and shaded focal rows as semantic navigation: use them for method families, protocol regimes, or the focal method, never as arbitrary decoration.
- Define the ranking universe before applying bold or underline. Closed models, oracles, ensembles, literature-only values, or incompatible protocols may be displayed while explicitly excluded from ranking.
- When displaying a parenthesized delta, preserve the absolute result and declare its baseline and whether the delta is absolute or relative. Never replace the primary measurement with a percentage gain alone.
- Keep visual channels non-overlapping: a restrained row shade may locate the focal method, bold may mark best, and underline may mark second-best. Do not reuse one marker for provenance and significance.
- Do not mix single runs, mean ± SD, published point estimates, and reproduced runs without explicit source markers and caption/notes.
- Keep the caption factual: evaluation scope, aggregation/uncertainty, metric direction, emphasis semantics, and essential comparability constraints.
