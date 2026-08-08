# Dataset landscape and design choices

For the full task taxonomy, dataset audit, metric failure analysis, inquiry evaluation, and proposed benchmark architecture, see [the detailed table-generation survey](table-generation-research.md).

PaperTable is a generation benchmark, not a table-recognition benchmark. The distinction matters: recognition datasets usually define `image → structure`, while we need `experimental data → publication table`.

| Dataset/work | Available pairing | Scale | What PaperTable borrows | Why it is not sufficient alone |
|---|---:|---:|---|---|
| [TableBank](https://github.com/doc-analysis/TableBank) | document/LaTeX ↔ table image | 417K tables | weakly supervised extraction and explicit splits | optimized for detection/recognition, not design preference |
| [PubTables-1M](https://github.com/microsoft/table-transformer) | cells, boxes, roles ↔ rendered tables | 947K annotated tables | canonical cells, header roles, complete geometry | biomedical papers; no author design intent or raw runs |
| [SciTSR](https://github.com/Academic-Hammer/SciTSR) | LaTeX-derived cells/relations ↔ PDF/image | 15K tables | spanning-cell structure and relation evaluation | recognition task, not generation aesthetics |
| [TabLeX](https://arxiv.org/abs/2105.06400) | LaTeX ↔ rendered scientific table | millions | deterministic source-to-image pairing | source retains the target styling, causing leakage for generation |
| [SciGen](https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/hash/149e9677a5989fd342ae44213df68868-Abstract-round2.html) | scientific table ↔ description | large scientific corpus | scientific-table extraction and context | output is text rather than table design |
| [TABVERSE](https://huggingface.co/datasets/MBZUAI/TABVERSE) | canonical JSON ↔ HTML/Markdown/LaTeX images | 629 unique tables | controlled content across renderers | generic tables, not author-designed ML result tables |
| [TableVisBench](https://huggingface.co/datasets/lntzm/TableVisBench) | source table ↔ creative visualization | 800 cases | data-fidelity plus aesthetic evaluation | infographic-style output; CC BY-NC 4.0 external data |
| [TASTE](https://github.com/purvanshi-lica/taste) | design candidates ↔ multi-axis designer preferences | 9 criteria | criterion-level preferences, agreement and position-bias checks | generic graphic design rather than academic tables |

## PaperBench's contribution

PaperBench adds the missing experimental-paper layer:

- explicit input tiers (`raw_runs`, `canonical_table`, `recovered_table`);
- paper, venue, page, table, and hash provenance;
- valid comparison groups, metric directions, uncertainty semantics, and claim intent;
- hard-gated numeric fidelity plus separate structure metrics;
- order-randomized human aesthetics instead of an unvalidated scalar image score;
- paper-level leakage prevention;
- published `y` versus frozen code-generated `y'` comparison artifacts.

Its executable mini set currently has six NeurIPS 2024 pairs: three honestly labeled PDF-recovered layout cases, two pinned author-artifact `canonical_table` cases, and one per-example `raw_runs` case. SWT-Bench reconstructs 24 published cells from 1,656 model-instance records with fixed 276/273 denominators and cell-level aggregation audits. Candidate promotion requires exact artifact-to-cell mapping and final-paper agreement. Public code alone is insufficient; incomplete seeds, mutable dashboards, and author-data/final-paper version drift are recorded as limitations instead of repaired with guessed or PDF-copied values.

PaperTable-Discovery complements—but does not enlarge—the paired leaderboard. Its diversity-capped NeurIPS 2024 manifest contains 200 records from 30 papers, with at most eight tables per paper. The 121-record prospective partition comes from 17 papers absent from the legacy development index. Rule-based purpose/form annotations, caption false-positive flags, crop contamination signals, and a pending 40-item audit queue support routing and extraction stress tests; all records explicitly set `gold: false` and `paperbench_generation_pair: false`.

## Scaling plan

1. Use official NeurIPS/ICLR/ICML proceedings to discover tables.
2. Match papers to author repositories or artifacts and prioritize cases with released per-seed CSV/JSON.
3. Fall back to LaTeX/PDF cell recovery only when the input tier is recorded honestly.
4. Curate train/reference/test by paper and research area.
5. Collect at least three independent human ratings per test pair before publishing aesthetic leaderboard claims.
