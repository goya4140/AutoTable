# Evaluation

Score each artifact from 0 to 2 on six axes: numeric faithfulness, comparison validity, hierarchy, readability at target width, claim salience, and editability/reproducibility. Numeric faithfulness is a hard gate: any unexplained changed value makes the example fail.

Use `benchmarks/paperbench/` for `(x,y)` generation evaluation. Record whether `x` contains raw runs, a canonical table, or cells recovered from the publication; never compare these tiers as if they test the same capability. Freeze `y'` before revealing `y`, split by paper, and keep numeric fidelity as a hard gate.

Use `benchmarks/neurips-tables/collect.py` only for candidate discovery. A captioned crop without structured `x` is not a generation pair and must not enter the PaperBench leaderboard.
