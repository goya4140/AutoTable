# StatBench: raw repeated runs to published cells

StatBench isolates the scientific aggregation stage that precedes table design. A case is admitted only when an author-released artifact contains genuinely repeated measurements and the recomputed cells can be mapped exactly to a published NeurIPS table.

This benchmark is deliberately separate from PaperBench. It does not claim an aesthetic `(x, y)` pair when the released raw artifact covers only one method or one slice of a larger published table.

## Current case

`neurips24-diamond-atari` uses the DIAMOND authors' 26-game Atari 100k result file. The paper states that each game was trained from scratch with five random seeds. The 130 released scores reproduce all 26 DIAMOND cells in Table 1 after mean aggregation and one-decimal display rounding.

The case checks:

- explicit independence and repeat-unit declarations;
- unique seed identifiers and exactly five seeds per game;
- a fixed seed-index set across games;
- finite raw values, sample SD, SE, and a hashed cell-level run audit;
- exact agreement with every published DIAMOND cell;
- no imputation and no invented uncertainty display.

Run:

```bash
python benchmarks/statbench/validate.py
```

Rebuild the derived payload and expected spec:

```bash
python benchmarks/statbench/build_diamond_case.py
```

The checked-in `author_DIAMOND.json` is preserved byte-for-byte from the pinned author repository. `raw_runs.json` assigns positional `seed_index` identifiers to the five released values; this identifier is an ordering label, not a claim about the authors' internal seed numbers.
