# Changelog

All notable changes to FinGuard-Red are documented here.

## [0.2.1] - 2026-02-25

### Added
- **Bayesian risk priors** — `bayesian_risk_priors.py` with beta-binomial conjugate priors for each detection rule, enabling probabilistic audit focus narrowing. Inspired by AuditAgent (2025).
- **`--bayesian` CLI flag** — includes posterior distributions, subject area risk aggregation, and audit focus ranking in JSON output.
- **Bayesian analysis in Streamlit dashboard** — expander section showing subject area risk bars and prioritized audit focus table.
- **55 Bayesian module tests** — total suite now at 157 tests across 5 test files.
- `bayesian_risk_priors.py` and `app_redteam.py` added to CI lint targets.
- `CONTRIBUTING.md` contributor guide.

### Fixed
- `build-backend` in `pyproject.toml` changed from legacy `setuptools.backends._legacy:_Backend` to standard `setuptools.build_meta`.
- Engine version now reads from package metadata (`importlib.metadata`) instead of hardcoded string.
- LICENSE copyright name formatting (removed bracket artifacts).
- `.gitignore` hardened with missing patterns (`*.so`, `*.egg`, `.eggs/`, `*.whl`, `*.tar.gz`, `.tox/`, `.mypy_cache/`).

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
