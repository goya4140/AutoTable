# DataPlanBench: ask for the observations that matter

DataPlanBench evaluates whether PaperTable turns incomplete repeated-run evidence into a concrete acquisition request instead of imputing or simulating missing outcomes.

Two controlled cases reuse the same six method–dataset groups and five declared seed IDs but target different estimands. Both include three missing runs and one invalid metric cell. The group-mean case tests marginal pilot SD, groups below the declared minimum, and a zero-variance pilot. The paired-difference case aligns every candidate with the baseline by seed, tests direction-aware improvements, and uses the SD of paired differences. Both must repair existing IDs first, preserve the common grid, mark counts provisional, and send zero variance for author review.

Twenty-three controlled mutations test duplicate IDs, undeclared independence, wrong estimands, missing precision targets or variance/interval assumptions, hidden observed IDs/groups/methods, invalid metric recovery, lower-is-better orientation, zero-SD safety, and repair-first author questioning.

Run:

```bash
python benchmarks/dataplanbench/build_case.py
python benchmarks/dataplanbench/validate.py
```
