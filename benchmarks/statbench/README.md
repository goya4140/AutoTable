# StatBench: raw repeated runs to published cells

StatBench isolates the scientific aggregation stage that precedes table design. An exact-gold case is admitted only when an author-released artifact contains genuinely repeated measurements and every recomputed cell maps exactly to a published NeurIPS table. Separately labeled drift diagnostics exercise the same formulas while proving why a later source snapshot must not be counted as exact gold.

This benchmark is deliberately separate from PaperBench. It does not claim an aesthetic `(x, y)` pair when the released raw artifact covers only one method or one slice of a larger published table.

## Current cases

`neurips24-diamond-atari` uses the DIAMOND authors' 26-game Atari 100k result file. The paper states that each game was trained from scratch with five random seeds. The 130 released scores reproduce all 26 DIAMOND cells in Table 1 after mean aggregation and one-decimal display rounding.

`neurips24-tunetables-tabzilla` is a deliberately non-gold drift diagnostic. It contains a complete 20-method × 98-dataset × 3-fold grid (5,880 selected test scores) derived from the authors' pinned post-publication results repository. The published Table 1 formulas—mean accuracy, mean rank, fold-level Z-score mean/population standard deviation/median, and strict wins—are executable. The current snapshot matches only 20 of 120 published cells exactly at displayed precision, so validation requires `published_exact_gold: false` and a blocking action instead of silently applying tolerances.

The TuneTables source exposes another reproducibility hazard: 135 of 294 ExcelFormer dataset-folds have multiple trials tied for best validation accuracy. The checked-in reconstruction uses the lowest trial number as an explicit deterministic tie-break and never selects on test accuracy. Because the paper-time tie-break and exact snapshot are unavailable, this case tests whether the Skill reports the limitation rather than claiming a verified reproduction.

Together the cases check:

- explicit independence and repeat-unit declarations;
- unique seed identifiers and exactly five seeds per game;
- a fixed seed-index set across games;
- finite raw values, sample SD, SE, and a hashed cell-level run audit;
- exact agreement with every published DIAMOND cell;
- no imputation and no invented uncertainty display.
- complete method-by-dataset-fold pairing;
- average ranks, population Z-scores, medians, stability, and strict unique wins;
- source-snapshot drift detection and exact-gold admission refusal;
- validation-only hyperparameter selection with an explicit tie policy.

Run:

```bash
python benchmarks/statbench/validate.py
```

Rebuild the derived payload and expected spec:

```bash
python benchmarks/statbench/build_diamond_case.py
```

The checked-in `author_DIAMOND.json` is preserved byte-for-byte from the pinned author repository. `raw_runs.json` assigns positional `seed_index` identifiers to the five released values; this identifier is an ordering label, not a claim about the authors' internal seed numbers.
