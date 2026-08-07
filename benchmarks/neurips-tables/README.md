# NeurIPS Tables benchmark

This benchmark evaluates reconstruction and redesign of tables from accepted NeurIPS papers. The collector uses official proceedings pages and materializes source PDFs, extracted cells, and table crops locally.

The committed `index.jsonl` is a provenance manifest. Cached PDFs and crops are ignored because source papers retain their original terms.

## Collection

```bash
python collect.py --year 2024 --papers 50 --max-tables 200
```

Sampling is deterministic. Cases are deduplicated by paper URL, page, bounding box, and extracted-cell hash.

## Metrics

- numeric faithfulness: exact normalized cell match;
- structural similarity: header depth, row/column count, grouping;
- readability: human rating at single- and double-column widths;
- claim salience: human rating of whether intended comparisons are easy to find;
- editability: successful rebuild from source spec;
- accessibility: grayscale and color-independent semantics.

Use paper-level train/test separation to prevent reference leakage. Never use a table from the same paper as both a retrieved reference and a test target.

