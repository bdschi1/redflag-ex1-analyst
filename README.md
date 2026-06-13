<!-- redflag-ex1-analyst/README.md | Last updated: 2026-06-13 -->

# FinGuard-Red

[![CI](https://github.com/bdschi1/redflag-ex1-analyst/actions/workflows/ci.yml/badge.svg)](https://github.com/bdschi1/redflag-ex1-analyst/actions/workflows/ci.yml)
![tests](https://img.shields.io/badge/tests-165%20passing-brightgreen?style=flat)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

A deterministic, rule-based engine that scans analyst notes, research PDFs, and IC memos for regulatory red flags — MNPI, tipping, conflicts of interest, cross-border regulatory arbitrage, and portfolio-construction traps — and gates each document as PASS, PM_REVIEW, or AUTO_REJECT in under 60 seconds. Same input, same output: no model variance, no API keys.

**Plain English:** Every research note passes through this gate before a PM sees it. Clean notes go through, borderline ones get extra review, high-risk ones are blocked. Published sell-side research and SEC filings are treated as zero-MNPI-risk, so MNPI flags are suppressed for them while portfolio-construction flags stay active.

## Install

```
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"        # the `redflag` CLI alias becomes available
```

## Usage

```
redflag -i analyst_note.txt -p            # .txt, .pdf, or .docx; -p = pretty
redflag -i report.pdf --stdout | jq .overall
redflag -i analyst_note.txt --bayesian -p # add Bayesian audit-focus priors
redflag -i report.pdf --no-filter -p      # disable boilerplate stripping
pip install -e ".[dashboard]" && streamlit run app_redteam.py
```

Standard institutional disclaimers are stripped before analysis; a protected-keyword safety net never removes paragraphs containing risk terms (e.g. "insider", "off the record", "soft dollar").

**Exit codes (CI gating):** `0` PASS · `10` PM_REVIEW · `20` AUTO_REJECT · `2` error.

## What it catches

12 golden adversarial scenarios across four families:

- **Compliance & MNPI** — tipping (Dirks v. SEC), Reg FD selective disclosure, MiFID II vs. Section 28(e) arbitrage
- **Portfolio & market mechanics** — options / event risk, factor & beta fallacy, crowding & endogenous risk, liquidity / basis mismatch, MVO optimizer trap
- **Process & governance** — overconfidence / certainty language, position concentration
- **Fund-level structural** — short-and-distort defamation liability, redemption / liquidity mismatch

The `use_cases/` and `failure_cases/` directories contain worked examples modeled on patterns from SEC enforcement actions.

## Tests

```
pytest tests/ -v
```

## License

MIT

> **Disclaimer:** A red-teaming / control artifact. It does not provide legal advice — route flagged items through your firm's Compliance policies and counsel.
