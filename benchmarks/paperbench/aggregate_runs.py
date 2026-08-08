#!/usr/bin/env python3
"""Compatibility entry point for the Skill's repeated-run aggregator."""
from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "skills/paper-table/scripts/aggregate_runs.py"
SPEC = importlib.util.spec_from_file_location("paper_table_aggregate_runs", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

aggregate = MODULE.aggregate
main = MODULE.main


if __name__ == "__main__":
    main()
