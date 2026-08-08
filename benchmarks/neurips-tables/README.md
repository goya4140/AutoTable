# NeurIPS Tables benchmark

This directory is a candidate-discovery layer for accepted NeurIPS, ICLR, and ICML papers. It is not itself a paired generation benchmark. The collector uses official proceedings pages and materializes source PDFs, caption anchors, text regions, and table crops locally.

The committed `index.jsonl` is the original high-recall provenance manifest. `index-diverse-2024.jsonl` applies an eight-table-per-paper cap to increase paper coverage. Cached PDFs and crops are ignored because source papers retain their original terms.

## Collection

```bash
python collect.py --year 2024 --papers 50 --max-tables 200 --max-tables-per-paper 8 --out index-diverse-2024.jsonl
python collect.py --venue iclr --year 2024 --papers 50 --max-tables 200
python collect.py --venue icml --year 2024 --papers 50 --max-tables 200
```

Sampling is deterministic. Promote a candidate to `benchmarks/paperbench/cases/` only after a structured `x` is linked and manually verified.

The committed manifests contain a legacy 150-table NeurIPS index, a diversity-capped 200-table/30-paper NeurIPS index, and 25-table ICLR/ICML indexes from 2024. The collector bounds a crop at the next high-confidence caption when possible, but caption anchoring remains high-recall and can include surrounding text or a displaced float; visual QA is mandatory before promotion.

## Weak structural annotations

Build and validate the diagnostic annotation layer:

```bash
python annotate.py index-diverse-2024.jsonl \
  --legacy-development-index index.jsonl \
  --out annotations-diverse-2024.jsonl \
  --summary annotations-summary-2024.json \
  --audit-queue audit-queue-2024.jsonl
python validate_annotations.py index-diverse-2024.jsonl annotations-diverse-2024.jsonl \
  --legacy-development-index index.jsonl \
  --summary annotations-summary-2024.json \
  --audit-queue audit-queue-2024.jsonl
```

The legacy 13 papers form a development partition. The 17 newly collected papers form a paper-disjoint prospective stress partition with 121 records. Rules label purpose, recommended form, numeric/direction/uncertainty signals, crop geometry, extraction artifacts, probable narrative mentions, and multi-table regions. These annotations are explicitly `weak_rule_based` and `gold: false`.

`audit-queue-2024.jsonl` samples 40 prospective records across purposes and unflagged/flagged strata. “Unflagged” only means no current heuristic fired; it is not a human clean-crop label. Every review field is deliberately `pending` or `null`; completing the queue requires inspecting the crop and recording reviewer identity. The validator rejects any discovery record promoted to numeric reconstruction, PaperBench generation-pair, or human-aesthetic gold status.

Render unflagged and flagged review sheets after materializing crops:

```bash
python render_audit_sheet.py audit-queue-2024.jsonl --quality unflagged --out ../../output/audit-unflagged.png
python render_audit_sheet.py audit-queue-2024.jsonl --quality flagged --out ../../output/audit-flagged.png
```

For a public-label regression diagnostic, submit one JSONL prediction per prospective ID:

```json
{"id":"...","action":"route","purpose":"main_results","recommended_form":"comparison_table","quality_flags":[]}
```

```bash
python evaluate_annotations.py annotations-diverse-2024.jsonl predictions.jsonl --out diagnostic-report.json
```

The evaluator reports coverage, narrative-mention filtering, macro purpose/form F1, and quality-flag precision/recall separately. It emits no composite score and fixes `diagnostic_only: true`, `gold: false`, and `leaderboard_eligible: false`, because the rules and labels are public.

## Metrics

- numeric faithfulness: exact normalized cell match;
- structural similarity: header depth, row/column count, grouping;
- readability: human rating at single- and double-column widths;
- claim salience: human rating of whether intended comparisons are easy to find;
- editability: successful rebuild from source spec;
- accessibility: grayscale and color-independent semantics.

Use paper-level train/test separation to prevent reference leakage. Never use a table from the same paper as both a retrieved reference and a test target.
