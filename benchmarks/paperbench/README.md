# PaperBench: `(x, y)` pairs for academic table generation

PaperBench evaluates a generator `f` with `y' = f(x)` against the table published by an author, `y`.

## Input tiers

Not every paper releases raw runs. PaperBench therefore records the strongest available input instead of pretending all inputs are equivalent:

- `raw_runs`: per-seed or per-example experimental outputs; supports aggregation and uncertainty evaluation.
- `canonical_table`: de-styled cells, metric directions, comparison groups, and provenance; supports content selection and table design evaluation.
- `recovered_table`: cells recovered from a PDF/LaTeX source and manually verified; supports layout generation but not claims about experiment aggregation.

The bundled mini set contains three `recovered_table` cases and one `canonical_table` case. The latter is generated from RankUp's pinned author-released three-seed aggregate CSV and aligned with its published NeurIPS Table 1. It is a real seed set for end-to-end repository tests, not a statistically representative leaderboard.

## Case layout

```text
cases/<case-id>/
├── case.json           # provenance, task, input tier, reference location
├── x.json              # de-styled input to f(.)
├── y_reference.png     # published table crop
└── ratings.json        # optional human pairwise/rubric ratings
```

Generated artifacts are written to `output/paperbench/<case-id>/` and are not source data.

## Run

```bash
python benchmarks/paperbench/build_seed.py
python benchmarks/paperbench/build_rankup_case.py
python benchmarks/paperbench/evaluate.py
python benchmarks/paperbench/visualize.py
```

For true per-run inputs, use the deterministic long-form aggregator:

```bash
python benchmarks/paperbench/aggregate_runs.py runs.json --out x.json
```

It rejects duplicate run identifiers and single-run groups, computes sample standard deviation or standard error, and stores an `aggregation_audit` with every contributing run ID. Do not reconstruct pseudo-runs from published means and error bars.

## Evaluation dimensions

Objective metrics are computed from code and canonical cells:

- numeric recall and numeric precision;
- all-cell recall and header recall;
- hallucinated numeric token count;
- row/column and uncertainty-field preservation;
- render success.

Subjective dimensions use order-randomized human judgments:

- typography;
- visual hierarchy;
- readability;
- claim salience;
- overall aesthetics.

Automated visual proxies are reported separately and must not be called human aesthetics. See `protocol.md`.
