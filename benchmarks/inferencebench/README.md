# InferenceBench: statistical claims before table decoration

InferenceBench evaluates whether PaperTable can turn paired experimental evidence into an auditable inferential report without pseudoreplication, test-set selection, missing pairs, or uncorrected significance markers.

The first case derives dataset-level scores from the pinned TuneTables StatBench snapshot. Three OpenML folds are averaged before inference, leaving 98 paired dataset units. TuneTables is the declared baseline and four prominent alternatives form one planned comparison family. The executable contract uses:

- a two-sided paired sign-flip test of mean differences;
- exact enumeration for small samples and deterministic Monte Carlo with the plus-one p-value correction otherwise;
- paired percentile-bootstrap intervals over complete dataset units;
- Holm correction across the declared family;
- positive oriented effects meaning the candidate improves on the baseline;
- no significance stars unless pairing, independence, multiplicity, and provenance gates all pass.

Five TuneTables safety mutations remove a pair, hide independence, skip Holm correction, remove the sign-exchangeability rationale, or introduce nested pseudoreplicated units. Every mutation must fail before rendering.

The second case is deterministic synthetic gold for clustered designs. It contains 28 paired tasks nested in eight independent studies of unequal size. Its v2 contract flips signs and bootstraps intact studies. A deliberately volume-biased method has a negative equal-study effect but a positive unit-weighted effect, so the evaluator can detect silent estimand changes. Six more mutations test missing pairs, unknown cluster independence, missing weighting, missing exchangeability, unit-level randomization, and skipped Holm correction.

This is a current-snapshot inferential diagnostic, not a reproduction of the paper's critical-difference figure. The source snapshot itself is already marked version-drifted in StatBench.

Run:

```bash
python benchmarks/inferencebench/build_tunetables_case.py
python benchmarks/inferencebench/build_clustered_case.py
python benchmarks/inferencebench/validate.py
```
