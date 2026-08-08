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
├── x.json              # de-styled input to f(.) with metric units/directions
├── y_reference.png     # published table crop
└── ratings.json        # optional human pairwise/rubric ratings
```

Generated artifacts are written to `output/paperbench/<case-id>/` and are not source data.

## Run

```bash
python benchmarks/paperbench/build_seed.py
python benchmarks/paperbench/build_rankup_case.py
python benchmarks/paperbench/validate_cases.py
python benchmarks/paperbench/build_controlled.py
python benchmarks/paperbench/evaluate_controlled.py
python benchmarks/paperbench/build_inquiry.py
python benchmarks/paperbench/evaluate_inquiry.py
python benchmarks/paperbench/evaluate.py
python benchmarks/paperbench/visualize.py
```

## Blind evaluation

Use the three-stage protocol when comparing generators. Keep the private directory unavailable to the generator until after freezing:

```bash
python benchmarks/paperbench/blind_protocol.py prepare \
  --mode generation --public-dir output/blind/public --private-dir output/blind/private

# Give only output/blind/public to the generator. It writes one directory per opaque request ID.

python benchmarks/paperbench/blind_protocol.py freeze \
  --public-dir output/blind/public --submissions-dir output/blind/submissions \
  --frozen-manifest output/blind/frozen.json

python benchmarks/paperbench/blind_protocol.py score \
  --public-dir output/blind/public --private-dir output/blind/private \
  --submissions-dir output/blind/submissions --frozen-manifest output/blind/frozen.json \
  --report output/blind/report.json
```

For generation, each submission directory must contain `submission.json` with `request_id` and `candidate_spec`, plus editable `table.tex`. For inquiry, `submission.json` is the trace schema accepted by `evaluate_inquiry.py`. Use `--mode inquiry` to prepare the 32 sanitized InquiryBench requests.

The freeze manifest hashes every submission file and the public episode. Scoring fails if a request, manifest, directory, or output changes after freezing. Public and private roots must be non-nested. This is an artifact firewall, not an operating-system sandbox: leaderboard execution should additionally disable network access and mount the private root only for the scorer.

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

The scientific gate additionally requires the semantic contract to preserve metric units/directions, uncertainty type, comparison eligibility, emphasis scope, provenance, and (for raw runs) aggregation audit. `controlled/cases.jsonl` contains deterministic negative cases that prove each failure class is detectable.

`inquiry/requests.jsonl` contains model-visible inputs with one author-provided field removed; it uses opaque request IDs and exposes neither the missing field nor the inquiry-profile answers. `inquiry/scenarios.jsonl` is evaluator-only gold. An interaction trace records asked, answered, used, and assumed fields plus its final status. The scorer measures whether the generator asks high-value questions, avoids unsupported inference, repeated/irrelevant questions, and impossible traces such as using an answer it never requested, then stops at the right time.

Subjective dimensions use order-randomized human judgments:

- typography;
- visual hierarchy;
- readability;
- claim salience;
- overall aesthetics.

Automated visual proxies are reported separately and must not be called human aesthetics. See `protocol.md`.
