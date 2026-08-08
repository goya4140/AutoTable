# PaperTable

PaperTable studies code-first generation of publication-quality academic tables. Given experimental data `x`, the Skill implements a generator `f` and produces `y' = f(x)`. PaperBench compares `y'` with the author's published table `y` along two deliberately separate axes:

- **objective fidelity**: were all values, headers, uncertainty fields, and valid comparisons preserved without hallucination?
- **subjective design quality**: is the table readable, well structured, visually polished, and effective at communicating its claim?

![PaperBench comparison](docs/assets/paperbench-comparison.png)

## What is included

- A reusable Codex Skill in [`skills/paper-table`](skills/paper-table).
- Deterministic JSON → LaTeX/HTML tables or SVG/PDF/PNG table-charts, with numeric verification.
- [`PaperBench`](benchmarks/paperbench): a versioned `(x,y)` dataset schema, real NeurIPS seed cases, evaluation scripts, human-rating protocol, and reference-vs-generated dashboard.
- [`StatBench`](benchmarks/statbench): exact author-run reconstructions plus explicitly ineligible source-drift diagnostics, without pretending a partial statistical artifact is a full visual-table gold pair.
- [`InferenceBench`](benchmarks/inferencebench): paired statistical comparisons, confidence intervals, multiplicity correction, and controlled rejection of pseudoreplication or unsafe significance markers.
- Candidate discovery manifests from official 2024 proceedings: a legacy 150-table NeurIPS index, a diversity-capped 200-table/30-paper NeurIPS index, and 25-table ICLR/ICML indexes. Discovery cases are explicitly kept separate from paired benchmark cases.
- External adapters/registry for TableVisBench and TABVERSE rather than silently relicensing their data.
- A [dataset landscape](docs/dataset-landscape.md) covering TableBank, PubTables-1M, SciTSR, TabLeX, SciGen, TABVERSE, TableVisBench, and TASTE.
- A detailed [table-generation dataset and evaluation survey](docs/table-generation-research.md), including task boundaries, metric failure modes, an inquiry benchmark, and implications for the next Skill design.

## Dataset semantics

PaperBench records the strongest available `x`:

| Input tier | Contains | What can be evaluated |
|---|---|---|
| `raw_runs` | per-seed or per-example results | aggregation, uncertainty, selection, and design |
| `canonical_table` | de-styled cells and semantic metadata | content selection, structure, and design |
| `recovered_table` | cells recovered from a paper and manually verified | layout/design only; no claim about experiment aggregation |

The committed mini set contains six NeurIPS 2024 pairs: three `recovered_table`, two `canonical_table`, and one genuine per-example `raw_runs` case. SWT-Bench reconstructs all 24 cells of published Table 4 from 1,656 model-instance records over a fixed 276-instance universe, with 273 countable gold-coverage instances. RankUp is built from a pinned author aggregate experiment log. AgentBoard is built from a separately pinned author-site JSON and an exact contiguous excerpt of the published table; its final-paper/source version mismatch is recorded instead of silently filling missing rows. This is an executable seed set, not yet a statistically representative leaderboard. Every case contains provenance, an `x.json`, a published `y_reference.png`, and an aesthetic rating record.

## Reproduce the benchmark

```bash
python benchmarks/paperbench/build_seed.py
python benchmarks/paperbench/build_rankup_case.py
python benchmarks/paperbench/build_agentboard_case.py
python benchmarks/paperbench/build_swtbench_case.py --artifact-dir /path/to/downloaded/swt-lite-zips
python benchmarks/paperbench/validate_cases.py
python benchmarks/paperbench/evaluate_controlled.py
python benchmarks/paperbench/evaluate_inquiry.py
python benchmarks/paperbench/evaluate.py
python benchmarks/paperbench/visualize.py
python benchmarks/statbench/validate.py
python benchmarks/inferencebench/validate.py
```

Outputs appear in `output/paperbench/`. The current reference run passes numeric, semantic-contract, provenance, and XeLaTeX physical-width gates on all 6/6 cases, with numeric/cell/header recall and numeric precision all `1.00` and zero hallucinated numeric tokens. SWT-Bench fits a 234.5pt single column at 225.5pt using three semantically named panels. Its raw input is recomputed during validation, and its blind public request contains only per-example observations while private scoring retains canonical `x.json`. PaperTable-Controlled detects all 46/46 deterministic mutations—including an audit-only provenance change—and InquiryBench's gold traces pass all 48/48 evaluator-separated scenarios.

StatBench contains two complementary cases. DIAMOND's 130 author-released Atari scores reproduce all 26 published cells exactly. TuneTables contributes a complete 5,880-record grid spanning 20 methods, 98 datasets, and three folds; it executes all six Table 1 aggregation formulas but intentionally fails exact-gold admission because the pinned post-publication author snapshot matches only 20/120 displayed cells. This makes version drift, hyperparameter tie-breaking, and false `verified` claims directly testable instead of hiding them behind numeric tolerance.

