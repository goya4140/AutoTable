# Audited inference routing

Use inferential output only after fixing the estimand, independent sampling unit, pairing, planned comparison family, and multiplicity policy. A p-value is not a styling input.

| Observed structure | Required route | Randomization/bootstrap unit |
|---|---|---|
| One complete pair per independent unit | `paper-table-paired-inference-v1` | paired unit |
| Multiple paired units nested in independent clusters | `paper-table-paired-inference-v2` | intact cluster |
| Three or more methods on the same independent complete blocks | `paper-table-multimethod-inference-v1` | method labels within block; paired blocks for post-hoc |
| Cross-classified, overlapping, longitudinal, or multiple clustering | stop and request a predeclared specialist model | unsupported |

For v1, require `paired_sign_flip_mean`, paired-sign exchangeability, and `paired_percentile_bootstrap_mean`. Do not treat folds or examples as independent units.

For v2, require `cluster_sign_flip_mean`, cluster-sign exchangeability, and `cluster_percentile_bootstrap_mean`. Require at least four independent clusters. Flip every nested difference in one cluster together and resample intact clusters; never randomize or bootstrap nested units independently.

Declare one cluster estimand before looking at results:

- `equal_cluster_mean`: average within each cluster, then give every independent cluster equal weight. Use for a claim about the average study, subject, or site.
- `unit_weighted_mean`: average all nested units, so large clusters contribute more. Use for a claim about the average nested task or observation under the observed cluster-size distribution.

When unequal cluster sizes make the conclusions differ, render the primary estimand and a clearly labeled sensitivity column. Never attach the primary estimand's p-value to the sensitivity effect. Ask the author which population-level claim matters; do not choose the weighting because it produces significance.

For three or more methods, require one score per method in every independent block. Resolve exact ties with average within-block ranks. Run the `friedman_block_permutation` omnibus by permuting method labels independently inside each block; declare and justify label exchangeability under the global null. Use exact enumeration only when the full unique configuration space is bounded; otherwise use deterministic Monte Carlo with the plus-one p-value.

Fix one baseline and every baseline-versus-other comparison before outcome inspection. Require the omnibus rejection gate, then apply Holm to the entire planned post-hoc family. Retain post-hoc estimates and adjusted p-values when the gate fails for audit, but render no stars or rejection claims. Post-hoc effects and intervals use original scores—not ranks—so the table remains interpretable in the scientific unit. Do not silently replace baseline-vs-all with selected pairs or all-pairs comparisons.

For every supported route, record exact versus Monte Carlo mode, random seed, evaluated sample count, unit/cluster/block hashes, effect orientation, interval method and level, resampling unit, family ID, correction, and alpha. Use Holm correction for multiple planned candidate-versus-baseline comparisons. Render enough p-value precision to avoid numeric zero.

Cluster bootstrap references: [Cheng, Yu, and Huang (2013)](https://doi.org/10.1016/j.jmva.2012.09.003) and [Flynn et al. (2005)](https://pmc.ncbi.nlm.nih.gov/articles/PMC535558/). The latter also cautions that bootstrap interval performance can be poor with few clusters; report cluster count and avoid claiming that more resamples compensate for too few independent clusters.

Multi-method references: [Friedman (1937)](https://doi.org/10.1080/01621459.1937.10503522), [Demšar (2006)](https://www.jmlr.org/papers/v7/demsar06a.html), and [Phipson and Smyth (2010)](https://doi.org/10.2202/1544-6115.1585).
