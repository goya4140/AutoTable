# PaperTable

PaperTable turns experimental data into faithful, publication-ready academic tables. It is code-first: values remain traceable from input to LaTeX/HTML output, while an agent actively asks for scientifically important missing data and proposes a visual structure before rendering.

## Why

Academic tables are not screenshots. They are compact arguments: grouping defines what is comparable, emphasis guides the claim, and uncertainty determines whether apparent gains are credible. PaperTable separates those decisions from deterministic rendering and numeric verification.

## Pipeline

1. **Diagnose** the input schema, repeats, missing values, metrics, and intended claim.
2. **Ask** for high-value missing evidence such as seeds, sample-level predictions, units, and comparison design.
3. **Plan** hierarchy, emphasis, precision, uncertainty, and table-vs-chart form.
4. **Render** editable LaTeX and HTML from a declarative JSON spec.
5. **Verify** that every observed value survived the transformation.
6. **Critique** the result at the target paper width and iterate.

Unlike image-first figure systems such as [PaperBanana](https://github.com/dwzhu-pku/PaperBanana), the default renderer is deterministic code. Image generation is intentionally outside the numeric path.

## Quick start

```bash
python skills/paper-table/scripts/analyze_data.py examples/main-results.csv --json
python skills/paper-table/scripts/render_table.py examples/main-results.json --out-dir output/example
python skills/paper-table/scripts/verify_table.py examples/main-results.json output/example/table.tex
```

The reusable Codex Skill lives in [`skills/paper-table`](skills/paper-table). Copy that folder into your Codex skills directory, or invoke it from this repository during development.

## NeurIPS Tables benchmark

`benchmarks/neurips-tables/collect.py` discovers papers from the official NeurIPS proceedings, downloads PDFs into an ignored cache, locates caption-anchored tables with PDFium, creates table regions, and writes a JSONL index. This keeps the committed benchmark auditable without redistributing full PDFs.

```bash
python benchmarks/neurips-tables/collect.py --year 2024 --papers 50 --max-tables 200
```

Each case records the official paper URL, page, bounding box, caption, extracted grid, and SHA-256 hashes. See the benchmark README for the evaluation protocol.

## Status

This is an MVP: deterministic table rendering, input diagnosis, numeric verification, and a reproducible NeurIPS table collector are implemented. Next priorities are multi-level headers, automatic paired significance tests, camera-ready width linting, and a human preference benchmark.

## License

MIT. Source papers remain under their publishers' or authors' terms; benchmark metadata does not relicense them.
