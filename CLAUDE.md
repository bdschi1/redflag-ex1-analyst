# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## What This Is

FinGuard-Red is a deterministic, rule-based red-teaming engine that scans analyst notes, research PDFs, and IC memos for MNPI, tipping, regulatory arbitrage, and portfolio construction traps. It gates outputs as PASS, PM_REVIEW, or AUTO_REJECT in under 60 seconds, with no API keys required.

## Commands

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"

# Run (after pip install, `redflag` is the entry point alias)
redflag -i analyst_note.txt -p
redflag -i report.pdf -p
redflag -i memo.docx -n -p
redflag -i analyst_note.txt --stdout | jq .overall
redflag --version

# Dashboard
pip install -e ".[dashboard]"
streamlit run app_redteam.py

# Tests
pytest tests/ -v

# Lint
ruff check .
ruff format .
```

## Architecture

- **`redflag_engine.py`** -- Core detection engine with 8 rule-based checks (MNPI indicators, expert network hours, cross-border regulatory, defamation, overconfidence, risk limits, crowding/liquidity, options leverage) + sell-side source detection (suppresses MNPI rules for published sell-side research). Produces JSON with flags, severity scores, and a gate decision.
- **`document_loader.py`** -- Unified loader accepting .txt, .pdf, .docx files, returning `LoadResult` with extracted text and metadata.
- **`boilerplate_filter.py`** -- Strips institutional disclaimers before analysis. Uses a protected-keyword safety net so paragraphs containing risk-relevant terms are never removed.
- **`bayesian_risk_priors.py`** -- Beta-binomial conjugate priors for each detection rule, enabling probabilistic audit focus narrowing. Inspired by AuditAgent (2025). Integrated into CLI (`--bayesian`) and dashboard.
- **`run_redflag.py`** -- CLI entry point (`redflag` alias after install). Chains loader -> filter -> engine -> JSON output. Flags: `--stdout`/`-s`, `--pretty`/`-p`, `--no-filter`/`-n`, `--bayesian`, `--version`. Exit codes: 0 (PASS), 10 (PM_REVIEW), 20 (AUTO_REJECT), 2 (error).
- **`app_redteam.py`** -- Streamlit dashboard with file upload, 12 adversarial "Golden Data" scenarios (MNPI, Reg FD, MiFID II, options, factor risk, crowding, liquidity, MVO, overconfidence, concentration, short-and-distort, redemption mismatch), and visual analysis.

## Key Patterns

- **Gate outcomes:** `PASS`, `PM_REVIEW`, `AUTO_REJECT` based on aggregate severity score.
- **Detection rules** are keyword/regex driven with configurable thresholds in `DEFAULT_THRESHOLDS`.
- **Protected-keyword safety:** Boilerplate filter never strips paragraphs containing engine-vocabulary risk keywords.
- **Sell-side bypass:** Published sell-side research (firm name + sell-side language pattern) suppresses MNPI rules; portfolio construction flags remain active. Output includes `sellside_source` metadata.
- **No LLM dependency:** Entirely deterministic and local -- no API keys, no model calls.

## Testing Conventions

- 165 tests across 5 test files, all deterministic (no network/API calls).
- `conftest.py` dynamically generates PDF and DOCX fixtures using fpdf2 and python-docx.
- Test files: `test_redflag_engine.py`, `test_document_loader.py`, `test_boilerplate_filter.py`, `test_bayesian_priors.py`, `test_integration.py`.
- Run `pytest tests/ -v` -- expect 165 passing.
