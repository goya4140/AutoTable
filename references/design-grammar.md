# Main-table design grammar

A strong main table is a compact scientific argument. Design it in this order; visual styling is the final layer, not the first.

## 1. Comparison contract

Write down the valid ranking universe before arranging cells.

- Which rows share the same task, data, supervision, backbone, budget, and evaluation protocol?
- Are proprietary systems, oracles, ensembles, literature-only results, or incompatible settings shown only as references?
- Is best/second-best computed globally, within a method family, or among open/reproducible systems?
- What is the explicit baseline for every delta, speedup, or relative improvement?

Display a scientifically useful reference even when it is excluded from ranking, but state that exclusion in the caption.

## 2. Row topology

The left side answers "what exactly was run?"

- Use separate identity columns when model, method, backbone, data, budget, protocol, or source changes comparability.
- Use full-width family bands when readers primarily need to scan categories such as proprietary / general / multimodal / agentic systems.
- Use whitespace or midrules for lighter distinctions such as prior work / reproduced baselines / ours.
- Use a restrained focal-row shade only to locate the proposed system. It must not substitute for numerical emphasis.

## 3. Column topology

The right side answers "what happened?"

- `dataset → metric` supports benchmark-by-benchmark reading.
- `metric family → dataset` supports quality-efficiency or clean-robustness trade-offs.
- Put `Avg.` at the end of a benchmark block only when its macro/micro/weighted definition is known.
- Keep quality, absolute cost, and relative speedup separate. Do not collapse them into a decorative composite score.

## 4. Value grammar

Choose one primary representation per evidence type:

```text
87.4                 point estimate
87.4 ± 0.3           mean ± declared SD/SE
87.4 [86.9, 87.9]    estimate + confidence interval
87.4 (+2.1)          absolute result + absolute-point delta
87.4 (+2.5%)         absolute result + relative delta
1.43×                ratio or speedup
```

Never infer uncertainty or significance. Define precision and unit per metric. Rank on unrounded values, then format. Missing, not applicable, and failed experiments are different states; the current renderer reserves `--` for unavailable evidence.

## 5. Emphasis grammar

Recommended default:

- focal-row shade: locate the proposed method;
- bold: best within the declared ranking universe;
- underline: second-best within that universe;
- `*`, `†`, `‡`: only for explicitly documented significance, provenance, or protocol differences.

Ties share a marker. Color is secondary and the table must remain intelligible in grayscale.

## 6. Caption contract

The caption must explain evaluation scope, grouping, metric direction, uncertainty and run count, missingness, ranking universe, marker semantics, and every auxiliary delta. Put hardware/protocol details in a note when they are essential but too long for headers.

## 7. Visual QA

Compile the actual LaTeX. Check that group bands span the full table, focal shading does not hide rules, multi-level headers align with their evidence columns, numbers remain readable after width fitting, and the table still has a clear scan path in grayscale.
