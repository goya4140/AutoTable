# PaperBench: `(x, y)` pairs for academic table generation

PaperBench evaluates a generator `f` with `y' = f(x)` against the table published by an author, `y`.

## Input tiers

Not every paper releases raw runs. PaperBench therefore records the strongest available input instead of pretending all inputs are equivalent:

- `raw_runs`: per-seed or per-example experimental outputs; supports aggregation and uncertainty evaluation.
- `canonical_table`: de-styled cells, metric directions, comparison groups, and provenance; supports content selection and table design evaluation.
- `recovered_table`: cells recovered from a PDF/LaTeX source and manually verified; supports layout generation but not claims about experiment aggregation.

The bundled mini set contains three `recovered_table`, two `canonical_table`, and one `raw_runs` case. SWT-Bench reconstructs published Table 4 from author-released per-instance reports: 6 models × 276 instances produce 1,656 records, while change coverage uses the 273 instances with countable gold coverage. RankUp is generated from a pinned author-released three-seed aggregate CSV. AgentBoard maps a pinned author-site JSON to the exact Table 3 header and first two contiguous rows; the case is deliberately restricted because the source has 13 models while the final paper has 19. These are real seed cases for end-to-end repository tests, not a statistically representative leaderboard.

## Case layout

```text
cases/<case-id>/
├── case.json           # provenance, task, input tier, reference location
├── raw_outcomes.json   # optional public raw input for raw_runs cases
├── x.json              # de-styled input to f(.) with metric units/directions
├── y_reference.png     # published table crop
└── ratings.json        # optional human pairwise/rubric ratings
```

Generated artifacts are written to `output/paperbench/<case-id>/` and are not source data.

## Run

```bash
python benchmarks/paperbench/build_seed.py
python benchmarks/paperbench/build_rankup_case.py
python benchmarks/paperbench/build_agentboard_case.py
python benchmarks/paperbench/build_swtbench_case.py --artifact-dir /path/to/downloaded/swt-lite-zips
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

For generation, each submission directory must contain `submission.json` with `request_id` and `candidate_spec`, plus editable `table.tex`. A `raw_runs` public request carries the hashed raw payload named by `case.json`; its canonical `x.json`, reference crop, and recomputed gold stay private. For inquiry, `submission.json` is the trace schema accepted by `evaluate_inquiry.py`; the current six-case set produces 48 sanitized scenarios.

Every prepared episode randomly remaps request IDs so they cannot be enumerated back to public case/field names. The freeze manifest hashes every submission file and the public episode. Scoring fails if a request, manifest, directory, or output changes after freezing. Public and private roots must be non-nested. This is an artifact firewall, not an operating-system sandbox: leaderboard execution should additionally disable network access and mount the private root only for the scorer.

### Executable multi-turn inquiry

Run an adapter against a simulated author instead of submitting a self-reported trace:

```bash
python benchmarks/paperbench/blind_protocol.py prepare \
  --mode inquiry --public-dir output/inquiry/public --private-dir output/inquiry/private

python benchmarks/paperbench/run_interaction.py \
  --public-dir output/inquiry/public --private-dir output/inquiry/private \
  --output-dir output/inquiry/submissions \
  --adapter python benchmarks/paperbench/baselines/rule_inquiry_adapter.py
```

The runner appends `TURN_REQUEST.json TURN_RESPONSE.json` to the adapter command. An adapter returns either:

- `{"action":"ask","questions":[{"field_id":"...","text":"..."}]}`; or
- `{"action":"submit","candidate_spec":{...},"resolved_fields":{...},"used_answer_fields":[],"assumed_fields":[],"applied_answer_fields":[],"final_status":"verified"}`.

The simulated author answers only fields actually hidden in that scenario and returns `unavailable` for irrelevant questions. Scoring verifies the trace, the resolved value, the final semantic contract, rendered numeric fidelity, and field-specific output evidence. Merely claiming that an answer was used does not pass. The bundled rule adapter is an executable protocol baseline; it detects missing semantics only from the public request and never receives scenario gold.

For true per-run inputs, use the deterministic long-form aggregator:

```bash
python skills/paper-table/scripts/aggregate_runs.py runs.json --out x.json
```

It rejects duplicate run identifiers and single-run groups, computes sample standard deviation or standard error, and stores an `aggregation_audit` with every contributing run ID. Do not reconstruct pseudo-runs from published means and error bars.

For per-example observations with fixed dataset denominators, use:

```bash
python skills/paper-table/scripts/aggregate_observations.py raw_outcomes.json --out x.json
```

It rejects duplicate observation identities and missing denominator members, then records the formula, denominator, sufficient statistic, and observation-ID hash for every output cell. Examples are not independent seeds and do not justify between-run uncertainty.

## Evaluation dimensions

Objective metrics are computed from code and canonical cells:

- numeric recall and numeric precision;
- all-cell recall and header recall;
- hallucinated numeric token count;
- row/column and uncertainty-field preservation;
- render success.
- measured tabular width/body-height fit, selected typography candidate, panel count, structural transform, and width utilization.
- recommended visual form plus unresolved design warnings/questions, reported as diagnostics rather than self-scored aesthetics.

The scientific gate additionally requires the semantic contract to preserve metric units/directions, uncertainty type, comparison eligibility, emphasis scope, provenance, and (for raw runs) aggregation audit. A legal multi-panel candidate repeats identity columns and covers every metric exactly once in canonical order. It may pack adjacent complete metric groups together, but it cannot place a partial group beside another group; this keeps paired outcomes intact without forcing one panel per task. The separate publication-readiness gate also requires the XeLaTeX-measured table to fit its declared width and tabular-body height without whole-table scaling; the reference optimizer automatically accepts no more than three stacked panels. `controlled/cases.jsonl` contains deterministic negative cases that prove each failure class is detectable.

`inquiry/requests.jsonl` is a committed development set with one author-provided field removed; it strips paper identity, URLs, source commits, reference metadata, and inquiry-profile answers. Always distribute a freshly prepared blind episode—not these static files—for reported evaluation. `inquiry/scenarios.jsonl` is evaluator-only gold. An interaction trace records asked, answered, used, applied, and assumed fields plus its final status. The scorer measures whether the generator asks high-value questions, avoids unsupported inference, repeated/irrelevant questions, and impossible traces such as using an answer it never requested, then stops at the right time.

Subjective dimensions use order-randomized human judgments:

- typography;
- visual hierarchy;
- readability;
- claim salience;
- overall aesthetics.

Automated visual proxies are reported separately and must not be called human aesthetics. See `protocol.md`.
