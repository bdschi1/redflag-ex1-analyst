#!/usr/bin/env python3
"""
run_redflag.py

CLI entry point to run the RedFlag Analyst gate on a text input.

Usage:
  python run_redflag.py --input analyst_note.txt
  python run_redflag.py --input report.pdf
  python run_redflag.py --input research.docx --no-filter
  python run_redflag.py --input analyst_note.txt --output report.json

Design goals:
- Runs locally with deterministic outputs (no API keys required)
- Produces JSON with risk flags, severity scores, and gate recommendation
- Accepts .txt, .pdf, and .docx inputs
- Strips institutional boilerplate by default (configurable)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from boilerplate_filter import BoilerplateFilter
from document_loader import DocumentLoader, UnsupportedFormatError
from redflag_engine import RedFlagAnalyzer


def _default_results_path(input_path: str) -> str:
    """
    Construct a default RESULTS/<input>_<timestamp>.json path.
    """
    results_dir = "RESULTS"
    os.makedirs(results_dir, exist_ok=True)

    base = os.path.splitext(os.path.basename(input_path))[0]
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return os.path.join(results_dir, f"{base}_{ts}.json")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="RedFlag Analyst: gate research drafts for institutional finance risks."
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Path to a .txt, .pdf, or .docx file containing a research draft / analyst note.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Optional path to write JSON output. If omitted, writes to RESULTS/.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    parser.add_argument(
        "--no-filter",
        action="store_true",
        help="Disable boilerplate legal language filtering (filter is ON by default).",
    )
    args = parser.parse_args()

    in_path = args.input
    if not os.path.exists(in_path):
        print(f"ERROR: input file not found: {in_path}", file=sys.stderr)
        return 2

    # --- Load document ---
    loader = DocumentLoader()
    try:
        load_result = loader.load_file(in_path)
    except UnsupportedFormatError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for warning in load_result.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    # --- Boilerplate filter ---
    filter_meta = None
    if args.no_filter:
        text = load_result.text
    else:
        bp_filter = BoilerplateFilter()
        filter_result = bp_filter.filter(load_result.text)
        text = filter_result.filtered_text
        filter_meta = {
            "boilerplate_filter": True,
            "original_chars": filter_result.original_length,
            "filtered_chars": filter_result.filtered_length,
            "chars_removed": filter_result.chars_removed,
            "sections_removed": filter_result.sections_removed,
        }

    # --- Analyze ---
    analyzer = RedFlagAnalyzer()
    result = analyzer.analyze(text)

    # Attach metadata about the input
    result["input"] = {
        "path": in_path,
        "format": load_result.format,
        "chars": load_result.char_count,
        "page_count": load_result.page_count,
        "warnings": load_result.warnings,
    }
    if filter_meta:
        result["preprocessing"] = filter_meta

    json_kwargs: dict = {"ensure_ascii": False}
    if args.pretty:
        json_kwargs.update({"indent": 2, "sort_keys": False})

    payload = json.dumps(result, **json_kwargs)

    # Determine output path
    out_path = args.output if args.output else _default_results_path(in_path)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(payload + "\n")

    # Exit code is useful for CI / gating:
    # 0 PASS, 10 PM_REVIEW, 20 AUTO_REJECT
    gate = result.get("overall", {}).get("gate_decision", "PASS")
    if gate == "PASS":
        return 0
    if gate == "PM_REVIEW":
        return 10
    return 20


if __name__ == "__main__":
    raise SystemExit(main())