InferenceBench averages TuneTables' three folds before testing, producing 98 dataset-level pairs for four planned comparisons against TuneTables. Its deterministic sign-flip tests, paired bootstrap intervals, and Holm correction generate an editable inference table while controlled mutations reject missing pairs, undeclared independence, and skipped correction. A second controlled case adds 28 tasks nested in eight unequal independent-study clusters; it verifies intact-cluster randomization/bootstrap and an intentional direction reversal between equal-study and unit-weighted estimands. The TuneTables result remains explicitly tied to the drifted current snapshot rather than being presented as a reproduction of the paper-time critical-difference analysis.

The dashboard also shows a single model-based pilot visual rubric so the full reporting path is testable. It is labeled as **not human-validated**. Publication-quality aesthetic results require at least three order-randomized human ratings per pair following [`protocol.md`](benchmarks/paperbench/protocol.md).

## Generate one table

```bash
python skills/paper-table/scripts/analyze_data.py examples/main-results.csv --json
python skills/paper-table/scripts/optimize_layout.py examples/main-results.json --out-dir output/example --target-width-pt 469
python skills/paper-table/scripts/verify_table.py output/example/selected-spec.json output/example/table.tex
```

The optimizer compiles bounded typography candidates, measures the real LaTeX box, and produces `selected-spec.json`, editable LaTeX/HTML, PDF/PNG previews, `design-advice.json`, `layout-report.json`, and structural redesign advice when no readable candidate fits. If typography alone fails, it can split metrics at semantic group boundaries, repeat identity columns, or wrap long identity text without abbreviation. It automatically accepts at most three stacked panels and never silently inserts whole-table scaling.

For a single dominant metric or signed delta, generate a code-first table-chart:

```bash
python skills/paper-table/scripts/design_advisor.py examples/accuracy-gain.json
python skills/paper-table/scripts/render_table_chart.py examples/accuracy-gain.json --out-dir output/accuracy-gain
python skills/paper-table/scripts/verify_table.py examples/accuracy-gain.json output/accuracy-gain/table-chart.svg
```

This route preserves exact labels while adding honest position encoding. It exports editable SVG, PDF, PNG, and a structured `chart-spec.json`; unresolved metric direction/unit or a multi-metric lookup request is rejected.

The Skill actively asks for missing repeats, units, metric direction, sample size, comparison design, and intended claim. Simulated variation must be labeled and cannot be used as observed evidence.

## Scale the real-paper set

```bash
python benchmarks/neurips-tables/collect.py --year 2024 --papers 50 --max-tables 200 --max-tables-per-paper 8 \
  --out benchmarks/neurips-tables/index-diverse-2024.jsonl
python benchmarks/neurips-tables/annotate.py benchmarks/neurips-tables/index-diverse-2024.jsonl \
  --legacy-development-index benchmarks/neurips-tables/index.jsonl \
  --out benchmarks/neurips-tables/annotations-diverse-2024.jsonl \
  --summary benchmarks/neurips-tables/annotations-summary-2024.json \
  --audit-queue benchmarks/neurips-tables/audit-queue-2024.jsonl
python benchmarks/neurips-tables/validate_annotations.py \
  benchmarks/neurips-tables/index-diverse-2024.jsonl \
  benchmarks/neurips-tables/annotations-diverse-2024.jsonl \
  --legacy-development-index benchmarks/neurips-tables/index.jsonl \
  --summary benchmarks/neurips-tables/annotations-summary-2024.json \
  --audit-queue benchmarks/neurips-tables/audit-queue-2024.jsonl
```

The diversity-capped NeurIPS set contains 200 records from 30 papers; 121 records from 17 previously unseen papers form a prospective stress partition. Its purpose/form labels are explicitly weak, 26 likely narrative false positives are retained as negative cases, and the 40-item audit queue remains pending. The collector stores PDFs/crops in ignored local caches. A discovered table becomes a PaperBench pair only after a structured `x` is linked and verified.

`evaluate_annotations.py` can score routing predictions against the public weak labels for CI regression, but its report is permanently marked diagnostic-only and leaderboard-ineligible. Numeric fidelity and aesthetic claims still require PaperBench pairs and blinded human evaluation respectively.

Optional external stress test:

```bash
python benchmarks/external/import_tablevisbench.py --limit 20
```

## Evaluation policy

- Numeric fidelity is a hard gate, never hidden inside an aesthetic average.
- Automated contrast/density/aspect measures are called visual proxies, not aesthetics.
- Human comparisons randomize left/right order and report agreement and position bias.
- Train/reference/test splits are paper-level to prevent same-paper style leakage.
- `y` and its LaTeX source remain hidden until `y'` is frozen.
- Blind runs use separate public/private roots and reject any post-freeze byte change.

## License

Code is MIT. Source papers and external datasets retain their original terms. Each benchmark case records provenance and redistribution status; this repository does not relicense source publications.
