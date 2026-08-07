# Evaluation

Score each artifact from 0 to 2 on six axes: numeric faithfulness, comparison validity, hierarchy, readability at target width, claim salience, and editability/reproducibility. Numeric faithfulness is a hard gate: any unexplained changed value makes the example fail.

Run the NeurIPS collector in `benchmarks/neurips-tables/collect.py` to materialize public-paper table cases locally. The committed index contains source URLs, page/table positions, captions when found, extracted cells, and hashes. Do not commit downloaded PDFs by default.

