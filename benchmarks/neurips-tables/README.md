# NeurIPS Tables benchmark

This directory is a candidate-discovery layer for accepted NeurIPS, ICLR, and ICML papers. It is not itself a paired generation benchmark. The collector uses official proceedings pages and materializes source PDFs, caption anchors, text regions, and table crops locally.

The committed `index.jsonl` is a provenance manifest. Cached PDFs and crops are ignored because source papers retain their original terms.

## Collection

```bash
python collect.py --year 2024 --papers 50 --max-tables 200
python collect.py --venue iclr --year 2024 --papers 50 --max-tables 200
python collect.py --venue icml --year 2024 --papers 50 --max-tables 200
```

Sampling is deterministic. Promote a candidate to `benchmarks/paperbench/cases/` only after a structured `x` is linked and manually verified.

The committed manifests currently contain 150 NeurIPS, 25 ICLR, and 25 ICML candidates from 2024. Caption anchoring is intentionally high-recall and can include surrounding text or a displaced float; visual QA is mandatory before promotion.

## Metrics

- numeric faithfulness: exact normalized cell match;
- structural similarity: header depth, row/column count, grouping;
- readability: human rating at single- and double-column widths;
- claim salience: human rating of whether intended comparisons are easy to find;
- editability: successful rebuild from source spec;
- accessibility: grayscale and color-independent semantics.

Use paper-level train/test separation to prevent reference leakage. Never use a table from the same paper as both a retrieved reference and a test target.
