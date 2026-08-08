# Active data-acquisition planning

Use `scripts/plan_more_data.py` when an author wants uncertainty but the repeated-run grid is incomplete, or asks how many additional independent runs to collect. Request observations; never invent outcomes.

Require the author to declare:

- what one independent repeat represents and why repeats are independent;
- group keys, run-ID key, expected groups, and expected run IDs;
- fixed-across-groups or group-specific pairing;
- metric direction and scientific unit;
- target estimand (`group_mean` for the current planner; paired differences require another plan);
- confidence level and target CI half-width for every metric;
- minimum pilot size and maximum run budget;
- acknowledgement that pilot sample SD is assumed stable for planning only.
- acknowledgement that a Student-t mean interval is appropriate for the repeat distribution.

Execute acquisition in two phases. First request every missing existing group–run cell and every invalid metric. For fixed pairing, complete the union or declared set of existing run IDs across all expected groups. Then recompute the plan from repaired observations before starting new IDs.

Second, project total runs for each group mean with the two-sided Student-t interval `mean ± t * s / sqrt(n)`, using the observed pilot sample SD. Do not use this formula to plan the precision of a paired method difference. Search integer total runs up to the author cap. Require the author to judge this interval appropriate; a small strongly skewed or heavy-tailed pilot needs a different plan. Treat the result as provisional: future SD and realized interval width can change. Do not describe it as power, guaranteed precision, or proof that the experiment is adequately replicated.

Require at least the declared pilot count before variance-based projection. If pilot SD is zero, return `zero_pilot_variance_requires_review`; never conclude that zero additional runs are needed. If the target cannot be reached within the cap, ask whether to raise the cap or relax the target instead of silently changing either.

For fixed pairing, use the largest provisional requirement across cells and request each new run ID for every expected group. Do not invent concrete seed values: report the number of new paired IDs and let the author allocate identifiers. Preserve the raw-run and planning-report hashes, and rerun both the acquisition planner and `aggregate_runs.py` when observations arrive.

Reference: [NIST confidence limits for a mean](https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm).
