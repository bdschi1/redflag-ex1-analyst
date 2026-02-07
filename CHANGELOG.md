# Changelog

All notable changes to FinGuard-Red are documented here.

## [0.2.0] - 2026-02-07

### Added
- **PDF & DOCX support** — `document_loader.py` accepts `.pdf` (via pdfplumber) and `.docx` (via python-docx) alongside `.txt`.
- **Boilerplate filter** — `boilerplate_filter.py` strips institutional disclaimers, analyst certifications, and distribution notices before analysis. On by default with protected-keyword safety.
- **`--no-filter` CLI flag** — disables boilerplate stripping when raw text analysis is needed.
- **`pyproject.toml`** — proper Python packaging with optional dependency groups (`[test]`, `[dashboard]`).
- **102 tests** across 4 test modules (engine, loader, filter, integration) with 81% coverage.
- **CI coverage reporting** — `pytest-cov` with `fail_under = 80` threshold.
- **Ruff linting & formatting** in CI pipeline.
- Streamlit dashboard now supports PDF/DOCX uploads with a boilerplate filter toggle.
- `preprocessing` metadata in CLI JSON output (chars removed, sections removed).

### Changed
- `datetime.utcnow()` replaced with `datetime.now(timezone.utc)` (deprecation fix).
- Detection thresholds externalized into `DEFAULT_THRESHOLDS` config dict.
- `RedFlagAnalyzer.__init__()` accepts `config` and `max_input_chars` parameters.
- Input size limit enforced (`MAX_INPUT_CHARS = 500_000`).
- Dependencies pinned with compatible version ranges.
- Python version requirement updated from 3.8+ to 3.9+.

### Removed
- Unused `openai` dependency.

## [0.1.0] - 2026-01-01

### Added
- Initial release with 8 deterministic detection rules (MNPI, tipping, expert-network steering, cross-border inducements, options leverage, beta neutrality, MVO trap, crowding risk, liquidity mismatch).
- CLI gate with exit codes (0=PASS, 10=PM_REVIEW, 20=AUTO_REJECT).
- Streamlit dashboard with golden-data adversarial benchmarks.
- 37 engine tests.
