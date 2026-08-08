# DataPlanBench: ask for the observations that matter

DataPlanBench evaluates whether PaperTable turns incomplete repeated-run evidence into a concrete acquisition request instead of imputing or simulating missing outcomes.

The controlled case contains six method–dataset groups with five declared paired seed IDs. It includes three missing paired runs, one invalid metric cell, pilot groups below the declared minimum, unequal observed variance, and one zero-variance pilot. The planner must repair existing pair IDs first, mark every precision count provisional, use Student-t mean intervals with the observed pilot SD, preserve the common paired grid, and send zero variance for author review.

Eleven controlled mutations test duplicate IDs, undeclared independence, wrong estimands, missing precision targets or variance/interval assumptions, hidden observed IDs/groups, invalid metric recovery, zero-SD safety, and repair-first author questioning.

Run:

```bash
python benchmarks/dataplanbench/build_case.py
python benchmarks/dataplanbench/validate.py
```
