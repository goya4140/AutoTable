# Active data-acquisition planning

Use this workflow when an author wants uncertainty but the repeated-run grid is incomplete, or asks how many additional independent runs to collect. Request observations; never invent outcomes.

Choose the planner by estimand:

- Use `scripts/plan_more_data.py` for the precision of each method–context group mean.
- Use `scripts/plan_paired_difference.py` for the precision of a within-run candidate-minus-baseline mean difference. Require one baseline, a predeclared candidate list, expected contexts, and fixed run IDs shared by every method.

Do not choose the route from whichever provisional run count is smaller. Ask which scientific quantity the author intends to estimate before inspecting the result.

Require the author to declare:

- what one independent repeat represents and why repeats are independent;
- group keys, run-ID key, expected groups, and expected run IDs;
- fixed-across-groups or group-specific pairing;
- metric direction and scientific unit;
- target estimand (`group_mean` or `paired_mean_difference`);
- confidence level and target CI half-width for every metric;
- minimum pilot size and maximum run budget;
- acknowledgement that pilot sample SD is assumed stable for planning only.
- acknowledgement that a Student-t mean interval is appropriate for the repeat distribution.

Execute acquisition in two phases. First request every missing existing group–run cell and every invalid metric. For fixed pairing, complete the union or declared set of existing run IDs across all expected groups. Then recompute the plan from repaired observations before starting new IDs.

Second, project total observations with the two-sided Student-t interval `mean ± t * s / sqrt(n)`. For `group_mean`, use the group's pilot sample SD. For `paired_mean_difference`, first align candidate and baseline by run ID, orient each difference so positive favors the candidate, and use the sample SD of those paired differences. Never substitute either method's marginal SD for paired-difference SD. Search integer totals up to the author cap. Require the author to judge the interval appropriate for the relevant repeat or difference distribution; a small strongly skewed or heavy-tailed pilot needs another plan. Treat the result as provisional: future SD and realized interval width can change. Do not describe it as power, guaranteed precision, or proof that the experiment is adequately replicated.

Require at least the declared pilot count before variance-based projection. If pilot SD is zero, return the planner's explicit zero-variance review status; never conclude that zero additional runs are needed. If the target cannot be reached within the cap, ask whether to raise the cap or relax the target instead of silently changing either. Never report a provisional total smaller than the already declared run-ID set.

For fixed pairing, use the largest provisional requirement across cells. A group-mean plan requests each new ID for every expected group. A paired-difference plan requests each new ID for the baseline and every declared candidate in every context, so no comparison acquires an unmatched run. Do not invent concrete seed values: report the number of new paired IDs and let the author allocate identifiers. Preserve the raw-run and planning-report hashes, and rerun both the acquisition planner and `aggregate_runs.py` when observations arrive.

References: [NIST confidence limits for a mean](https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm) and [NIST confidence interval for paired samples](https://www.itl.nist.gov/div898/handbook/prc/section3/prc312.htm).
