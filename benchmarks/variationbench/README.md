# VariationBench: simulated scenarios must never become evidence

VariationBench evaluates the narrow fallback used only when an author explicitly requests possible fluctuation but has no repeated-run evidence. It verifies deterministic, order-invariant Monte Carlo generation from an author-declared family, scale parameterization and source, bounds, future target, draw count, and seed.

The controlled case contains four observed point anchors. Two scenarios target one future run and two target the mean of four independent future runs. Every generated range remains `simulated_scenario_only`, visually labeled, rank-ineligible, inference-ineligible, and separate from verified results.

Sixteen controlled mutations reject inferred simulation requests, missing seeds or scale provenance, wrong normal/truncated-normal parameterization, too few draws, invalid bounds or run counts, duplicate cells, inference-oriented purposes, and provenance that falsely claims observed or verified status. They also verify seed sensitivity, input-order invariance, and permanent non-observed status.

Run:

```bash
python benchmarks/variationbench/build_case.py
python benchmarks/variationbench/validate.py
```
